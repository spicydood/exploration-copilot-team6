"""Bundle the front end + one survey's data + recorded answers into a single
HTML file that runs with no server (the clickable prototype / backup demo).

    MOCK=1 python frontend/build_standalone.py            # synthetic survey
    python frontend/build_standalone.py --out demo.html    # real store (keep it on the HPC!)
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config  # noqa: E402
from backend.agent import Agent  # noqa: E402
from backend.render import section_png  # noqa: E402
from backend.store import Store  # noqa: E402
from backend.tools import Tools  # noqa: E402
from backend.views import lead_detail_view, leads_view, meta_view, wells_view  # noqa: E402


def b64png(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode()


def record(agent: Agent, q: str, lead: str | None) -> list[dict]:
    return [ev for ev in agent.stream(q, lead) if ev["type"] != "status" or "Writing" in ev["text"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "exploration-copilot-prototype.html"))
    a = ap.parse_args()
    store = Store(config.STORE_DIR)
    tools = Tools(store)
    agent = Agent(store, mode="offline")

    maps = {k: b64png(store.map_png(k).read_bytes()) for k in store.meta["maps"]}
    inlines = set()
    details = {}
    for d in store.leads:
        det = lead_detail_view(store, tools, d["id"])
        details[d["id"]] = det
        inlines.add(det["section_inline"])
    for w in store.wells:
        if w.get("i") is not None:
            inlines.add(store.il_number(w["i"]))
    sections = {il: b64png(section_png(store, inline=il)) for il in sorted(inlines)}

    answers = {"-|opportunity": record(agent, "What is the geological opportunity, and why?", None),
               "-|similar": record(agent, "Find similar traps yet to be tested", None),
               "rank": record(agent, "Rank the top leads", None)}
    for d in store.leads:
        L = d["id"]
        answers[f"{L}|opportunity"] = record(agent, "What is the geological opportunity here, and why?", L)
        answers[f"{L}|risks"] = record(agent, f"What could make {L} wrong?", L)
        answers[f"{L}|similar"] = record(agent, f"Find similar traps yet to be tested like {L}", L)
    for w in store.wells:
        q = f"Why did {w['name']} {'fail' if w.get('result') == 'dry' else 'succeed'}?"
        answers[f"well|{w['name']}"] = record(agent, q, None)
    il0, xl0 = store.meta["ilines"][0], store.meta["xlines"][0]
    answers["point"] = record(agent, f"Is there oil at inline {il0 + 20}, crossline {xl0 + 20}?", None)

    data = {"meta": meta_view(store), "wells": wells_view(store), "leads": leads_view(store),
            "details": details, "maps": maps, "sections": sections, "answers": answers,
            "health": {"ok": True, "llm_mode": "offline", "prototype": True}}

    fe = ROOT / "frontend"
    html = (fe / "index.html").read_text()
    html = html.replace('<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n', "")
    html = html.replace('<link rel="stylesheet" href="styles.css">',
                        "<style>\n" + (fe / "styles.css").read_text() + "\n</style>")
    payload = json.dumps(data, default=float, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace('<script src="app.js"></script>',
                        f"<script>window.__STANDALONE__={payload};</script>\n<script>\n"
                        + (fe / "app.js").read_text() + "\n</script>")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {len(answers)} recorded answers, "
          f"{len(sections)} sections)")


if __name__ == "__main__":
    main()
