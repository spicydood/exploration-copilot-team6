"""The Exploration Copilot agent.

Stage 1 (plan): choose tools, run them, number every returned fact as evidence [E1], [E2], ...
Stage 2 (write): turn the evidence into a cited answer, streamed token by token.

Both stages use Gemma 4 when LLM=gemma, and fall back to a rule-based planner and a
template writer when the endpoint is slow, down, or LLM=offline. The fallback means the
demo never stalls, and it is also the baseline the LLM must beat in the test bank.
"""
from __future__ import annotations

import json
import re
import time
from typing import Iterator

import config
from . import llm, prompts
from .store import Store
from .tools import Tools

SIMILAR = re.compile(r"similar|look[- ]?alike|analog|like this|yet to be (tested|drilled)|untested", re.I)
RANK = re.compile(r"rank|top|best|which lead|opportunit|prospect|where should|drill next|overview", re.I)
RANKLIST = re.compile(
    r"\brank(?:ing)?\b|\btop\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"(?:undrilled\s+|drilled\s+)?(?:leads|opportunities|prospects))\b|"
    r"\blist\s+(?:(?:all|the)\s+)*(?:(?:undrilled|drilled)\s+)?(?:leads|opportunities|prospects)\b|"
    r"\ball (?:the )?leads\b|\bcompare (?:the )?leads\b|\boverview\b", re.I)
RISK = re.compile(r"wrong|alternative|risk|devil|uncertain|could fail|why not", re.I)
WHY_DRY = re.compile(r"dry|fail|failed|why did|result", re.I)
REFS = re.compile(r"\b(paper|publication|reference|citation|cite|journal|doi)\b", re.I)
ILXL = re.compile(r"(?:inline|\bil)\s*[:#]?\s*([+-]?\d+(?:\.\d+)?).*?"
                  r"(?:crossline|xline|\bxl)\s*[:#]?\s*([+-]?\d+(?:\.\d+)?)", re.I | re.S)


def is_ranking(question: str) -> bool:
    """Explicit lead rankings take priority over the UI's selected lead."""
    analogue = re.search(r"similar|look[- ]?alike|analog|like this", question, re.I)
    return bool(RANKLIST.search(question) and not analogue and not REFS.search(question))


