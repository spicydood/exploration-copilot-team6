"""JSON views shared by the API (app.py) and the prototype builder."""
from __future__ import annotations

from .store import Store
from .tools import Tools


def meta_view(store: Store) -> dict:
    # The frontend needs actual coordinates, including gaps and non-unit steps.
    return dict(store.meta)


def wells_view(store: Store) -> list[dict]:
    keep = ("name", "i", "j", "result", "result_text", "attributes_at_well", "inside_survey")
    out = []
    for w in store.wells:
        row = {k: w.get(k) for k in keep}
        row["inline"] = store.il_number(w["i"]) if w.get("i") is not None else None
        row["crossline"] = store.xl_number(w["j"]) if w.get("j") is not None else None
        out.append(row)
    return out


def leads_view(store: Store) -> list[dict]:
    keep = ("id", "name", "trap_type", "subtype", "gcos", "area_km2", "risked_area_km2", "drilled",
            "wells_inside", "nearest_well", "polygon", "centroid", "scorecard", "score_basis", "score_note")
    return [{k: d[k] for k in keep} for d in store.leads]


def lead_detail_view(store: Store, tools: Tools, lead_id: str) -> dict | None:
    d = store.lead(lead_id)
    if not d:
        return None
    ev = tools.lead_evidence(d["id"])
    pool = "drilled" if not d["drilled"] else "undrilled"
    sim = tools.similar_leads(d["id"], k=3, pool=pool)
    crest_i = d["crest"][0] if d.get("crest") else d["centroid"][0]
    return {"lead": d, "evidence": ev["evidence"], "alternatives": ev["result"]["alternatives"],
            "wells": ev["result"]["wells"], "similar": sim.get("result", {}).get("similar", []),
            "similar_pool": pool, "section_inline": store.il_number(crest_i)}
