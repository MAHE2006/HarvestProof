"""Writes SYNTHETIC leaf images so you can test the training pipeline. A model trained on these is NOT usable on real leaves."""
import argparse, pathlib
import numpy as np
from PIL import Image, ImageDraw

# class: (lesion count range, long axis, short axis, colour, yellow patches, white patches)
P = {"rice_blast": ((4, 10), (9, 14), (2, 4), "b", 0, 0), "rice_brownspot": ((10, 25), (3, 5), (3, 5), "b", 0, 0), "rice_healthy": ((0, 1), (3, 4), (3, 4), "b", 0, 0),
     "chilli_cercospora": ((3, 8), (7, 11), (7, 11), "b", 0, 0), "chilli_powdery": ((0, 2), (3, 4), (3, 4), "b", 0, 6), "chilli_murda": ((0, 2), (3, 4), (3, 4), "b", 3, 0),
     "chilli_nutritional": ((0, 2), (3, 4), (3, 4), "b", 6, 0), "chilli_healthy": ((0, 1), (3, 4), (3, 4), "b", 0, 0),
     "grapes_downy": ((2, 5), (4, 6), (4, 6), "b", 6, 0), "grapes_powdery": ((0, 2), (3, 4), (3, 4), "b", 0, 6), "grapes_healthy": ((0, 1), (3, 4), (3, 4), "b", 0, 0),
     "tea_greyblight": ((3, 7), (8, 12), (8, 12), "b", 0, 0), "tea_brownblight": ((2, 4), (14, 20), (10, 14), "b", 0, 0), "tea_algalspot": ((12, 25), (2, 3), (2, 3), "b", 0, 0),
     "tea_redspot": ((6, 14), (4, 6), (4, 6), "b", 2, 0), "tea_helopeltis": ((8, 16), (2, 3), (2, 3), "b", 0, 0), "tea_healthy": ((0, 1), (3, 4), (3, 4), "b", 0, 0)}


def blob(d, rng, cx, cy, rx, ry, ang, fill):
    t = np.linspace(0, 6.283, 24)
    x, y = rx * np.cos(t), ry * np.sin(t)
    pts = [(cx + x[i] * np.cos(ang) - y[i] * np.sin(ang), cy + x[i] * np.sin(ang) + y[i] * np.cos(ang)) for i in range(24)]
    d.polygon(pts, fill=fill)


def make(cls, rng, size=192):
    im = Image.new("RGB", (size, size), (238, 238, 238))
    d = ImageDraw.Draw(im)
    g = tuple(int(v) for v in (45 + rng.integers(-10, 10), 140 + rng.integers(-15, 15), 55 + rng.integers(-10, 10)))
    d.ellipse((12, 12, size - 12, size - 12), fill=g)
    (n0, n1), (a0, a1), (b0, b1), _, ny, nw = P[cls]
    pos = lambda: (rng.uniform(40, size - 40), rng.uniform(40, size - 40))
    for _ in range(int(rng.integers(n0, n1 + 1))):
        cx, cy = pos()
        blob(d, rng, cx, cy, rng.uniform(a0, a1), rng.uniform(b0, b1), rng.uniform(0, 3.14), (150 + int(rng.integers(-15, 15)), 90, 40))
    for _ in range(int(rng.integers(0, ny + 1)) if ny else 0):
        cx, cy = pos(); blob(d, rng, cx, cy, rng.uniform(10, 20), rng.uniform(10, 20), 0, (225, 205, 40))
    for _ in range(int(rng.integers(0, nw + 1)) if nw else 0):
        cx, cy = pos(); blob(d, rng, cx, cy, rng.uniform(10, 20), rng.uniform(10, 20), 0, (245, 245, 245))
    a = np.asarray(im).astype(np.int16) + rng.integers(-8, 9, (size, size, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/demo_images")
    ap.add_argument("--n", type=int, default=60)
    a = ap.parse_args()
    rng = np.random.default_rng(1)
    for c in P:
        p = pathlib.Path(a.out) / c
        p.mkdir(parents=True, exist_ok=True)
        for i in range(a.n):
            make(c, rng).save(p / f"{i:03d}.jpg", quality=92)
    print("wrote synthetic images to", a.out)
