"""Lesion-geometry features from a leaf photo. No neural network: colour segmentation plus shape statistics."""
import io
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

FEATURES = ["burden", "yellow", "white", "n_lesions", "spindle", "round", "lesion_v", "median_size", "green", "dark", "lesion_h"]
MAXSIDE = 256


def open_image(data):
    im = Image.open(io.BytesIO(data) if isinstance(data, (bytes, bytearray)) else data)
    im.draft("RGB", (MAXSIDE * 2, MAXSIDE * 2))   # fast decode of very large JPEGs
    im = im.convert("RGB")
    im.thumbnail((MAXSIDE, MAXSIDE))
    return np.asarray(im)


def _hsv(a):
    a = a.astype(np.float32) / 255
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    c = mx - mn
    s = np.where(mx > 0, c / np.maximum(mx, 1e-6), 0)
    cc = np.maximum(c, 1e-6)
    h = np.where(mx == r, ((g - b) / cc) % 6, np.where(mx == g, (b - r) / cc + 2, (r - g) / cc + 4)) * 60
    return np.where(c == 0, 0, h), s, mx


def _largest(mask):
    lab, k = ndi.label(mask)
    if k > 1:
        mask = lab == 1 + int(np.argmax(ndi.sum(mask, lab, range(1, k + 1))))
    return mask


def _plain_background_region(rgb):
    """If the photo border is one flat colour (a sheet of paper, a table), the leaf is whatever differs from it."""
    b = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(np.float32)
    if b.std(0).mean() > 22:
        return None
    fg = np.abs(rgb.astype(np.float32) - np.median(b, 0)).sum(-1) > 70
    fg = _largest(ndi.binary_fill_holes(ndi.binary_opening(fg, iterations=1)))
    return fg if .06 < fg.mean() < .92 else None


def extract(rgb):
    """Returns a dict of FEATURES, or None when no leaf is found."""
    h, s, v = _hsv(rgb)
    n = h.size
    white = (s < .12) & (v > .8)
    green = (s > .25) & (h >= 60) & (h < 165) & (v > .15)
    yellow = (s > .35) & (h >= 42) & (h < 60) & (v > .5)
    brown = (s > .25) & (h < 42) & (v < .8) & (v > .12)
    body = green | yellow
    region = _plain_background_region(rgb)
    if region is None:
        # Field photo: leaf = largest filled blob of leaf-coloured pixels. Brown outside it (soil) is ignored.
        if body.sum() < .05 * n:
            return None
        region = ndi.binary_fill_holes(ndi.binary_closing(body, iterations=3))
        region = _largest(region)
    region = ndi.binary_dilation(region, iterations=2)
    area = float(region.sum())
    if area < .05 * n:
        return None
    dark = (s < .25) & (v < .55) & (v > .08)
    lesion = (brown | dark) & region
    brown = lesion
    lab, k = ndi.label(brown)
    comps = []
    if k:
        sizes = ndi.sum(brown, lab, range(1, k + 1))
        min_a = max(6, int(.0002 * n))
        for i, sl in enumerate(ndi.find_objects(lab)):
            if sizes[i] < min_a:
                continue
            ys, xs = np.nonzero(lab[sl] == i + 1)
            cx = xs.var() + 1 / 12
            cy = ys.var() + 1 / 12
            cxy = ((xs - xs.mean()) * (ys - ys.mean())).mean()
            t, q = (cx + cy) / 2, np.sqrt(((cx - cy) / 2) ** 2 + cxy ** 2)
            comps.append((float(sizes[i]), float(np.sqrt((t + q) / max(t - q, 1e-6)))))
    comps = sorted(comps, reverse=True)[:300]
    tot = sum(a for a, _ in comps) or 1.0
    return {
        "burden": float(brown.sum() / area),
        "yellow": float((yellow & region).sum() / area),
        "white": float((white & region).sum() / area),
        "n_lesions": float(len(comps)),
        "spindle": sum(a for a, r in comps if r >= 2.2) / tot,
        "round": sum(a for a, r in comps if r < 1.7 and a >= 12) / tot,
        "lesion_v": float(v[brown].mean()) if brown.any() else 0.0,
        "green": float((green & region).sum() / area),
        "dark": float((dark & region).sum() / area),
        "lesion_h": float(h[brown].mean() / 360) if brown.any() else 0.0,
        "median_size": float(np.median([a for a, _ in comps]) / area) if comps else 0.0,
    }
