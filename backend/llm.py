"""Minimal client for the shared Gemma 4 endpoint (OpenAI-compatible vLLM).
Uses `requests` only, so nothing extra to install on the HPC."""
from __future__ import annotations

import json
from typing import Iterator

import requests

import config


class LLMError(RuntimeError):
    pass


def chat(messages: list[dict], temperature: float = 0.2, max_tokens: int = 400) -> str:
    try:
        r = requests.post(f"{config.LLM_BASE_URL}/chat/completions", timeout=config.LLM_TIMEOUT_S,
                          json={"model": config.LLM_MODEL, "messages": messages,
                                "temperature": temperature, "max_tokens": max_tokens})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"] or ""
    except Exception as e:
        raise LLMError(str(e)) from e


def stream(messages: list[dict], temperature: float = 0.3, max_tokens: int = 900) -> Iterator[str]:
    try:
        with requests.post(f"{config.LLM_BASE_URL}/chat/completions", stream=True,
                           timeout=config.LLM_TIMEOUT_S,
                           json={"model": config.LLM_MODEL, "messages": messages, "stream": True,
                                 "temperature": temperature, "max_tokens": max_tokens}) as r:
            r.raise_for_status()
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                if delta:
                    yield delta
    except Exception as e:
        raise LLMError(str(e)) from e


def reachable() -> bool:
    try:
        return requests.get(f"{config.LLM_BASE_URL}/models", timeout=3).ok
    except Exception:
        return False


def parse_json(text: str) -> dict | None:
    """Pull the first {...} object out of a model reply (tolerates code fences)."""
    start = text.find("{")
    while start != -1:
        depth = 0
        for k in range(start, len(text)):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:k + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None
