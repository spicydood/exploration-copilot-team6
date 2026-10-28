"""Agent tools. Each one reads the precomputed store and returns
    {"result": <compact facts>, "evidence": [<items the answer may cite>]}
Evidence items carry the exact numbers the copilot is allowed to quote, plus a
`ref` the UI uses to highlight the lead, well or map behind the claim.
"""
from __future__ import annotations

import numpy as np

from engine.leads import similar as _similar
from .store import Store

TOOL_SPECS = [
    {"name": "get_leads", "description": "List leads ranked by geological chance of success (GCoS). "
     "Use for 'what are the opportunities', ranking and overview questions.",
     "args": {"trap_type": "optional: Structural | Stratigraphic | Combination | Unclassified",
              "drilled": "optional: true | false", "top": "optional int, default 5"}},
    {"name": "lead_evidence", "description": "Full evidence for one lead: trap type and why, attributes "
     "inside vs outside, structure, fault contact, wells, petroleum-system scorecard, alternatives.",
     "args": {"lead_id": "e.g. L1"}},
    {"name": "well_summary", "description": "Logs, result and seismic attributes at one well, plus the lead it sits in.",
     "args": {"well": "well name, e.g. kenari-1"}},
    {"name": "similar_leads", "description": "Undrilled leads most similar to a lead or to the lead a well found. "
     "Use for 'find similar traps yet to be tested'.",
     "args": {"target": "lead id (L2) or well name", "k": "optional int, default 3",
              "pool": "optional: undrilled (default, untested look-alikes) | drilled (analog wells) | all"}},
    {"name": "value_at", "description": "All attribute values at an inline/crossline location and whether it is inside a lead.",
     "args": {"inline": "int", "crossline": "int"}},
    {"name": "calibration", "description": "Average attribute values at discovery wells vs dry wells.",
     "args": {}},
]

UNITS = {"sand": "", "vpvs": "", "pimp": "", "avo_diff": "", "rms_full": "", "disc": ""}
NAMES = {"sand": "Sand probability", "vpvs": "Vp/Vs", "pimp": "P-impedance",
         "avo_diff": "Far-minus-near amplitude", "rms_full": "Full-stack RMS amplitude"}


def _ev(label, value, unit="", compare=None, ref=None, note=None):
    return {"label": label, "value": value, "unit": unit, "compare": compare, "ref": ref or {}, "note": note}


def _lead_brief(d: dict) -> dict:
    return {"id": d["id"], "trap_type": d["trap_type"], "subtype": d["subtype"],
            "gcos": d["gcos"], "area_km2": d["area_km2"], "drilled": d["drilled"],
            "wells_inside": d["wells_inside"], "nearest_well": d["nearest_well"]}


