"""Exploration Copilot API + static front end.

    MOCK=1 uvicorn backend.app:app --port 8800            # laptop, synthetic survey
    uvicorn backend.app:app --host 127.0.0.1 --port 8800  # HPC, then open http://localhost:8800 in Firefox
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from backend import llm  # noqa: E402
from backend.agent import Agent  # noqa: E402
from backend.render import section_png  # noqa: E402
from backend.store import Store  # noqa: E402
from backend.tools import Tools  # noqa: E402
from backend.views import lead_detail_view, leads_view, meta_view, wells_view  # noqa: E402

store = Store(config.STORE_DIR)
agent = Agent(store)
tools = Tools(store)
app = FastAPI(title="Exploration Copilot")

CACHE_ON = os.environ.get("CACHE", "0") == "1"
CACHE_PATH = Path(store.root) / "answer_cache.json"
_cache: dict = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}


class ChatIn(BaseModel):
    message: str
    selected_lead: str | None = None
    audience: str | None = None          # "geoscientist" (default) | "executive": plain-language wording
    hide_wells: list[str] | None = None  # blind well test; accepted now, honoured by the tools once implemented


def _key(msg: str, lead: str | None) -> str:
    return f"{lead or '-'}|{re.sub(r'[^a-z0-9 ]', '', msg.lower()).strip()}"


@app.get("/api/health")
def health():
    return {"ok": True, "mock": config.MOCK, "synthetic": store.meta.get("synthetic"),
            "llm_mode": agent.mode, "llm_reachable": llm.reachable() if agent.mode == "gemma" else None,
            "cache": CACHE_ON, "cached_answers": len(_cache),
            "hide_wells": False,   # flip to True when Tools honour ChatIn.hide_wells (blind well test)
            "renders": sorted(p.stem for p in (Path(store.root) / "renders").glob("*.png")) if (Path(store.root) / "renders").exists() else []}


@app.get("/api/meta")
def meta():
    return meta_view(store)


@app.get("/api/wells")
def wells():
    return wells_view(store)


@app.get("/api/leads")
def leads():
    return leads_view(store)


@app.get("/api/leads/{lead_id}")
def lead_detail(lead_id: str):
    out = lead_detail_view(store, tools, lead_id)
    if out is None:
        raise HTTPException(404, f"no lead {lead_id}")
    return out


@app.get("/api/map/{name}.png")
def map_png(name: str):
    p = store.map_png(name)
    if not p.exists():
        raise HTTPException(404, f"no map {name}")
    return FileResponse(p, media_type="image/png")


@app.get("/api/render/{name}.png")
def render_png(name: str):
    """Static renders made by the engine (volume, stack_L3, ...): store/renders/<name>.png."""
    p = Path(store.root) / "renders" / f"{re.sub(r'[^A-Za-z0-9_-]', '', name)}.png"
    if not p.exists():
        raise HTTPException(404, f"no render {name}; run python -m engine.render_instrument")
    return FileResponse(p, media_type="image/png")


@app.get("/api/section.png")
def section(inline: int | None = None, crossline: int | None = None):
    if inline is None and crossline is None:
        raise HTTPException(400, "give inline or crossline")
    return Response(section_png(store, inline=inline, crossline=crossline), media_type="image/png")


@app.post("/api/chat")
def chat(body: ChatIn):
    message = body.message
    if body.audience == "executive":
        message += " (Answer for an asset manager: plain words, no jargon, say the odds as 'about 1 in N'.)"
    key = _key(message, body.selected_lead)

    def gen():
        if CACHE_ON and key in _cache:
            for ev in _cache[key]:
                if ev["type"] == "token":
                    time.sleep(0.012)
                yield f"data: {json.dumps(ev)}\n\n"
            return
        events = []
        for ev in agent.stream(message, body.selected_lead):
            events.append(ev)
            yield f"data: {json.dumps(ev, default=str)}\n\n"
        if CACHE_ON:
            _cache[key] = events
            CACHE_PATH.write_text(json.dumps(_cache, default=str))

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


FRONTEND = Path(config.ROOT) / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
