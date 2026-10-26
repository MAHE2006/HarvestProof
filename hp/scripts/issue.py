"""Issue real pack codes for a product:  python -m scripts.issue TRICY75 B2603 --count 10
Product codes are in data/products.csv. Codes carry a signature that only your HP_SECRET can produce."""
import argparse
from datetime import date, timedelta
from sqlmodel import Session, select
from api import db, security as sec
from api.db import Batch, Product

ap = argparse.ArgumentParser()
ap.add_argument("product_code"); ap.add_argument("batch"); ap.add_argument("--count", type=int, default=10); ap.add_argument("--months", type=int, default=24)
a = ap.parse_args()
db.init_db()
with Session(db.engine) as s:
    p = s.exec(select(Product).where(Product.code == a.product_code)).first()
    if not p:
        raise SystemExit("Unknown product code. See data/products.csv")
    b = s.exec(select(Batch).where(Batch.code == a.batch.upper())).first()
    if not b:
        b = Batch(code=a.batch.upper(), product_id=p.id, mfg=date.today(), exp=date.today() + timedelta(days=30 * a.months)); s.add(b); s.commit()
    for n in range(1, a.count + 1):
        print(f"{b.code}-{n:05d}-{sec.sig(b.code, f'{n:05d}')}")
