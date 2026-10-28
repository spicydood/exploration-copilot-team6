"""Readers for SEG-Y volumes, LAS logs, deviation files and the well list.

Every reader returns plain numpy / pandas objects so the rest of the engine
never touches file formats. Uses segyio and lasio when installed (they are on
pip and work on the HPC); LAS and deviation files also have a small built-in
parser as a fallback.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- paths
def resolve(base: Path, rel: str) -> Path:
    """Find base/rel matching folder and file names case-insensitively."""
    p = Path(base)
    for part in Path(rel).parts:
        exact = p / part
        if exact.exists():
            p = exact
            continue
        hits = [c for c in p.iterdir()] if p.is_dir() else []
        match = [c for c in hits if c.name.lower() == part.lower()]
        if not match:
            raise FileNotFoundError(f"{part!r} not found in {p}")
        p = match[0]
    return p


# --------------------------------------------------------------------------- seismic
@dataclass
class Volume:
    """A 3D seismic volume on a regular inline/crossline grid."""
    data: np.ndarray          # (n_il, n_xl, n_t) float32, NaN where no trace
    ilines: np.ndarray        # (n_il,)
    xlines: np.ndarray        # (n_xl,)
    times: np.ndarray         # (n_t,) ms (or depth units if the volume is in depth)
    cdp_x: np.ndarray         # (n_il, n_xl) map coordinates, NaN where no trace
    cdp_y: np.ndarray

    def window_index(self, t0: float, t1: float) -> slice:
        i0 = int(np.searchsorted(self.times, t0))
        i1 = int(np.searchsorted(self.times, t1, side="right"))
        return slice(max(i0, 0), min(i1, len(self.times)))


def _scale_coords(raw: np.ndarray, scalar: np.ndarray) -> np.ndarray:
    raw = raw.astype(np.float64)
    s = scalar.astype(np.float64)
    out = raw.copy()
    neg, pos = s < 0, s > 0
    out[neg] = raw[neg] / np.abs(s[neg])
    out[pos] = raw[pos] * s[pos]
    return out


def read_segy(path: Path, iline_byte: int = 189, xline_byte: int = 193) -> Volume:
    """Read a (possibly cropped / irregular) 3D SEG-Y into a regular grid.

    Builds the grid from the inline/crossline trace headers, so it works even
    when segyio's own geometry inference fails on cropped volumes.
    """
    import segyio  # imported here so MOCK mode works without it

    with segyio.open(str(path), "r", ignore_geometry=True) as f:
        f.mmap()
        il = np.asarray(f.attributes(iline_byte)[:])
        xl = np.asarray(f.attributes(xline_byte)[:])
        cx = np.asarray(f.attributes(segyio.TraceField.CDP_X)[:])
        cy = np.asarray(f.attributes(segyio.TraceField.CDP_Y)[:])
        sc = np.asarray(f.attributes(segyio.TraceField.SourceGroupScalar)[:])
        traces = f.trace.raw[:].astype(np.float32)          # (n_traces, n_t)
        times = np.asarray(f.samples, dtype=np.float64)

    ilines, ii = np.unique(il, return_inverse=True)
    xlines, jj = np.unique(xl, return_inverse=True)
    data = np.full((len(ilines), len(xlines), traces.shape[1]), np.nan, np.float32)
    data[ii, jj, :] = traces
    x = np.full((len(ilines), len(xlines)), np.nan)
    y = np.full_like(x, np.nan)
    x[ii, jj] = _scale_coords(cx, sc)
    y[ii, jj] = _scale_coords(cy, sc)
    return Volume(data, ilines, xlines, times, x, y)


# --------------------------------------------------------------------------- wells
def read_las(path: Path) -> tuple[pd.DataFrame, dict]:
    """Return (curves DataFrame indexed by depth, header dict)."""
    try:
        import lasio
        las = lasio.read(str(path))
        df = las.df()
        header = {item.mnemonic: str(item.value) for item in las.well}
        units = {c.mnemonic: c.unit for c in las.curves}
        header["_units"] = units
        return df, header
    except ImportError:
        return _read_las_simple(path)


def _read_las_simple(path: Path) -> tuple[pd.DataFrame, dict]:
    """Minimal LAS 2.0 reader (used only when lasio is not installed)."""
    section, header, curves, units, rows = None, {}, [], {}, []
    null = -999.25
    for line in Path(path).read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("~"):
            section = s[1].upper()
            continue
        if section in ("W", "C"):
            m = re.match(r"([^.\s]+)\s*\.(\S*)\s*(.*?):\s*(.*)", s)
            if not m:
                continue
            mnem, unit, value, _desc = m.groups()
            if section == "W":
                header[mnem] = value.strip()
                if mnem.upper() == "NULL":
                    try:
                        null = float(value)
                    except ValueError:
                        pass
            else:
                curves.append(mnem)
                units[mnem] = unit
        elif section == "A":
            rows.extend(float(v) for v in s.split())
    n = len(curves)
    arr = np.array(rows[: len(rows) // n * n], dtype=float).reshape(-1, n)
    arr[np.isclose(arr, null)] = np.nan
    df = pd.DataFrame(arr[:, 1:], index=arr[:, 0], columns=curves[1:])
    df.index.name = curves[0]
    header["_units"] = units
    return df, header


def read_table_txt(path: Path) -> pd.DataFrame:
    """Read a whitespace/CSV text table with a header line (deviation, markers)."""
    text = Path(path).read_text(errors="ignore").splitlines()
    # first line that looks like a header (mostly letters) followed by numeric rows
    start = 0
    for i, line in enumerate(text):
        toks = re.split(r"[,\t ]+", line.strip())
        if len(toks) >= 2 and sum(t.replace(".", "", 1).replace("-", "", 1).isdigit()
                                  for t in toks) == 0:
            start = i
            break
    sep = "," if "," in text[start] else r"\s+"
    return pd.read_csv(path, sep=sep, skiprows=start, engine="python",
                       comment="#").dropna(how="all")


def find_col(df: pd.DataFrame, *keys: str) -> str | None:
    """First column whose name contains any key (case-insensitive)."""
    for k in keys:
        for c in df.columns:
            if k.lower() in str(c).lower():
                return c
    return None


def read_well_list(path: Path) -> pd.DataFrame:
    """Well list spreadsheet -> DataFrame with lower-case column names kept."""
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df
