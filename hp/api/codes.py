"""Demo batches so the site is usable on first run. Disable in production with HP_DEMO=0."""
import os
from datetime import date, datetime, timedelta, timezone
from sqlmodel import Session, select
from . import security as sec
from .db import Batch, Product, Scan

DEMO = [("DEMOTR", "TRICY75", 700, "Tricyclazole, rice blast"), ("DEMOAZ", "AZOX23", 700, "Azoxystrobin, chilli and grapes"),
        ("DEMOKR", "KRESO443", 700, "Kresoxim-methyl, tea, rice, chilli, grapes"), ("DEMOHX", "HEXA2", 700, "Hexaconazole, chilli and grapes"),
        ("DEMOOLD", "METRA500", -20, "Metrafenone, expired batch")]


def enabled():
    return os.getenv("HP_DEMO", "1") == "1"


def seed_demo(s: Session):
    if not enabled():
        return
    for code, pc, days, _ in DEMO:
        if not s.exec(select(Batch).where(Batch.code == code)).first():
            p = s.exec(select(Product).where(Product.code == pc)).first()
            s.add(Batch(code=code, product_id=p.id, mfg=date.today() - timedelta(days=100), exp=date.today() + timedelta(days=days)))
    s.commit()
    full = f"DEMOAZ-00009-{sec.sig('DEMOAZ', '00009')}"
    if not s.exec(select(Scan).where(Scan.code == full)).first():     # one code already scanned in 5 districts within hours
        now = datetime.now(timezone.utc)
        for i, d in enumerate(["salem", "erode", "madurai", "theni", "trichy"]):
            s.add(Scan(code=full, user_id=0, district=d, ts=now - timedelta(hours=5 - i)))
        s.commit()


def demo_codes():
    if not enabled():
        return []
    mk = lambda b, n: f"{b}-{n}-{sec.sig(b, n)}"
    return [{"code": mk("DEMOTR", "00001"), "kind": "genuine", "label": "Genuine: tricyclazole (rice)"}, {"code": mk("DEMOAZ", "00001"), "kind": "genuine", "label": "Genuine: azoxystrobin (chilli, grapes)"},
            {"code": mk("DEMOKR", "00001"), "kind": "genuine", "label": "Genuine: kresoxim-methyl (tea and more)"}, {"code": mk("DEMOHX", "00001"), "kind": "genuine", "label": "Genuine: hexaconazole (chilli, grapes)"},
            {"code": mk("DEMOOLD", "00001"), "kind": "expired", "label": "Expired batch"}, {"code": "DEMOTR-00002-AAAAAAAA", "kind": "forged", "label": "Forged signature"},
            {"code": mk("DEMOAZ", "00009"), "kind": "cloned", "label": "Code already scanned in 5 districts"}]