class Tools:
    def __init__(self, store: Store):
        self.s = store

    def run(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if fn is None or name.startswith("_") or name == "run":
            return {"error": f"unknown tool {name}", "evidence": []}
        try:
            return fn(**(args or {}))
        except TypeError as e:
            return {"error": f"bad arguments for {name}: {e}", "evidence": []}
        except Exception as e:  # never crash the chat
            return {"error": f"{name} failed: {e}", "evidence": []}

    # ------------------------------------------------------------------ tools
    def get_leads(self, trap_type=None, drilled=None, top=5):
        rows = self.s.leads
        if trap_type:
            rows = [d for d in rows if d["trap_type"].lower().startswith(str(trap_type).lower()[:5])]
        if drilled is not None and str(drilled).lower() in ("true", "false"):
            want = str(drilled).lower() == "true"
            rows = [d for d in rows if d["drilled"] == want]
        rows = rows[: int(top or 5)]
        ev = []
        for d in rows:
            ev.append(_ev(f"{d['id']} GCoS ({d['trap_type']}, {'drilled' if d['drilled'] else 'undrilled'})",
                          d["gcos"], "", ref={"lead": d["id"]}))
            ev.append(_ev(f"{d['id']} area", d["area_km2"], "km2", ref={"lead": d["id"]}))
        return {"result": {"leads": [_lead_brief(d) for d in rows],
                           "n_total": len(self.s.leads)}, "evidence": ev}

    def lead_evidence(self, lead_id):
        d = self.s.lead(lead_id)
        if not d:
            return {"error": f"no lead {lead_id}; valid ids: {[x['id'] for x in self.s.leads]}", "evidence": []}
        a, st, sc = d["attributes"], d["structure"], d["scorecard"]
        cal = self.s.meta.get("calibration", {})
        ref = {"lead": d["id"]}
        ev = [
            _ev(f"{d['id']} trap type", f"{d['trap_type']}: {d['subtype']}", ref=ref),
            _ev(f"{d['id']} sand probability inside vs around", a["sand"]["inside"], "",
                compare=a["sand"]["outside"], ref={**ref, "map": "sand"}),
            _ev(f"{d['id']} Vp/Vs inside vs around", a["vpvs"]["inside"], "",
                compare=a["vpvs"]["outside"], ref={**ref, "map": "vpvs"}),
            _ev(f"{d['id']} far-minus-near amplitude (z-score vs survey)", a["avo_diff"]["z"], "sd",
                ref={**ref, "map": "avo_diff"}),
            _ev(f"{d['id']} P-impedance inside vs around", a["pimp"]["inside"], "",
                compare=a["pimp"]["outside"], ref={**ref, "map": "pimp"}),
            _ev(f"{d['id']} shape: elongation / sinuosity",
                f"{d['shape']['elongation']} / {d['shape']['sinuosity']}", ref=ref),
            _ev(f"{d['id']} closure (crest to spill on top-sand time)", st["closure_ms"], "ms",
                ref={**ref, "map": "top_time"}),
            _ev(f"{d['id']} sand probability just up-dip of the crest", st["updip_sand_prob"], "",
                compare=self.s.meta.get("sand_threshold"), ref={**ref, "map": "sand"},
                note="compare = threshold used to call sand"),
            _ev(f"{d['id']} share of outline touching a mapped fault", d["fault_contact_frac"], "",
                ref={**ref, "map": "disc"}),
            _ev(f"{d['id']} area", d["area_km2"], "km2", ref=ref),
            _ev(f"{d['id']} scorecard reservoir / trap / seal / charge",
                f"{sc['reservoir']} / {sc['trap']} / {sc['seal']} / {sc['charge']}", ref=ref),
            _ev(f"{d['id']} GCoS", d["gcos"], "", ref=ref),
        ]
        wells = []
        for n in d["wells_inside"]:
            w = self.s.well(n) or {}
            wells.append({"well": n, "result": w.get("result"), "result_text": w.get("result_text")})
            ev.append(_ev(f"well {n} inside {d['id']}: result", w.get("result_text") or w.get("result"),
                          ref={"well": n, "lead": d["id"]}))
        if "discovery" in cal and "dry" in cal:
            ev.append(_ev("Vp/Vs at discovery wells vs dry wells", cal["discovery"]["vpvs"], "",
                          compare=cal["dry"]["vpvs"], ref={"map": "vpvs"}))
            ev.append(_ev("Sand probability at discovery wells vs dry wells", cal["discovery"]["sand"], "",
                          compare=cal["dry"]["sand"], ref={"map": "sand"}))
        return {"result": {"lead": _lead_brief(d), "wells": wells, "flags": d["flags"],
                           "alternatives": self._alternatives(d)}, "evidence": ev}

    def well_summary(self, well):
        w = self.s.well(well)
        if not w:
            return {"error": f"no well {well}; valid: {[x['name'] for x in self.s.wells]}", "evidence": []}
        lead = self.s.lead_of_well(w["name"])
        logs = w.get("logs", {})
        ref = {"well": w["name"]}
        ev = [_ev(f"well {w['name']} result", w.get("result_text") or w.get("result"), ref=ref)]
        if w.get("i") is not None:
            ev.append(_ev(f"well {w['name']} location inline / crossline",
                          f"{self.s.il_number(w['i'])} / {self.s.xl_number(w['j'])}", ref=ref))
        if "sand_fraction" in logs:
            ev.append(_ev(f"well {w['name']} sand fraction of logged interval (GR below {logs.get('gr_sand_cutoff')})",
                          logs["sand_fraction"], "", ref=ref))
        if logs.get("res_in_sand_p90") is not None:
            ev.append(_ev(f"well {w['name']} resistivity in sands (P90) vs shale median",
                          logs["res_in_sand_p90"], "ohm.m", compare=logs.get("res_in_shale_median"), ref=ref))
        for k, v in (w.get("attributes_at_well") or {}).items():
            if k in NAMES:
                ev.append(_ev(f"well {w['name']} {NAMES[k]} at well location", v, ref={**ref, "map": k}))
        cal = self.s.meta.get("calibration", {})
        if "discovery" in cal and "dry" in cal:
            ev.append(_ev("Vp/Vs at discovery wells vs dry wells", cal["discovery"]["vpvs"], "",
                          compare=cal["dry"]["vpvs"], ref={"map": "vpvs"}))
        return {"result": {"well": w["name"], "result": w.get("result"), "result_text": w.get("result_text"),
                           "inline": self.s.il_number(w["i"]) if w.get("i") is not None else None,
                           "crossline": self.s.xl_number(w["j"]) if w.get("j") is not None else None,
                           "curves": logs.get("curves"), "in_lead": lead["id"] if lead else None},
                "evidence": ev}

    def similar_leads(self, target, k=3, pool="undrilled"):
        t = str(target)
        lead = self.s.lead(t) or self.s.lead_of_well(t)
        if not lead:
            return {"error": f"{target} is not a lead id or a well inside a lead", "evidence": []}
        rows = _similar(self.s.leads, lead["id"], k=int(k or 3), pool=pool or "undrilled")
        for r in rows:
            r["well_results"] = {n: (self.s.well(n) or {}).get("result") for n in r["wells_inside"]}
        ev = []
        for r in rows:
            ev.append(_ev(f"{r['id']} similarity to {lead['id']} (cosine, 1 = identical)", r["similarity"], "",
                          ref={"lead": r["id"]}, note="matching: " + (", ".join(r["matching_features"]) or "none")))
            ev.append(_ev(f"{r['id']} GCoS", r["gcos"], "", ref={"lead": r["id"]}))
        return {"result": {"reference": _lead_brief(lead), "pool": pool, "similar": rows}, "evidence": ev}

    def value_at(self, inline, crossline):
        i, j = self.s.il_index(inline), self.s.xl_index(crossline)
        vals = {k: round(float(self.s.map(k)[i, j]), 3) for k in NAMES}
        lead = self.s.lead_at(i, j)
        ref = {"point": [i, j]}
        ev = [_ev(f"{NAMES[k]} at IL {inline} / XL {crossline}", v, ref={**ref, "map": k}) for k, v in vals.items()]
        ev.append(_ev(f"lead at IL {inline} / XL {crossline}", lead["id"] if lead else "none", ref=ref))
        ev.append(_ev("sand probability threshold used to call sand", self.s.meta.get("sand_threshold"), ""))
        return {"result": {"values": vals, "in_lead": lead["id"] if lead else None,
                           "sand_threshold": self.s.meta.get("sand_threshold")}, "evidence": ev}

    def calibration(self):
        cal = self.s.meta.get("calibration", {})
        ev = []
        for res, vals in cal.items():
            for k, v in vals.items():
                if k in NAMES:
                    ev.append(_ev(f"{NAMES[k]} average at {res} wells (n={vals.get('n_wells')})", v,
                                  ref={"map": k}))
        return {"result": cal, "evidence": ev}

    # ------------------------------------------------------------------ rules
    def _alternatives(self, d: dict) -> list[dict]:
        alt, f, a = [], d["flags"], d["attributes"]
        if (a["vpvs"]["z"] or 0) < -1 or (a["avo_diff"]["z"] or 0) > 1:
            alt.append({"risk": "charge", "alternative": "Low-saturation ('fizz') gas or a lithology effect "
                        "can give the same low Vp/Vs and far-stack brightening as commercial gas.",
                        "de_risk": "AVO modelling at a calibrated well; check for a flat spot or "
                        "amplitude conformance to structure."})
        if f["stratigraphic"]:
            alt.append({"risk": "reservoir/seal", "alternative": "The channel may be partly mud-filled or "
                        "below seismic resolution, so sands may not be connected along its length.",
                        "de_risk": "Map sand probability along the channel axis; compare thickness at nearby wells."})
        if f["faulted"]:
            alt.append({"risk": "seal", "alternative": "The bounding fault may leak if sand is juxtaposed "
                        "against sand across it.", "de_risk": "Fault juxtaposition / shale-gouge analysis."})
        if f["closure"]:
            alt.append({"risk": "trap", "alternative": "Closure measured in time can shrink or vanish "
                        "after depth conversion.", "de_risk": "Depth-convert with well velocities."})
        if not d["wells_inside"]:
            alt.append({"risk": "calibration", "alternative": "No well tests this body directly; the case "
                        "rests on analogy with drilled bodies.", "de_risk": "Compare with the most similar drilled lead."})
        return alt
