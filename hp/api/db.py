import csv, os, pathlib
from datetime import date, datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
URL = os.getenv("DATABASE_URL", "sqlite:///harvestproof.db")
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str = ""
    district: str = ""
    role: str = "farmer"          # farmer | issuer (can issue pack codes) | admin
    salt: str = ""
    pw_hash: str = ""


class Product(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    moa: str = ""                 # FRAC code(s), "+" separated for mixtures


class Label(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(index=True)
    crop: str
    dose: str = ""
    phi: int                      # waiting days from last spray to harvest
    c0: Optional[float] = None    # measured initial residue (ppm), optional
    half_life: Optional[float] = None
    eu_mrl: Optional[float] = None
    source: str = ""


class Efficacy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(index=True)
    disease: str
    eff: float


class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    product_id: int
    mfg: date
    exp: date
    signed: bool = True           # False = imported registry batch without our signature


class Scan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)
    user_id: int
    district: str = ""
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Spray(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    field: str
    crop: str
    product_id: int
    batch_code: str
    sprayed: date
    disease: Optional[str] = None


class Share(SQLModel, table=True):
    token: str = Field(primary_key=True)
    user_id: int
    field: str
    crop: str


def rows(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(r for r in f if not r.startswith("#")))


def num(x, cast=float):
    return cast(x) if x not in ("", None) else None


def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if s.exec(select(Product)).first():
            return
        pid = {}
        for r in rows("products.csv"):
            p = Product(code=r["code"], name=r["name"], moa=r["moa"]); s.add(p); s.commit(); s.refresh(p); pid[p.code] = p.id
        for r in rows("labels.csv"):
            s.add(Label(product_id=pid[r["product_code"]], crop=r["crop"], dose=r["dose"], phi=int(r["phi"]), c0=num(r["c0"]), half_life=num(r["half_life"]), eu_mrl=num(r["eu_mrl"]), source=r["source"]))
        for r in rows("efficacy.csv"):
            s.add(Efficacy(product_id=pid[r["product_code"]], disease=r["disease"], eff=float(r["eff"])))
        s.commit()


def get_session():
    with Session(engine) as s:
        yield s
