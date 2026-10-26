import io, json, pathlib, secrets, hmac
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Optional
import qrcode
from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select
from . import db, codes, security as sec
from .db import Batch, Efficacy, Label, Product, Scan, Share, Spray, User
from engine import clone, planner
from engine import features as feat
from engine.model import Model

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"
MODEL = Model()


@asynccontextmanager
async def lifespan(app):
    db.init_db()
    with Session(db.engine) as s:
        codes.seed_demo(s)
    yield


app = FastAPI(title="HarvestProof", lifespan=lifespan)
bearer = HTTPBearer(auto_error=False)


def current_user(c: Optional[HTTPAuthorizationCredentials] = Depends(bearer), s: Session = Depends(db.get_session)):
    uid = sec.read_token(c.credentials) if c else None
    u = s.get(User, uid) if uid else None
    if not u:
        raise HTTPException(401, "Sign in required")
    return u


class Reg(BaseModel):
    email: str
    password: str
    name: str = ""
    district: str = ""


class Login(BaseModel):
    email: str
    password: str


@app.post("/api/register")
def register(r: Reg, s: Session = Depends(db.get_session)):
    e = r.email.strip().lower()
    if "@" not in e or len(r.password) < 8:
        raise HTTPException(422, "Use a valid email and a password of at least 8 characters")
    if s.exec(select(User).where(User.email == e)).first():
        raise HTTPException(409, "This email is already registered")
    salt, h = sec.hash_pw(r.password)
    u = User(email=e, name=r.name.strip(), district=r.district.strip(), salt=salt, pw_hash=h, role="admin" if not s.exec(select(User)).first() else "farmer")
    s.add(u); s.commit(); s.refresh(u)
    return {"token": sec.make_token(u.id), "name": u.name, "role": u.role}


