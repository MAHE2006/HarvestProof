"""Import a manufacturer's batch registry from CSV:  python -m scripts.import_batches registry.csv
Columns: batch_code,product_code,mfg,exp   (dates as YYYY-MM-DD). Imported batches are registry-only (signed=False):
a pack is 'genuine' if its batch is listed and not expired, and clone detection still applies.
Pack codes must then be written BATCH-SERIAL-NA  (any text may replace NA)."""
import csv, sys
from datetime import date
from sqlmodel import Session, select
from api import db
from api.db import Batch, Product

db.init_db()
n = bad = 0
with Session(db.engine) as s, open(sys.argv[1], newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        p = s.exec(select(Product).where(Product.code == r["product_code"].strip())).first()
        if not p:
            print("skipped, unknown product:", r["product_code"]); bad += 1; continue
        code = r["batch_code"].strip().upper()
        if s.exec(select(Batch).where(Batch.code == code)).first():
            continue
        s.add(Batch(code=code, product_id=p.id, mfg=date.fromisoformat(r["mfg"]), exp=date.fromisoformat(r["exp"]), signed=False)); n += 1
    s.commit()
print(f"imported {n} batches, skipped {bad}")
