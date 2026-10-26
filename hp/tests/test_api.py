import os, io, json, tempfile
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["HP_SECRET"] = "test-secret"
os.environ["HP_DEMO"] = "1"
import numpy as np
from datetime import date, timedelta
from fastapi.testclient import TestClient
from scripts.make_demo_data import make
from api.main import app, eu_info


def hdr(c, email="a@x.com"):
    r = c.post("/api/register", json={"email": email, "password": "longpassword", "name": "Asha", "district": "Madurai"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_eu_info():
    assert eu_info(None)["level"] == "unknown" and eu_info(.01)["level"] == "strict" and eu_info(3.0)["level"] == "ok"


def test_full_flow():
    with TestClient(app) as c:
        assert c.post("/api/diagnose", data={"crop": "rice"}).status_code == 401
        h = hdr(c)
        assert c.post("/api/register", json={"email": "a@x.com", "password": "longpassword"}).status_code == 409
        assert c.post("/api/login", json={"email": "a@x.com", "password": "bad"}).status_code == 401
        assert c.post("/api/login", json={"email": "a@x.com", "password": "longpassword"}).status_code == 200
        t = date.today()
        # demo codes behave as labelled
        demo = {d["kind"]: d["code"] for d in c.get("/api/demo-codes", headers=h).json()}
        g = c.post("/api/verify", headers=h, json={"code": demo["genuine"]}).json()
        assert g["ok"] and [k["name"] for k in g["checks"]] == ["Code format", "Registered batch", "Signature", "Not expired", "Scan pattern"] and all(k["ok"] for k in g["checks"])
        assert "expired" in c.post("/api/verify", headers=h, json={"code": demo["expired"]}).json()["title"].lower()
        assert "signature" in c.post("/api/verify", headers=h, json={"code": demo["forged"]}).json()["title"].lower()
        assert "cloned" in c.post("/api/verify", headers=h, json={"code": demo["cloned"]}).json()["title"].lower()
        assert c.post("/api/verify", headers=h, json={"code": "NOPE-00001-AAAAAAAA"}).json()["title"] == "This batch is not registered"
        # issue codes (first user is admin) and verify one
        codes = c.post("/api/admin/issue", headers=h, json={"product_code": "TRICY75", "batch": "t1", "mfg": str(t - timedelta(days=5)), "exp": str(t + timedelta(days=500)), "count": 3}).json()["codes"]
        good = codes[0]
        assert c.post("/api/verify", headers=h, json={"code": good}).json()["product_code"] == "TRICY75"
        bad = good[:-1] + ("A" if good[-1] != "A" else "B")
        assert not c.post("/api/verify", headers=h, json={"code": bad}).json()["ok"]
        # diagnose: questions only, photo on a trained crop and an untrained crop
        r = c.post("/api/diagnose", headers=h, data={"crop": "grapes", "answers": "{}"}).json()
        assert r["next"] and len(r["posterior"]) == 3 and not r["photo_trained"]
        first = c.post("/api/diagnose", headers=h, data={"crop": "grapes", "answers": "{}"}).json()["next"]["question"]
        r = c.post("/api/diagnose", headers=h, data={"crop": "grapes", "answers": json.dumps({first: None})}).json()
        assert r["next"]["question"] != first and r["answered"] == 0     # 'not sure' is never asked twice
        r = c.post("/api/diagnose", headers=h, data={"crop": "grapes", "answers": '{"yellow_oily":true,"white_fuzz":true}'}).json()
        assert r["verdict"]["status"] == "confident" and r["verdict"]["id"] == "grapes_downy"
        buf = io.BytesIO(); make("tea_greyblight", np.random.default_rng(1)).save(buf, "JPEG")
        r = c.post("/api/diagnose", headers=h, data={"crop": "tea", "answers": "{}"}, files={"image": ("l.jpg", buf.getvalue(), "image/jpeg")}).json()
        assert r["features"] and r["photo_used"] and r["photo_only"] and len(r["posterior"]) == 6
        assert c.post("/api/diagnose", headers=h, data={"crop": "rice"}, files={"image": ("x.jpg", b"notanimage", "image/jpeg")}).status_code == 422
        # plan: only products whose label lists the problem; harvest date filters
        p = c.post("/api/plan", headers=h, json={"crop": "rice", "disease": "rice_blast", "harvest": str(t + timedelta(days=40))}).json()["options"]
        assert p[0]["recommended"] and p[0]["wait"] <= 12 and all(o["code"] != "AZOX23" for o in p)
        assert any(o["code"] == "ISOPRO40" and "too late" in o["why"] for o in p)
        assert not any(o["recommended"] for o in c.post("/api/plan", headers=h, json={"crop": "rice", "disease": "rice_blast", "harvest": str(t + timedelta(days=3))}).json()["options"])
        assert c.post("/api/plan", headers=h, json={"crop": "rice", "disease": "rice_healthy"}).json()["no_spray"]
        assert c.post("/api/plan", headers=h, json={"crop": "chilli", "disease": "chilli_murda"}).json()["options"] == []
        # log sprays: wrong crop, future date, forged code rejected
        base = {"field": "Plot 1", "crop": "grapes", "code": good, "sprayed": str(t)}
        assert c.post("/api/sprays", headers=h, json=base).status_code == 422
        assert c.post("/api/sprays", headers=h, json={**base, "crop": "rice", "sprayed": str(t + timedelta(days=2))}).status_code == 422
        assert c.post("/api/sprays", headers=h, json={**base, "crop": "rice", "code": bad}).status_code == 422
        assert c.post("/api/sprays", headers=h, json={**base, "crop": "rice", "sprayed": str(t - timedelta(days=10))}).status_code == 200
        g = c.get("/api/passport", headers=h).json()["groups"][0]
        assert g["clear"] == str(t - timedelta(days=10) + timedelta(days=30)) and g["hold_days"] == 20 and g["export_warning"]
        # a later rotation: same mode of action as the last spray is ruled out
        p = c.post("/api/plan", headers=h, json={"crop": "rice", "disease": "rice_blast", "field": "Plot 1"}).json()
        assert any(o["code"] == "TRICY75" and "mode of action" in o["why"] for o in p["options"])
        # share and signature
        tok = c.post("/api/passport/share", headers=h, json={"field": "Plot 1", "crop": "rice"}).json()["token"]
        pub = c.get(f"/api/public/passport/{tok}").json()
        assert c.post("/api/public/passport/check", json=pub).json()["valid"]
        pub["payload"] = pub["payload"].replace("Asha", "Bob")
        assert not c.post("/api/public/passport/check", json=pub).json()["valid"]
        # isolation between users
        h2 = hdr(c, "b@x.com")
        assert c.get("/api/passport", headers=h2).json()["groups"] == []
        assert c.delete(f"/api/sprays/{g['sprays'][0]['id']}", headers=h2).status_code == 404
        assert c.post("/api/admin/issue", headers=h2, json={"product_code": "TRICY75", "batch": "z", "mfg": str(t), "exp": str(t), "count": 1}).status_code == 403
        assert c.get("/api/qr.png?text=hello").headers["content-type"] == "image/png"


def test_sample_photos_and_static_pages():
    import pathlib
    from api.main import WEB
    with TestClient(app) as c:
        h = hdr(c, "s@x.com")
        for name, crop in [("tea_greyblight", "tea"), ("chilli_powdery", "chilli")]:
            img = (WEB / "samples" / f"{name}.jpg").read_bytes()
            r = c.post("/api/diagnose", headers=h, data={"crop": crop, "answers": "{}"}, files={"image": ("s.jpg", img, "image/jpeg")}).json()
            assert r["photo_used"] and r["photo_only"] and abs(sum(x["p"] for x in r["posterior"]) - 1) < 1e-3 and r["verdict"]["status"] in ("confident", "asking", "leading", "uncertain")
        assert "HarvestProof" in c.get("/").text and c.get("/samples/tea_healthy.jpg").status_code == 200
        assert c.get("/p/abc").status_code == 200 and c.get("/api/meta").json()["photo_model"]["trained_crops"] == ["chilli", "tea"]
