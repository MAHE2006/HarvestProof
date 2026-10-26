def clone_risk(events, max_scans=15):
    """events: list of (datetime, district) scans of one code. Many districts in a short time means copied codes."""
    if not events:
        return {"risk": 0.0, "flag": False, "scans": 0, "districts": 0}
    ts = [t for t, _ in events]
    span = (max(ts) - min(ts)).total_seconds() / 86400
    d = len({x for _, x in events if x})
    risk = d / (1 + span / 3)
    return {"risk": round(risk, 2), "flag": risk >= 2 or len(events) > max_scans, "scans": len(events), "districts": d}