class Agent:
    def __init__(self, store: Store, mode: str | None = None):
        self.s = store
        self.tools = Tools(store)
        self.mode = mode or config.LLM_MODE

    # ------------------------------------------------------------------ public
    def stream(self, question: str, selected_lead: str | None = None) -> Iterator[dict]:
        t0 = time.time()
        evidence: list[dict] = []
        calls: list[dict] = []

        def register(name, args, out):
            ids = []
            for e in out.get("evidence", []):
                e = {**e, "id": f"E{len(evidence) + 1}"}
                evidence.append(e)
                ids.append(e["id"])
            calls.append({"tool": name, "args": args, "result": out.get("result"),
                          "error": out.get("error"), "evidence_ids": ids})
            return ids

        yield {"type": "status", "text": "Planning which measurements to look at"}
        used_llm = self.mode == "gemma"
        # These requests have unambiguous tools, regardless of UI selection or LLM mode.
        direct = bool(ILXL.search(question) or is_ranking(question))
        plan_iter = self._plan_llm(question, selected_lead, calls) if used_llm and not direct else None
        fallback_reason = None
        if plan_iter is not None:
            try:
                for name, args, why in plan_iter:
                    out = self.tools.run(name, args)
                    ids = register(name, args, out)
                    yield {"type": "tool", "name": name, "args": args, "why": why,
                           "evidence_ids": ids, "error": out.get("error")}
            except llm.LLMError as e:
                fallback_reason = "Gemma couldn't plan, so rules chose the measurements"
        if not calls:
            for name, args, why in self._plan_rules(question, selected_lead):
                out = self.tools.run(name, args)
                ids = register(name, args, out)
                yield {"type": "tool", "name": name, "args": args, "why": why,
                       "evidence_ids": ids, "error": out.get("error")}
        self._ensure_lead_evidence(question, selected_lead, calls, register)
        yield {"type": "evidence", "items": evidence}

        yield {"type": "status", "text": "Writing the geological reasoning"}
        text = ""
        location_error = any(c["tool"] == "value_at" and c["error"] for c in calls)
        writer_mode = "gemma" if used_llm and not fallback_reason and not location_error else "offline"
        if writer_mode == "gemma":
            try:
                for tok in llm.stream([
                        {"role": "system", "content": prompts.writer_prompt(question)},
                        {"role": "user", "content": self._writer_user(question, evidence, calls)}]):
                    text += tok
                    yield {"type": "token", "text": tok}
            except llm.LLMError:
                fallback_reason = ("Gemma stopped partway, so the offline reasoner answered" if text
                                   else "Gemma didn't answer, so the offline reasoner did")
                writer_mode = "offline"
            if writer_mode == "gemma" and not text.strip():
                fallback_reason, writer_mode = "Gemma returned an empty answer, so the offline reasoner did", "offline"
            if writer_mode == "offline" and text:
                # Tokens already reached the client: tell it to drop them before the offline answer,
                # so one answer is shown, never half a model answer joined to the template.
                yield {"type": "reset", "text": "Gemma stopped partway. Writing the answer with the offline reasoner"}
                text = ""
        if writer_mode == "offline":
            text = self._write_offline(question, selected_lead, evidence, calls)
            for chunk in re.findall(r"\S+\s*", text):
                yield {"type": "token", "text": chunk}

        cited = sorted(set(re.findall(r"\bE\d+\b", text)), key=lambda x: int(x[1:]))
        yield {"type": "done", "cited": cited,
               "unverified_numbers": [] if location_error else unverified_numbers(text, evidence),
               "mode": writer_mode, "note": fallback_reason, "seconds": round(time.time() - t0, 1)}

    def answer(self, question: str, selected_lead: str | None = None) -> dict:
        """Non-streaming helper for the eval harness."""
        out = {"text": "", "tools": [], "evidence": []}
        for ev in self.stream(question, selected_lead):
            if ev["type"] == "token":
                out["text"] += ev["text"]
            elif ev["type"] == "reset":
                out["text"] = ""
            elif ev["type"] == "tool":
                out["tools"].append(ev["name"])
            elif ev["type"] == "evidence":
                out["evidence"] = ev["items"]
            elif ev["type"] == "done":
                out.update({k: v for k, v in ev.items() if k != "type"})
        return out

    # ------------------------------------------------------------------ planning
    def _plan_llm(self, question, selected_lead, calls):
        msgs = [{"role": "system", "content": prompts.planner_prompt(self.s, config.MAX_TOOL_STEPS)},
                {"role": "user", "content": f"Question: {question}\nSelected lead in the UI: {selected_lead or 'none'}"}]
        for _ in range(config.MAX_TOOL_STEPS):
            reply = llm.chat(msgs, max_tokens=200)
            step = llm.parse_json(reply)
            if step is None:  # one retry with a nudge
                msgs += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "Reply with valid JSON only."}]
                step = llm.parse_json(llm.chat(msgs, max_tokens=200))
            if not step or step.get("done") or "tool" not in step:
                return
            name, args = step["tool"], step.get("args") or {}
            yield name, args, step.get("why", "")
            last = calls[-1] if calls else {}
            msgs += [{"role": "assistant", "content": json.dumps(step)},
                     {"role": "user", "content": "RESULT: " + json.dumps(
                         {"result": last.get("result"), "error": last.get("error"),
                          "evidence_ids": last.get("evidence_ids")}, default=str)[:3500]}]

    def _plan_rules(self, q, selected):
        if REFS.search(q):
            return [("get_leads", {"top": 3}, "context only; no literature tool exists")]
        lead_ids = [x for x in re.findall(r"\bL\d+\b", q.upper()) if self.s.lead(x)]
        wells = [w["name"] for w in self.s.wells if w["name"] in q.lower()]
        m = ILXL.search(q)
        if m:
            return [("value_at", {"inline": m.group(1), "crossline": m.group(2)}, "look up that exact location")]
        if is_ranking(q):
            args = {"top": len(self.s.leads)}
            limit = re.search(r"\btop\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", q, re.I)
            if limit:
                words = dict(zip("one two three four five six seven eight nine ten".split(), range(1, 11)))
                token = limit.group(1).lower()
                args["top"] = int(token) if token.isdigit() else words[token]
            if re.search(r"\b(?:undrilled|untested)\b", q, re.I):
                args["drilled"] = False
            elif re.search(r"\bdrilled\b", q, re.I):
                args["drilled"] = True
            for trap_type in ("Structural", "Stratigraphic", "Combination", "Unclassified"):
                if re.search(rf"\b{trap_type}\b", q, re.I):
                    args["trap_type"] = trap_type
                    break
            return [("get_leads", args, "rank the survey leads")]
        target = (lead_ids or [None])[0] or (self.s.lead_of_well(wells[0])["id"]
                                             if wells and self.s.lead_of_well(wells[0]) else None) or selected
        if SIMILAR.search(q):
            tgt = target or self._best_drilled_discovery()
            if not tgt:
                return [("get_leads", {"top": 5}, "overview")]
            return [("lead_evidence", {"lead_id": tgt}, "understand the reference body"),
                    ("similar_leads", {"target": tgt, "pool": "undrilled", "k": 3}, "find untested look-alikes")]
        if wells and (WHY_DRY.search(q) or not lead_ids):
            steps = [("well_summary", {"well": wells[0]}, "check the well result and logs")]
            lw = self.s.lead_of_well(wells[0])
            if lw:
                steps.append(("lead_evidence", {"lead_id": lw["id"]}, "evidence for the body it drilled"))
            steps.append(("calibration", {}, "compare discoveries with dry wells"))
            return steps
        if target:
            steps = [("lead_evidence", {"lead_id": target}, "measure the lead")]
            d = self.s.lead(target)
            if d and not d["drilled"]:
                steps.append(("similar_leads", {"target": target, "pool": "drilled", "k": 1}, "find a drilled analog"))
            return steps
        best = self._best_undrilled()
        steps = [("get_leads", {"top": 5}, "rank the leads")]
        if best:
            steps += [("lead_evidence", {"lead_id": best}, "evidence for the best undrilled lead"),
                      ("similar_leads", {"target": best, "pool": "drilled", "k": 1}, "find a drilled analog")]
        return steps

    def _ensure_lead_evidence(self, q, selected, calls, register):
        """If the question is about a lead but no lead_evidence was fetched, fetch it."""
        if any(c["tool"] == "lead_evidence" for c in calls) or REFS.search(q) or is_ranking(q):
            return
        lid = (re.findall(r"\bL\d+\b", q.upper()) or [selected])[0]
        if lid and self.s.lead(lid) and not ILXL.search(q):
            register("lead_evidence", {"lead_id": lid}, self.tools.run("lead_evidence", {"lead_id": lid}))

    def _best_undrilled(self):
        und = [d for d in self.s.leads if not d["drilled"]]
        return und[0]["id"] if und else None

    def _best_drilled_discovery(self):
        for d in self.s.leads:
            if any((self.s.well(n) or {}).get("result") == "discovery" for n in d["wells_inside"]):
                return d["id"]
        return None

    # ------------------------------------------------------------------ writing
    def _writer_user(self, question, evidence, calls):
        facts = [{"tool": c["tool"], "args": c["args"], "result": c["result"], "error": c["error"]}
                 for c in calls]
        return (f"QUESTION: {question}\n\nEVIDENCE (cite these tags):\n{prompts.evidence_block(evidence)}"
                f"\n\nTOOL FACTS (for context; cite the evidence tags, not this block):\n"
                f"{json.dumps(facts, default=str)[:6000]}")

    def _write_offline(self, q, selected, evidence, calls) -> str:
        W = OfflineWriter(self.s, evidence, calls)
        tools = [c["tool"] for c in calls]
        if REFS.search(q):
            return ("I don't have a source for that. My evidence is only the measurements made on this survey's "
                    "seismic and well data, so I won't name a paper or reference. Ask me about a lead or a well "
                    "and I will cite the measurements instead.")
        if "value_at" in tools:
            return W.point()
        if RANKLIST.search(q) and "get_leads" in tools:
            return W.ranking()
        if "well_summary" in tools:
            return W.well()
        if RISK.search(q) and "lead_evidence" in tools:
            return W.risks()
        if "similar_leads" in tools and SIMILAR.search(q):
            return W.similar()
        if "lead_evidence" in tools:
            return W.opportunity()
        return W.ranking()


