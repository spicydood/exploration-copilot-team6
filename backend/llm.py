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
            complete = False
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    complete = True
                    break
                choices = json.loads(data).get("choices", [])
                if not choices:  # optional usage-only chunk
                    continue
                if choices[0].get("finish_reason") in ("length", "content_filter"):
                    raise LLMError("The model did not finish its answer.")
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    if not isinstance(delta, str):
                        raise LLMError("The model returned invalid text content.")
                    yield delta
            if not complete:
                raise LLMError("The model stream ended before its completion marker.")
    except Exception as e:
        raise LLMError(str(e)) from e


def reachable() -> bool:
    try:
        return requests.get(f"{config.LLM_BASE_URL}/models", timeout=3).ok
    except Exception:
        return False


def parse_json(text: str) -> dict | None:
    """Pull the first {...} object out of a model reply (tolerates code fences)."""
    for start, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None
