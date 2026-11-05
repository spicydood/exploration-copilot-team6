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
import hashlib
import logging
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from backend import llm  # noqa: E402
from backend.agent import Agent  # noqa: E402
from backend.render import section_png  # noqa: E402
from backend.store import InvalidLocationError, Store, json_safe  # noqa: E402
from backend.tools import Tools  # noqa: E402
from backend.views import lead_detail_view, leads_view, meta_view, wells_view  # noqa: E402

store = Store(config.STORE_DIR)
agent = Agent(store)
tools = Tools(store)
app = FastAPI(title="Exploration Copilot")

CACHE_ON = os.environ.get("CACHE", "0") == "1"
CACHE_PATH = Path(store.root) / "answer_cache.json"
_cache_lock = threading.RLock()
logger = logging.getLogger(__name__)


def _load_cache(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


_cache: dict = _load_cache(CACHE_PATH)


def _save_cache():
    """Atomic replacement prevents interrupted/concurrent requests corrupting JSON."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=CACHE_PATH.parent,
                                         prefix="answer-cache-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(_cache, handle, allow_nan=False)
        os.replace(temporary, CACHE_PATH)
    except (OSError, ValueError):
        logger.warning("Answer cache could not be saved; the completed answer is still available.")
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    selected_lead: str | None = None
    audience: Literal["geoscientist", "executive"] | None = None
    hide_wells: list[str] | None = None  # explicitly rejected until independent exclusion is implemented


def _key(msg: str, lead: str | None, audience: str | None = None) -> str:
    knowledge = hashlib.sha256(b"".join(path.read_bytes() for path in sorted(config.KNOWLEDGE_DIR.glob("*.md")))).hexdigest()
    # Include data, wording rules and model settings; preserve signed coordinates.
    return json.dumps(["hpc-readiness-v2", store.revision, knowledge, agent.mode, config.LLM_BASE_URL,
                       config.LLM_MODEL, lead, audience or "geoscientist", msg.strip()], ensure_ascii=False)


@app.get("/api/health")
def health():
    return {"ok": True, "mock": config.MOCK, "synthetic": store.meta.get("synthetic"),
            "llm_mode": agent.mode, "llm_reachable": llm.reachable() if agent.mode == "gemma" else None,
            "cache": CACHE_ON, "cached_answers": len(_cache),
            "hide_wells": False,
            "blind_test_note": "Independent well exclusion is not implemented; blind-test requests are disabled.",
            "store_revision": store.revision, "score_note": store.meta["score_note"],
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
    if (inline is None) == (crossline is None):
        raise HTTPException(400, "give exactly one inline or crossline")
    try:
        image = section_png(store, inline=inline, crossline=crossline)
    except InvalidLocationError as e:
        raise HTTPException(400, str(e)) from e
    return Response(image, media_type="image/png")


@app.post("/api/chat")
def chat(body: ChatIn):
    message = body.message.strip()
    if not message:
        raise HTTPException(422, "give a nonempty question")
    if body.hide_wells or re.search(r"\bblind\s+(?:well\s+)?test\b", message, re.I):
        raise HTTPException(409, "Blind evaluation is unavailable: this backend cannot yet exclude all hidden-well evidence.")
    if body.selected_lead and not store.lead(body.selected_lead):
        raise HTTPException(400, f"unknown selected lead {body.selected_lead}")
    key = _key(message, body.selected_lead, body.audience)
    if body.audience == "executive":
        message += " (Answer for an asset manager in plain words. Treat screening scores as provisional, not success probabilities.)"

    def gen():
        with _cache_lock:
            cached = _cache.get(key) if CACHE_ON else None
        if cached:
            for ev in cached:
                if ev["type"] == "token":
                    time.sleep(0.012)
                yield f"data: {json.dumps({**ev, 'cached': True}, allow_nan=False)}\n\n"
            return
        events = []
        for ev in agent.stream(message, body.selected_lead):
            ev = json_safe(ev)
            events.append(ev)
            yield f"data: {json.dumps(ev, allow_nan=False)}\n\n"
        done = events[-1] if events else {}
        if CACHE_ON and done.get("type") == "done" and done.get("cacheable") and not done.get("unverified_numbers"):
            with _cache_lock:
                _cache[key] = events
                while len(_cache) > 128:
                    _cache.pop(next(iter(_cache)))
                _save_cache()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


FRONTEND = Path(config.ROOT) / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend")
