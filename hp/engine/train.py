"""Train the photo likelihood tables from a labelled image folder.

    data/images/<class_id>/*.jpg      (class_id values come from data/classes.csv)

Steps: stratified train/val/test split, learn quantile bins, per-class bin likelihoods (Laplace smoothing),
fit a temperature on validation so probabilities are calibrated, pick the confidence threshold that reaches
the target precision on validation, then report everything on the untouched test split.
"""
import argparse, json, math, pathlib, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from . import features as F
from .model import Model, read_csv, DATA

EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def load_items(root, classes, min_per_class):
    """Classes with no photo folder stay question-only. A crop must be fully covered or not at all."""
    items, skipped_classes = [], []
    for c in classes:
        files = [p for p in sorted((root / c).glob("*")) if p.suffix.lower() in EXT] if (root / c).is_dir() else []
        if not files:
            skipped_classes.append(c)
            continue
        if len(files) < min_per_class:
            raise SystemExit(f"Class '{c}' has {len(files)} images in {root / c}; need at least {min_per_class}. "
                             f"Add images, or remove the class from data/classes.csv.")
        items += [(p, c) for p in files]
    crops = {r["class_id"]: r["crop"] for r in read_csv(DATA / "classes.csv")}
    for c in skipped_classes:
        if any(crops[x] == crops[c] for _, x in items):
            raise SystemExit(f"Crop '{crops[c]}' has photos for some classes but none for '{c}'. Add photos or remove '{c}' from data/classes.csv.")
    if skipped_classes:
        print("Question-only (no photos):", ", ".join(skipped_classes))
    return items, [c for c in classes if c not in skipped_classes]


def _ext(p):
    try:
        return F.extract(F.open_image(p))
    except Exception:
        return None


def featurize(items, workers=4):
    X, y, skipped = [], [], 0
    with ProcessPoolExecutor(workers) as ex:
        for i, f in enumerate(ex.map(_ext, [p for p, _ in items], chunksize=16)):
            if f is None:
                skipped += 1
                continue
            X.append([f[k] for k in F.FEATURES])
            y.append(items[i][1])
            if (i + 1) % 1000 == 0:
                print(f"  features {i + 1}/{len(items)}", flush=True)
    return np.array(X), np.array(y), skipped


def split(y, rng, fr=(.7, .15)):
    tr, va, te = [], [], []
    for c in np.unique(y):
        idx = rng.permutation(np.where(y == c)[0])
        a, b = int(len(idx) * fr[0]), int(len(idx) * (fr[0] + fr[1]))
        tr += list(idx[:a]); va += list(idx[a:b]); te += list(idx[b:])
    return np.array(tr), np.array(va), np.array(te)


def fit(X, y, classes, crops, seed=7):
    """One gradient-boosted classifier per crop on the lesion features. Balanced weights so rare classes are not ignored."""
    out = {}
    for crop in sorted(set(crops[c] for c in classes)):
        cls = [c for c in classes if crops[c] == crop]
        m = np.isin(y, cls)
        clf = HistGradientBoostingClassifier(max_iter=200, learning_rate=.08, class_weight="balanced", random_state=seed).fit(X[m], y[m])
        out[crop] = {"clf": clf, "classes": [str(c) for c in clf.classes_], "T": 1.0}
    return {"crops": out, "meta": {}}


def predict(model, X, y, Ts=None):
    """Image-only posteriors restricted to the true crop's classes. Returns (top class, top prob, prob of truth)."""
    for crop, T in (Ts or {}).items():
        model.img["crops"][crop]["T"] = T
    out = []
    for row, c in zip(X, y):
        post = model.posterior(model.classes[c]["crop"], dict(zip(F.FEATURES, row.tolist())), None)
        out.append((post[0][0], post[0][1], dict(post).get(c, 0.0)))
    return out


def nll(res):
    return -float(np.mean([math.log(max(p, 1e-9)) for _, _, p in res]))


