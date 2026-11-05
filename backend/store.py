"""Read-only access to what engine/precompute.py wrote."""
from __future__ import annotations

import json
import hashlib
from functools import cached_property
from pathlib import Path

import numpy as np
from engine.outcomes import well_outcome


SCORE_NOTE = "Provisional screening score from fixed rules; not a calibrated probability of success."


def json_safe(value):
    """Keep missing numeric measurements null in API JSON, never NaN/Infinity."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    return value


class InvalidLocationError(ValueError):
    """The requested location has no exact cell in this survey."""


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        if not (self.root / "meta.json").exists():
            raise FileNotFoundError(
                f"No precomputed store at {self.root}. Run: python -m engine.precompute "
                "(add MOCK=1 on a laptop).")
        self.meta = json_safe(json.loads((self.root / "meta.json").read_text(encoding="utf-8")))
        self.wells = json_safe(json.loads((self.root / "wells.json").read_text(encoding="utf-8")))
        self.leads = json_safe(json.loads((self.root / "leads.json").read_text(encoding="utf-8")))
        for well in self.wells:
            well["result"] = well_outcome(well)
        # Rebuild outcome-dependent summaries from confirmed labels, including older stores.
        calibration = {}
        for outcome in ("discovery", "dry"):
            selected = [w for w in self.wells if w["result"] == outcome
                        and w.get("inside_survey", True) and w.get("attributes_at_well")]
            if not selected:
                continue
            values = {}
            keys = set().union(*(w["attributes_at_well"] for w in selected))
            for key in keys:
                measured = [w["attributes_at_well"].get(key) for w in selected]
                measured = [v for v in measured if isinstance(v, (int, float)) and np.isfinite(v)]
                if measured:
                    values[key] = round(float(np.mean(measured)), 3)
            calibration[outcome] = {**values, "n_wells": len(selected)}
        self.meta["calibration"] = calibration
        self.meta["score_basis"] = "heuristic_unvalidated"
        self.meta["score_note"] = SCORE_NOTE
        for lead in self.leads:
            lead["score_basis"] = "heuristic_unvalidated"
            lead["score_note"] = SCORE_NOTE
        content = json.dumps([self.meta, self.wells, self.leads], sort_keys=True, allow_nan=False)
        self.revision = hashlib.sha256(content.encode()).hexdigest()
        self._maps: dict[str, np.ndarray] = {}

    # ---------- lookups
    def lead(self, lead_id: str) -> dict | None:
        lid = str(lead_id).strip().upper()
        return next((d for d in self.leads if d["id"] == lid), None)

    def well(self, name: str) -> dict | None:
        n = str(name).strip().lower()
        return next((w for w in self.wells if w["name"] == n), None)

    def lead_of_well(self, name: str) -> dict | None:
        n = str(name).strip().lower()
        return next((d for d in self.leads if n in d["wells_inside"]), None)

    def map(self, name: str) -> np.ndarray:
        if name not in self._maps:
            self._maps[name] = np.load(self.root / "maps" / f"{name}.npy")
        return self._maps[name]

    def map_png(self, name: str) -> Path:
        return self.root / "maps" / f"{name}.png"

    @cached_property
    def cube_full(self) -> np.ndarray:
        return np.load(self.root / "cubes" / "full.npy", mmap_mode="r")

    @cached_property
    def cube_sand(self) -> np.ndarray:
        return np.load(self.root / "cubes" / "sand_prob.npy", mmap_mode="r")

    @cached_property
    def cube_times(self) -> np.ndarray:
        return np.load(self.root / "cubes" / "times.npy")

    # ---------- grid helpers
    def _grid_index(self, value, axis: str) -> int:
        values = np.asarray(self.meta[f"{axis}_values"])
        label = "inline" if axis == "il" else "crossline"
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            number = np.nan
        if isinstance(value, (bool, np.bool_)) or not np.isfinite(number) or not number.is_integer():
            raise InvalidLocationError(f"Invalid {label} {value!r}; give a whole-number survey coordinate.")
        number = int(number)
        if not len(values):
            raise InvalidLocationError(f"No {label} coordinates are available in this survey.")
        if number < values[0] or number > values[-1]:
            raise InvalidLocationError(
                f"The requested {label} {number} is outside the survey "
                f"(valid range {values[0]} to {values[-1]}).")
        index = int(np.searchsorted(values, number))
        if index >= len(values) or values[index] != number:
            raise InvalidLocationError(f"The requested {label} {number} is not present in the survey grid.")
        return index

    def il_index(self, inline: int) -> int:
        return self._grid_index(inline, "il")

    def xl_index(self, xline: int) -> int:
        return self._grid_index(xline, "xl")

    def il_number(self, i: int) -> int:
        return int(self.meta["il_values"][int(round(i))])

    def xl_number(self, j: int) -> int:
        return int(self.meta["xl_values"][int(round(j))])

    def lead_at(self, i: int, j: int) -> dict | None:
        from matplotlib.path import Path as MPath
        for d in self.leads:
            if MPath(np.array(d["polygon"])).contains_point((i, j)):
                return d
        return None