class OfflineWriter:
    """Template writer: same structure as the LLM writer, built only from evidence."""

    def __init__(self, store, evidence, calls):
        self.s, self.ev, self.calls = store, evidence, calls

    def tag(self, label_part: str, lead: str | None = None) -> str:
        for e in self.ev:
            if label_part in e["label"] and (lead is None or e["label"].startswith(lead) or
                                              e.get("ref", {}).get("lead") == lead):
                return f"[{e['id']}]"
        return ""

    def call(self, tool):
        return next((c for c in self.calls if c["tool"] == tool and not c["error"]), None)

    @staticmethod
    def conf(p):
        return "high" if p >= 0.6 else "moderate" if p >= 0.4 else "low"

    def _lead_sections(self, d, res):
        a, st, sc, L = d["attributes"], d["structure"], d["scorecard"], d["id"]
        why = []
        if d["flags"]["stratigraphic"]:
            why.append(f"the sand body is elongate and winding (elongation / sinuosity "
                       f"{d['shape']['elongation']} / {d['shape']['sinuosity']}) {self.tag('shape', L)}, "
                       f"the map signature of a river channel or point bar")
        if d["flags"]["faulted"]:
            why.append(f"{int(round(100 * d['fault_contact_frac']))}% of its outline sits against a mapped fault "
                       f"{self.tag('fault', L)}, so the fault may act as the seal")
        if d["flags"]["closure"]:
            why.append(f"the top-sand surface closes by about {st['closure_ms']} ms around the crest "
                       f"{self.tag('closure', L)}")
        if st.get("updip_is_shale") and d["flags"]["stratigraphic"]:
            why.append(f"sand probability drops to {st['updip_sand_prob']} just up-dip of the crest "
                       f"{self.tag('up-dip', L)}, i.e. it pinches out into shale")
        if not why:
            why.append("no clear closing geometry was measured, so the trap is unproven")
        cal = self.s.meta.get("calibration", {})
        cal_line = ""
        if "discovery" in cal and "dry" in cal:
            cal_line = (f" At wells, discoveries average Vp/Vs {cal['discovery']['vpvs']} against "
                        f"{cal['dry']['vpvs']} for dry wells {self.tag('Vp/Vs at discovery')}.")
        ps = [
            f"- **Reservoir ({self.conf(sc['reservoir'])}):** sand probability {a['sand']['inside']} inside vs "
            f"{a['sand']['outside']} around it {self.tag('sand probability inside', L)}.",
            f"- **Trap ({self.conf(sc['trap'])}):** {d['trap_type'].lower()}, {d['subtype']}.",
            f"- **Seal ({self.conf(sc['seal'])}):** " + (
                "relies on the fault; needs a fault-seal check." if d["flags"]["faulted"]
                else "shale above and around the body; lateral seal is the main uncertainty."
                if d["flags"]["stratigraphic"] else "assumed shale top seal."),
            f"- **Charge ({self.conf(sc['charge'])}):** Vp/Vs {a['vpvs']['inside']} inside vs "
            f"{a['vpvs']['outside']} around {self.tag('Vp/Vs inside', L)}, far-minus-near amplitude "
            f"{abs(a['avo_diff']['z'] or 0)} sd {'above' if (a['avo_diff']['z'] or 0) >= 0 else 'below'} "
            f"the survey average {self.tag('far-minus-near', L)}.{cal_line}",
        ]
        return why, ps

    def opportunity(self) -> str:
        le = self.call("lead_evidence")
        d = self.s.lead(le["args"]["lead_id"])
        res = le["result"]
        why, ps = self._lead_sections(d, res)
        drilled = (f"It has been drilled by {', '.join(d['wells_inside'])} "
                   f"({', '.join(str(w['result']) for w in res['wells'])}) {self.tag('well ')}."
                   if d["drilled"] else "It has not been drilled.")
        sim = self.call("similar_leads")
        analog = ""
        if sim and sim["result"]["similar"]:
            r = sim["result"]["similar"][0]
            wr = ", ".join(f"{k}: {v}" for k, v in r.get("well_results", {}).items()) or "no wells"
            analog = (f"\n\n**Closest drilled analog:** {r['id']} (similarity {r['similarity']} "
                      f"{self.tag(r['id'] + ' similarity')}; {wr}). Shared traits: "
                      f"{nice(r['matching_features']) or 'few'}.")
        alt = res["alternatives"][0] if res["alternatives"] else None
        results = [w["result"] for w in res["wells"]]
        if "discovery" in results:
            rec = "treat as a proven play: appraise it and use it as the analog for undrilled look-alikes"
        elif results:
            rec = "downgrade unless the failure at the well is explained and avoidable elsewhere"
        elif d["gcos"] >= 0.15:
            rec = "mature to prospect: run AVO modelling at the analog well and map the seal"
        else:
            rec = "keep as a lead until the weakest element is de-risked"
        weakest = min(d["scorecard"], key=d["scorecard"].get)
        out = [
            f"**Opportunity** - {d['id']} is a {d['trap_type'].lower()} lead ({d['subtype']}), "
            f"{d['area_km2']} km² {self.tag('area', d['id'])}, with a geological chance of success of "
            f"{d['gcos']} {self.tag('GCoS', d['id'])}. {drilled} Recommendation: {rec}.",
            "**Trap type and why** - " + "; ".join(why) + ".",
            "**Petroleum system**\n" + "\n".join(ps),
            "**What could make this wrong** - " + (f"{alt['alternative']} De-risk: {alt['de_risk']}" if alt
                                                    else "no specific alternative flagged."),
        ]
        out.append(f"**Next step** - attack the weakest element, {weakest} "
                   f"({d['scorecard'][weakest]}) {self.tag('scorecard', d['id'])}." + analog)
        return "\n\n".join(out)

    def risks(self) -> str:
        le = self.call("lead_evidence")
        d = self.s.lead(le["args"]["lead_id"])
        alts = le["result"]["alternatives"]
        lines = [f"**What could make {d['id']} wrong** - scorecard {self.tag('scorecard', d['id'])}, "
                 f"weakest element: {min(d['scorecard'], key=d['scorecard'].get)}."]
        for k, a in enumerate(alts, 1):
            lines.append(f"{k}. **{a['risk'].capitalize()}:** {a['alternative']} *De-risk:* {a['de_risk']}")
        if not alts:
            lines.append("No alternative interpretation was triggered by the measurements.")
        return "\n\n".join(lines)

    def similar(self) -> str:
        sim = self.call("similar_leads")
        ref = sim["result"]["reference"]
        rows = sim["result"]["similar"]
        head = (f"**Similar traps yet to be tested** - compared with {ref['id']} ({ref['trap_type'].lower()}, "
                f"{'drilled by ' + ', '.join(ref['wells_inside']) if ref['wells_inside'] else 'undrilled'}):")
        lines = [head, "", "| Lead | Trap | Similarity | GCoS | Shared traits |", "|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['trap_type']} | {r['similarity']} {self.tag(r['id'] + ' similarity')} "
                         f"| {r['gcos']} | {nice(r['matching_features']) or '-'} |")
        if rows:
            lines += ["", f"**Next step** - review {rows[0]['id']} first: highest similarity among undrilled bodies."]
        else:
            lines += ["", "No undrilled lead resembles it closely."]
        return "\n".join(lines)

    def well(self) -> str:
        ws = self.call("well_summary")
        r = ws["result"]
        w = self.s.well(r["well"])
        logs = w.get("logs", {})
        out = [f"**{r['well']}** - result: {r['result_text'] or r['result']} {self.tag('result')}. "
               f"Inline {r['inline']}, crossline {r['crossline']} {self.tag('location inline')}."]
        if logs.get("res_in_sand_p90") is not None:
            out.append(f"Logs: sands make up {int(100 * logs.get('sand_fraction', 0))}% of the logged interval "
                       f"{self.tag('sand fraction')}, with sand resistivity (P90) {logs['res_in_sand_p90']} ohm.m vs "
                       f"{logs.get('res_in_shale_median')} in shale {self.tag('resistivity')}.")
        le = self.call("lead_evidence")
        if le:
            d = self.s.lead(le["args"]["lead_id"])
            why, ps = self._lead_sections(d, le["result"])
            out.append(f"It tested {d['id']}, a {d['trap_type'].lower()} lead:\n" + "\n".join(ps))
            if w.get("result") == "dry":
                out.append("**Most likely reason it failed** - " + self._dry_reason(w, d, le))
        else:
            out.append("The well does not sit inside a mapped lead, which is consistent with no reservoir "
                       "or trap at this location.")
        return "\n\n".join(out)

    def _dry_reason(self, w, d, le) -> str:
        cal = self.s.meta.get("calibration", {})
        at = (w.get("attributes_at_well") or {})
        if "discovery" in cal and "dry" in cal and "vpvs" in at:
            v, dv, wv = at["vpvs"], cal["discovery"]["vpvs"], cal["dry"]["vpvs"]
            if abs(v - wv) < abs(v - dv):
                return (f"charge. The reservoir is there (sand probability {at.get('sand')} at the well "
                        f"{self.tag('Sand probability at well')}), but Vp/Vs at the well is {v} "
                        f"{self.tag('Vp/Vs at well')}, closer to the dry-well average {wv} than to the "
                        f"discovery average {dv} {self.tag('Vp/Vs at discovery')}: a water-wet sand. "
                        + ("The fault next to it likely separates it from the charged block, so the fault "
                           "probably seals." if d["flags"]["faulted"] else ""))
        alts = le["result"]["alternatives"]
        return " ".join(f"({k}) {a['alternative']}" for k, a in enumerate(alts, 1)) or "not resolved by the evidence."

    def point(self) -> str:
        va = self.call("value_at")
        if va is None:
            failed = next((c for c in self.calls if c["tool"] == "value_at" and c["error"]), None)
            reason = failed["error"] if failed else "The location could not be checked."
            return (f"**Location unavailable** - {reason} No measurement was returned. "
                    "Choose an inline and crossline shown on the survey.")
        r = va["result"]
        v, thr = r["values"], r["sand_threshold"]
        inside = r["in_lead"]
        if not inside and v["sand"] < thr:
            return (f"**No evidence of an opportunity here.** Sand probability is {v['sand']} "
                    f"{self.tag('Sand probability at')}, below the {thr} used to call sand, and the point is not "
                    f"inside any mapped lead {self.tag('lead at')}. I can't say there is oil or gas here; a "
                    f"well or a new lead would be needed first.")
        return (f"The point lies {'inside ' + inside if inside else 'outside any mapped lead'} "
                f"{self.tag('lead at')}. Sand probability {v['sand']} {self.tag('Sand probability at')}, "
                f"Vp/Vs {v['vpvs']} {self.tag('Vp/Vs at')}. Ask about {inside or 'the nearest lead'} "
                f"for the full reasoning.")

    def ranking(self) -> str:
        gl = self.call("get_leads")
        rows = gl["result"]["leads"] if gl else []
        lines = ["**Leads ranked by geological chance of success**", "",
                 "| Lead | Trap | Area km² | GCoS | Drilled |", "|---|---|---|---|---|"]
        for r in rows:
            lines.append(f"| {r['id']} | {r['trap_type']} | {r['area_km2']} | {r['gcos']} {self.tag(r['id'] + ' GCoS')} "
                         f"| {', '.join(r['wells_inside']) or 'no'} |")
        return "\n".join(lines)


