"""Conservative outcome labels shared by ingestion and existing saved stores.

Free-form notes are not geological outcome labels. Ruthan can supply canonical
discovery/dry/unknown values through well_results.csv when a label is ambiguous.
"""
from __future__ import annotations

import math
import re


DISCOVERY = {"discovery", "gas discovery", "oil discovery", "hydrocarbon discovery",
             "oil and gas discovery", "oil", "gas", "oil/gas", "oil and gas", "hydrocarbon"}
DRY = {"dry", "dry hole", "dry well", "water", "water wet", "water-wet", "water bearing", "water-bearing",
       "dry - water-wet sand", "dry - no reservoir"}


def classify_result(text) -> str:
    if text is None or isinstance(text, float) and not math.isfinite(text):
        return "unknown"
    label = re.sub(r"\s+", " ", str(text).strip().lower()).rstrip(".")
    if label in DISCOVERY:
        return "discovery"
    if label in DRY:
        return "dry"
    return "unknown"


def well_outcome(well: dict) -> str:
    text = well.get("result_text")
    # A nonempty source label takes precedence over a previously inferred result.
    source = text if text is not None and str(text).strip() else well.get("result")
    return classify_result(source)
