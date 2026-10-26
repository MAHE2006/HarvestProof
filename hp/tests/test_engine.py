import numpy as np, pathlib, tempfile, json
from datetime import datetime, timedelta
from scripts.make_demo_data import make
from engine import features as F, planner, clone, train
from engine.model import Model


def img(cls, seed=0):
    return np.asarray(make(cls, np.random.default_rng(seed)))


def test_spindle_vs_round_features():
    s, r = F.extract(img("rice_blast")), F.extract(img("rice_brownspot"))
    assert s["spindle"] > .6 and s["round"] < .4
    assert r["round"] > .5 and r["spindle"] < .3


def test_no_leaf_returns_none():
    assert F.extract(np.full((64, 64, 3), 240, np.uint8)) is None


def test_soil_outside_leaf_is_ignored():
    a = img("rice_healthy").copy(); a[:30, :] = (150, 90, 40)
    assert F.extract(a)["burden"] < .02


def test_questions_only_diagnosis_and_gain():
    m = Model()
    q = m.next_question("grapes", None, {})
    assert q and q["gain"] > .3
    post = m.posterior("grapes", None, {"yellow_oily": True, "white_fuzz": True})
    assert post[0][0] == "grapes_downy" and post[0][1] > .9


def test_wait_days_label_only_and_measured_model():
    assert planner.wait_days(21) == 21                         # no measured data: label waiting days
    assert planner.wait_days(21, 8, None, .5) == 21            # measured c0, limit reached on the label day
    assert planner.wait_days(21, 8, None, .01) > 21            # stricter limit extends the wait
    assert abs(planner.residue_at(21, 8, None, 21) - .5) < 1e-6


def test_planner_filters_and_orders():
    from datetime import date
    mk = lambda n, phi, moa, eff, lb=True: {"name": n, "code": n, "moa": moa, "eff": {"d": eff}, "label": {"phi": phi, "dose": "1", "eu_mrl": None} if lb else None}
    items = [mk("long", 30, "3", .8), mk("short", 7, "11", .8), mk("mix", 5, "1+M3", .8), mk("nolabel", 3, "9", .8, False), mk("notlisted", 2, "9", 0)]
    r = planner.rank(items, "d", date(2026, 3, 1), date(2026, 1, 1), None)
    assert [x["code"] for x in r] == ["mix", "short", "long"] and r[0]["recommended"]          # only label-listed products, shortest wait first
    r = planner.rank(items, "d", date(2026, 1, 10), date(2026, 1, 1), None)
    assert [x["code"] for x in r if not x["why"]] == ["mix", "short"] and "too late" in r[2]["why"]
    r = planner.rank(items, "d", None, date(2026, 1, 1), last_moa="1+M3")
    assert r[-1]["code"] == "mix" and "mode of action" in r[-1]["why"]


def test_clone_risk():
    t = datetime(2026, 1, 1)
    assert not clone.clone_risk([(t, "a"), (t + timedelta(days=20), "a")])["flag"]
    assert clone.clone_risk([(t + timedelta(hours=i), f"d{i}") for i in range(5)])["flag"]


def test_training_pipeline_end_to_end():
    from scripts import make_demo_data as g
    tmp = pathlib.Path(tempfile.mkdtemp())
    rng = np.random.default_rng(3)
    for c in g.P:
        (tmp / "img" / c).mkdir(parents=True)
        for i in range(30):
            g.make(c, rng).save(tmp / "img" / c / f"{i}.jpg")
    rep = train.main(["--data", str(tmp / "img"), "--out", str(tmp / "out"), "--min-per-class", "30"])
    assert all(c["test_top1_accuracy"] > .45 for c in rep["crops"].values())   # chance is 0.17 to 0.33 per crop
    m = Model(path=tmp / "out" / "image_model.joblib")
    assert m.trained
    f = F.extract(img("tea_greyblight", 9))
    assert m.crop_trained("tea") and abs(sum(p for _, p in m.posterior("tea", f)) - 1) < 1e-9


def test_shipped_model_covers_tea_and_chilli_only():
    import pytest
    if not (pathlib.Path(__file__).resolve().parent.parent / "models" / "image_model.joblib").exists():
        pytest.skip("no trained model in models/")
    m = Model()
    assert m.trained_crops == ["chilli", "tea"] and not m.crop_trained("rice") and not m.crop_trained("grapes")
    f = F.extract(img("tea_greyblight", 4))
    assert abs(sum(p for _, p in m.posterior("tea", f)) - 1) < 1e-9
    assert m.accept_for("chilli") >= .99          # chilli photos alone are never treated as confident
