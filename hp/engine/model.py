"""Evidence-fusion diagnosis: trained photo likelihoods + question answers, with information-gain question choice."""
import csv, math, pathlib
import joblib
import numpy as np
from .features import FEATURES

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, MODELS = ROOT / "data", ROOT / "models"


def read_csv(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(r for r in f if not r.startswith("#")))


def entropy(p):
    p = np.asarray(p)
    return float(-(p[p > 0] * np.log2(p[p > 0])).sum())


class Model:
    def __init__(self, img=None, path=None):
        self.classes = {r["class_id"]: {"crop": r["crop"], "name": r["name"], "prior": float(r["prior"])} for r in read_csv(DATA / "classes.csv")}
        self.questions = {r["question"]: r["text"] for r in read_csv(DATA / "questions.csv")}
        self.qlik = {}
        for r in read_csv(DATA / "question_likelihoods.csv"):
            self.qlik.setdefault(r["class_id"], {})[r["question"]] = float(r["p_yes"])
        p = pathlib.Path(path) if path else MODELS / "image_model.joblib"
        # Only load model files that you trained yourself: joblib files can run code when loaded.
        self.img = img or (joblib.load(p) if p.exists() else None)

    @property
    def trained(self):
        return bool(self.img)

    def crop_trained(self, crop):
        return bool(self.img) and crop in self.img["crops"]

    @property
    def trained_crops(self):
        return sorted(self.img["crops"]) if self.img else []

    def accept_for(self, crop):
        return (self.img or {}).get("meta", {}).get("accept", {}).get(crop, .8)

    def posterior(self, crop, feats=None, answers=None, use_img=True):
        ids = [c for c, v in self.classes.items() if v["crop"] == crop]
        if not ids:
            raise ValueError("unknown crop")
        lp = np.log([self.classes[c]["prior"] for c in ids])
        if use_img and feats and self.crop_trained(crop):
            m = self.img["crops"][crop]
            pr = dict(zip(m["classes"], m["clf"].predict_proba([[feats.get(f, 0.0) for f in FEATURES]])[0]))
            lp += np.array([math.log(max(pr.get(c, 0.0), 1e-6)) for c in ids]) / m["T"]
        for q, a in (answers or {}).items():
            if a is None or q not in self.questions:
                continue
            for j, c in enumerate(ids):
                p = min(max(self.qlik[c][q], 1e-3), 1 - 1e-3)
                lp[j] += math.log(p if a else 1 - p)
        e = np.exp(lp - lp.max())
        e /= e.sum()
        return sorted(zip(ids, e.tolist()), key=lambda x: -x[1])

    def next_question(self, crop, feats, answers, skip=()):
        """The unanswered question with the highest expected entropy reduction."""
        post = self.posterior(crop, feats, answers)
        base = entropy([p for _, p in post])
        best = None
        for q in self.questions:
            if q in (answers or {}) or q in skip:
                continue
            py = sum(p * self.qlik[c][q] for c, p in post)
            hy = entropy([p for _, p in self.posterior(crop, feats, {**(answers or {}), q: True})])
            hn = entropy([p for _, p in self.posterior(crop, feats, {**(answers or {}), q: False})])
            g = base - py * hy - (1 - py) * hn
            if best is None or g > best["gain"]:
                best = {"question": q, "text": self.questions[q], "gain": round(g, 4)}
        return best if best and best["gain"] > 1e-3 else None

    def verdict(self, post, has_next, crop):
        c, p = post[0]
        if p >= self.accept_for(crop):
            return {"status": "confident", "id": c, "p": p}
        if has_next:
            return {"status": "asking", "id": c, "p": p}
        return {"status": "leading" if p >= .6 else "uncertain", "id": c if p >= .6 else None, "p": p}
