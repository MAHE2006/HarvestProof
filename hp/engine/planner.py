"""Waiting-period logic and spray planner."""
import math
from datetime import timedelta


def half_life(phi, c0, hl=None, ref=0.5):
    """Measured half-life if known, else the one that reaches `ref` ppm on the label waiting day."""
    if hl:
        return hl
    return phi / math.log2(c0 / ref) if c0 > ref else 1.0


def wait_days(phi, c0=None, hl=None, mrl=None):
    """Days from last spray to safe harvest. With no measured residue data this is the label waiting period.
    If measured c0 (and optionally half-life) AND a residue limit are supplied, the decay curve can extend it."""
    if c0 is None or mrl is None or c0 <= mrl:
        return phi
    return max(phi, math.ceil(half_life(phi, c0, hl) * math.log2(c0 / mrl)))


def residue_at(phi, c0, hl, t):
    return c0 * 2 ** (-t / half_life(phi, c0, hl))


def moa_set(m):
    return {x for x in (m or "").split("+") if x}


def rank(items, disease, harvest, today, last_moa=None):
    """Only products whose label lists this problem on this crop are candidates.
    Order: fits the harvest date, then does not repeat the last mode of action, then shortest waiting period."""
    out = []
    for it in items:
        lb, eff = it["label"], it["eff"].get(disease, 0.0)
        if not lb or eff < .3:
            continue
        wait, why = wait_days(lb["phi"], lb.get("c0"), lb.get("half_life")), ""
        if harvest and today + timedelta(wait) > harvest:
            why = f"too late: earliest harvest would be {(today + timedelta(wait)).isoformat()}"
        elif last_moa and moa_set(it["moa"]) & moa_set(last_moa):
            why = "same mode of action as your last spray (resistance risk)"
        out.append({"product": it["name"], "code": it["code"], "moa": it["moa"], "eff": eff, "wait": wait, "dose": lb["dose"], "eu_mrl": lb.get("eu_mrl"),
                    "earliest": (today + timedelta(wait)).isoformat(), "why": why, "score": round(eff - wait / 1000, 4)})
    out.sort(key=lambda r: (bool(r["why"]), -r["score"], r["product"]))
    for i, r in enumerate(out):
        r["recommended"] = i == 0 and not r["why"]
    return out