FEATURE_NAMES = {"sand_in": "sand probability", "vpvs_z": "low Vp/Vs", "avo_z": "far-stack brightening",
                 "pimp_z": "low impedance", "log_area": "size", "elongation": "shape",
                 "closure_ms": "structural closure"}


def nice(features: list[str]) -> str:
    return ", ".join(FEATURE_NAMES.get(f, f) for f in features)


NUM = re.compile(r"(?<![A-Za-z\d.])-?\d+(?:\.\d+)?")


def unverified_numbers(text: str, evidence: list[dict]) -> list[str]:
    """Numbers in the answer that appear in no evidence value (a hallucination check)."""
    pool = set()
    for e in evidence:
        for part in (e.get("value"), e.get("compare"), e.get("label"), e.get("note")):
            for n in NUM.findall(str(part)):
                pool.add(n.lstrip("-"))
                try:
                    f = float(n)
                    pool.update({f"{abs(f):g}", f"{abs(f):.1f}", f"{abs(f):.2f}", str(int(round(abs(f) * 100)))})
                except ValueError:
                    pass
    clean = re.sub(r"\[E\d+\]|\bL\d+\b|\bE\d+\b", "", text)
    bad = [n for n in NUM.findall(clean) if n.lstrip("-") not in pool and len(n.lstrip("-")) > 1]
    return sorted(set(bad))
