"""Mechanical checks for model-written answers, not a geological correctness test."""
from __future__ import annotations

import math
import re

CITATION = re.compile(r"\[(E\d+)\]")
NUMBER = re.compile(r"(?<![A-Za-z\d.])[-+]?\d+(?:,\d{3})*(?:\.\d+)?")


def _numbers(value):
    if isinstance(value, dict):
        return [n for item in value.values() for n in _numbers(item)]
    if isinstance(value, (list, tuple)):
        return [n for item in value for n in _numbers(item)]
    if value is None or isinstance(value, bool):
        return []
    return [float(m.group().replace(",", "")) for m in NUMBER.finditer(str(value))]


def check_answer(text: str, evidence: list[dict], wells: list[dict]) -> list[str]:
    issues = []
    if not text.strip():
        return ["empty answer"]
    by_id = {item["id"]: item for item in evidence}
    cited = set(CITATION.findall(text))
    if cited - by_id.keys():
        issues.append("unknown evidence citation")
    if evidence and not cited:
        issues.append("answer has no evidence citations")

    # A number must be supported by evidence cited on that line, with its sign intact.
    for line in text.replace("−", "-").splitlines():
        clean = CITATION.sub("", line)
        clean = re.sub(r"^\s*\d+[.)]\s+|\bL\d+\b|\b[234]D\b|\b4-way\b", "", clean)
        for well in wells:
            clean = re.sub(re.escape(well["name"]), "", clean, flags=re.I)
        pool = [number for key in CITATION.findall(line) if key in by_id
                for field in ("value", "compare") for number in _numbers(by_id[key].get(field))]
        for match in NUMBER.finditer(clean):
            number = float(match.group().replace(",", ""))
            decimals = len(match.group().split(".")[1]) if "." in match.group() else 0
            candidates = pool
            if clean[match.end():].lstrip().startswith("%"):
                candidates = [value * 100 for value in pool]
            if not any(math.isclose(number, value, abs_tol=1e-8) or
                       math.isclose(number, round(value, decimals), abs_tol=1e-8) for value in candidates):
                issues.append("number is not supported by its cited evidence")
                break

    for well in wells:
        if well.get("result") != "unknown":
            continue
        clauses = re.findall(re.escape(well["name"]) + r"[^.\n]*", text, re.I)
        for clause in clauses:
            if re.search(r"\b(dry|failed|failure|discovery|succeeded|successful|proven)\b", clause, re.I) and not re.search(
                    r"unknown|unavailable|unconfirmed|not known|not established|cannot|can't", clause, re.I):
                issues.append("unknown well outcome presented as confirmed")
    return list(dict.fromkeys(issues))