@app.post("/api/login")
def login(r: Login, s: Session = Depends(db.get_session)):
    u = s.exec(select(User).where(User.email == r.email.strip().lower())).first()
    if not u or not sec.check_pw(r.password, u.salt, u.pw_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": sec.make_token(u.id), "name": u.name, "role": u.role}


@app.get("/api/meta")
def meta():
    pm = MODEL.img.get("meta", {}) if MODEL.img else {}
    return {"classes": {k: {"crop": v["crop"], "name": v["name"]} for k, v in MODEL.classes.items()}, "crops": sorted({v["crop"] for v in MODEL.classes.values()}),
            "photo_model": {"trained_crops": MODEL.trained_crops, "trained_at": pm.get("trained_at"), "images": pm.get("images")}, "demo": codes.enabled()}


@app.get("/api/demo-codes")
def demo_codes(u: User = Depends(current_user)):
    return codes.demo_codes()


# ---------- 1 diagnose ----------
def named(post):
    return [{"id": c, "name": MODEL.classes[c]["name"], "p": round(p, 4)} for c, p in post]


@app.post("/api/diagnose")
async def diagnose(crop: str = Form(...), answers: str = Form("{}"), features: str = Form(""), image: Optional[UploadFile] = File(None), u: User = Depends(current_user)):
    note, f = "", json.loads(features) if features else None
    if image is not None:
        data = await image.read()
        if len(data) > 8_000_000:
            raise HTTPException(413, "Photo is larger than 8 MB")
        try:
            f = feat.extract(feat.open_image(data))
        except Exception:
            raise HTTPException(422, "That file is not a readable image")
        if f is None:
            note = "We could not find a leaf in that photo. Use a close, well-lit photo of one leaf on a plain background."
    try:
        raw = json.loads(answers)
        ans = {k: v for k, v in raw.items() if v is not None}     # "not sure" answers carry no evidence but are not asked again
        post = MODEL.posterior(crop, f, ans)
    except ValueError:
        raise HTTPException(422, "Unknown crop")
    used = bool(f) and MODEL.crop_trained(crop)
    nq = MODEL.next_question(crop, f, ans, skip=set(raw))
    v = MODEL.verdict(post, nq is not None, crop)
    return {"features": f, "photo_used": used, "photo_trained": MODEL.crop_trained(crop), "note": note,
            "photo_only": named(MODEL.posterior(crop, f, None)) if used else None, "posterior": named(post), "next": nq,
            "verdict": {**v, "name": MODEL.classes[v["id"]]["name"] if v["id"] else None}, "answered": len(ans), "accept": MODEL.accept_for(crop)}


# ---------- 2 verify ----------
def eu_info(mrl):
    if mrl is None:
        return {"level": "unknown", "text": "EU residue limit not recorded for this product on this crop. Check before you export."}
    if mrl <= .05:
        return {"level": "strict", "text": f"The EU limit is very strict ({mrl} mg/kg). India's waiting period may not be enough for export, so get a lab residue test."}
    return {"level": "ok", "text": f"EU limit: {mrl} mg/kg."}


def check_code(s, raw):
    code = raw.strip().upper().replace(" ", "")
    checks = []
    fail = lambda t, x, **k: {"ok": False, "code": code, "title": t, "text": x, "checks": checks, **k}
    parts = code.rsplit("-", 2)
    if len(parts) != 3 or not all(parts):
        checks.append({"name": "Code format", "ok": False, "detail": "Expected BATCH-SERIAL-SIGNATURE"})
        return fail("The code format is wrong", "A code looks like BATCH-SERIAL-SIGNATURE. Re-read it from the pack.")
    batch, serial, sg = parts
    checks.append({"name": "Code format", "ok": True, "detail": "Batch, serial and signature found"})
    b = s.exec(select(Batch).where(Batch.code == batch)).first()
    if not b:
        checks.append({"name": "Registered batch", "ok": False, "detail": "This batch is not in the registry"})
        return fail("This batch is not registered", "Keep the pack and the bill and report the shop.")
    checks.append({"name": "Registered batch", "ok": True, "detail": "Batch found in the registry"})
    if b.signed:
        ok = sec.sig_ok(batch, serial, sg)
        checks.append({"name": "Signature", "ok": ok, "detail": "Matches the issuer's secret key" if ok else "Does not match, so the code is mistyped or forged"})
        if not ok:
            return fail("The signature does not match", "The code was typed wrongly or forged. Re-read it. If it still fails, do not spray.")
    p = s.get(Product, b.product_id)
    if b.exp < date.today():
        checks.append({"name": "Not expired", "ok": False, "detail": f"Expired on {b.exp.isoformat()}"})
        return fail("This pack has expired", f"This batch expired on {b.exp.isoformat()}. Do not use it.", product=p.name)
    checks.append({"name": "Not expired", "ok": True, "detail": f"Valid until {b.exp.isoformat()}"})
    return {"ok": True, "code": code, "batch": b, "product": p, "checks": checks}


class VerifyIn(BaseModel):
    code: str
    district: Optional[str] = None


@app.post("/api/verify")
def verify(v: VerifyIn, u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    r = check_code(s, v.code)
    if not r["ok"]:
        return {k: r[k] for k in r if k != "batch"}
    s.add(Scan(code=r["code"], user_id=u.id, district=(v.district or u.district).strip().lower())); s.commit()
    ev = [(x.ts, x.district) for x in s.exec(select(Scan).where(Scan.code == r["code"], Scan.ts > datetime.now(timezone.utc) - timedelta(days=30))).all()]
    cr = clone.clone_risk(ev)
    r["checks"].append({"name": "Scan pattern", "ok": not cr["flag"], "detail": f"Scanned {cr['scans']} time(s) in {cr['districts']} district(s) in the last 30 days"})
    labels = s.exec(select(Label).where(Label.product_id == r["product"].id)).all()
    base = {"code": r["code"], "product": r["product"].name, "product_code": r["product"].code, "moa": r["product"].moa, "mfg": r["batch"].mfg.isoformat(), "exp": r["batch"].exp.isoformat(), "clone": cr,
            "labels": [{"crop": l.crop, "dose": l.dose, "phi": l.phi} for l in labels], "checks": r["checks"]}
    if cr["flag"]:
        return {"ok": False, "title": "Possible cloned code", "text": "One genuine pack stays in one area. Many districts in a short time suggests copied codes. Ask the shop to confirm before you spray.", **base}
    return {"ok": True, "title": "Genuine pack", "text": "All checks passed.", **base}


class IssueIn(BaseModel):
    product_code: str
    batch: str
    mfg: date
    exp: date
    count: int = 100


@app.post("/api/admin/issue")
def issue(i: IssueIn, u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    if u.role not in ("admin", "issuer"):
        raise HTTPException(403, "Only issuers can create pack codes")
    p = s.exec(select(Product).where(Product.code == i.product_code)).first()
    if not p or not 1 <= i.count <= 5000:
        raise HTTPException(422, "Unknown product or bad count (1 to 5000)")
    b = s.exec(select(Batch).where(Batch.code == i.batch.upper())).first()
    if not b:
        b = Batch(code=i.batch.upper(), product_id=p.id, mfg=i.mfg, exp=i.exp); s.add(b); s.commit()
    return {"codes": [f"{b.code}-{n:05d}-{sec.sig(b.code, f'{n:05d}')}" for n in range(1, i.count + 1)]}


@app.get("/api/qr.png")
def qr(text: str):
    buf = io.BytesIO(); qrcode.make(text[:300]).save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")


# ---------- 3 plan and log ----------
def label_of(s, pid, crop):
    return s.exec(select(Label).where(Label.product_id == pid, Label.crop == crop)).first()


class PlanIn(BaseModel):
    crop: str
    disease: str
    harvest: Optional[date] = None
    field: str = "Plot 1"


@app.post("/api/plan")
def plan(p: PlanIn, u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    if p.disease.endswith("_healthy"):
        return {"no_spray": True, "options": []}
    last = s.exec(select(Spray).where(Spray.user_id == u.id, Spray.field == p.field, Spray.crop == p.crop).order_by(Spray.sprayed.desc())).first()
    last_moa = s.get(Product, last.product_id).moa if last else None
    items = []
    for pr in s.exec(select(Product)).all():
        lb = label_of(s, pr.id, p.crop)
        eff = {e.disease: e.eff for e in s.exec(select(Efficacy).where(Efficacy.product_id == pr.id)).all()}
        items.append({"name": pr.name, "code": pr.code, "moa": pr.moa, "eff": eff, "label": lb and {"phi": lb.phi, "c0": lb.c0, "half_life": lb.half_life, "dose": lb.dose, "eu_mrl": lb.eu_mrl}})
    opts = planner.rank(items, p.disease, p.harvest, date.today(), last_moa)
    for o in opts:
        o["eu"] = eu_info(o["eu_mrl"])
    return {"no_spray": False, "options": opts, "last_moa": last_moa}


class SprayIn(BaseModel):
    field: str
    crop: str
    code: str
    sprayed: date
    disease: Optional[str] = None


@app.post("/api/sprays")
def add_spray(x: SprayIn, u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    r = check_code(s, x.code)
    if not r["ok"]:
        raise HTTPException(422, r["title"] + ". " + r["text"])
    if x.sprayed > date.today():
        raise HTTPException(422, "The spray date is in the future. Log it after you spray.")
    if not label_of(s, r["product"].id, x.crop):
        raise HTTPException(422, f"{r['product'].name} is not registered for {x.crop}")
    sp = Spray(user_id=u.id, field=x.field.strip() or "Plot 1", crop=x.crop, product_id=r["product"].id, batch_code=r["code"], sprayed=x.sprayed, disease=x.disease)
    s.add(sp); s.commit()
    return {"id": sp.id}


@app.delete("/api/sprays/{sid}")
def del_spray(sid: int, u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    sp = s.get(Spray, sid)
    if not sp or sp.user_id != u.id:
        raise HTTPException(404, "Not found")
    s.delete(sp); s.commit()
    return {"ok": True}


# ---------- 4 passport ----------
def groups(s, uid, field=None, crop=None):
    out, today = {}, date.today()
    for sp in s.exec(select(Spray).where(Spray.user_id == uid).order_by(Spray.sprayed)).all():
        if (field and sp.field != field) or (crop and sp.crop != crop):
            continue
        lb, pr = label_of(s, sp.product_id, sp.crop), s.get(Product, sp.product_id)
        w = planner.wait_days(lb.phi, lb.c0, lb.half_life)
        g = out.setdefault((sp.field, sp.crop), {"field": sp.field, "crop": sp.crop, "clear": None, "sprays": []})
        c = sp.sprayed + timedelta(w)
        g["clear"] = max(g["clear"], c) if g["clear"] else c
        g["sprays"].append({"id": sp.id, "date": sp.sprayed.isoformat(), "product": pr.name, "batch": sp.batch_code, "wait": w, "dose": lb.dose, "eu": eu_info(lb.eu_mrl)})
    res = []
    for g in out.values():
        g["hold_days"] = max(0, (g["clear"] - today).days)
        g["clear"] = g["clear"].isoformat()
        g["export_warning"] = any(x["eu"]["level"] != "ok" for x in g["sprays"])
        res.append(g)
    return res


@app.get("/api/passport")
def passport(u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    return {"groups": groups(s, u.id)}


class ShareIn(BaseModel):
    field: str
    crop: str


@app.post("/api/passport/share")
def share(x: ShareIn, u: User = Depends(current_user), s: Session = Depends(db.get_session)):
    t = secrets.token_urlsafe(8)
    s.add(Share(token=t, user_id=u.id, field=x.field, crop=x.crop)); s.commit()
    return {"token": t, "url": f"/p/{t}"}


@app.get("/api/public/passport/{token}")
def public_passport(token: str, s: Session = Depends(db.get_session)):
    sh = s.get(Share, token)
    if not sh:
        raise HTTPException(404, "Passport not found")
    owner = s.get(User, sh.user_id)
    payload = json.dumps({"id": token, "owner": owner.name or "Farmer", "issued": date.today().isoformat(), "groups": groups(s, sh.user_id, sh.field, sh.crop)}, sort_keys=True)
    return {"payload": payload, "signature": sec.sign_payload(payload)}


class CheckIn(BaseModel):
    payload: str
    signature: str


@app.post("/api/public/passport/check")
def check_passport(c: CheckIn):
    return {"valid": hmac.compare_digest(sec.sign_payload(c.payload), c.signature)}


@app.get("/p/{token}")
def passport_page(token: str):
    return FileResponse(WEB / "passport.html")


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