def ece(res, y, bins=10):
    conf = np.array([p for _, p, _ in res]); ok = np.array([a == t for (a, _, _), t in zip(res, y)], float)
    e = 0.0
    for lo in np.linspace(0, 1, bins, endpoint=False):
        m = (conf > lo) & (conf <= lo + 1 / bins)
        if m.any():
            e += m.mean() * abs(ok[m].mean() - conf[m].mean())
    return float(e)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/images")
    ap.add_argument("--out", default="models")
    ap.add_argument("--min-per-class", type=int, default=30)
    ap.add_argument("--target-precision", type=float, default=.9)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    classes = [r["class_id"] for r in read_csv(DATA / "classes.csv")]
    items, classes = load_items(pathlib.Path(a.data), classes, a.min_per_class)
    print(f"{len(items)} images, {len(classes)} classes")
    X, y, skipped = featurize(items, a.workers)
    rng = np.random.default_rng(a.seed)
    tr, va, te = split(y, rng)
    crops = {r["class_id"]: r["crop"] for r in read_csv(DATA / "classes.csv")}
    img = fit(X[tr], y[tr], classes, crops, a.seed)
    m = Model(img=img)
    rep = {"trained_at": time.strftime("%Y-%m-%d %H:%M"), "images": len(items), "skipped_no_leaf": skipped, "train": len(tr), "val": len(va), "test": len(te),
           "model": "per-crop gradient boosting on lesion-geometry and colour features (no neural network)", "crops": {}}
    accept = {}
    for crop in img["crops"]:
        v = np.array([crops[c] == crop for c in y[va]]); t = np.array([crops[c] == crop for c in y[te]])
        temps = np.arange(.5, 6.01, .25)
        T = float(min(temps, key=lambda tt: nll(predict(m, X[va][v], y[va][v], {crop: tt}))))
        val = predict(m, X[va][v], y[va][v], {crop: T})
        thr = None
        for th in np.arange(.5, .995, .01):
            ok = [a_ == c for (a_, p, _), c in zip(val, y[va][v]) if p >= th]
            if len(ok) >= max(10, .1 * len(val)) and np.mean(ok) >= a.target_precision:
                thr = float(round(th, 2)); break
        warn = None
        if thr is None:
            thr, warn = .99, f"Target precision {a.target_precision} not reached on validation, so the photo alone is never treated as confident for {crop}. The app will ask questions instead."
        accept[crop] = thr
        test = predict(m, X[te][t], y[te][t])
        acc = [a_ == c for (a_, p, _), c in zip(test, y[te][t]) if p >= thr]
        cl = sorted({c for c in y[te][t]})
        rep["crops"][crop] = {"test_images": int(t.sum()), "temperature": T, "accept_threshold": thr, "test_top1_accuracy": float(np.mean([a_ == c for (a_, _, _), c in zip(test, y[te][t])])),
                              "test_coverage_at_threshold": len(acc) / len(test), "test_precision_at_threshold": float(np.mean(acc)) if acc else None, "test_ece": ece(test, y[te][t]),
                              "per_class_recall": {c: float(np.mean([a_ == c for (a_, _, _), tt in zip(test, y[te][t]) if tt == c])) for c in cl},
                              "confusion": {tc: {pc: int(sum(1 for (a_, _, _), tt in zip(test, y[te][t]) if tt == tc and a_ == pc)) for pc in cl} for tc in cl}, "warning": warn}
    img["meta"] = {"accept": accept, "trained_at": rep["trained_at"], "images": len(items), "classes": classes}
    out = pathlib.Path(a.out); out.mkdir(exist_ok=True)
    joblib.dump(img, out / "image_model.joblib")
    (out / "report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps({k: ({c: {kk: vv for kk, vv in d.items() if kk not in ("confusion",)} for c, d in v.items()} if k == "crops" else v) for k, v in rep.items()}, indent=2))
    return rep


if __name__ == "__main__":
    main()
