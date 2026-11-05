"""Check the Challenge 1 data before the first real precompute. Run on the HPC.

    python scripts/check_real_data.py

Reads trace headers (fast), a sample of the sand-probability traces and the well
files, then prints:
  1. every volume: found, time range, inline/crossline range, same grid as the rest
  2. every well: placed inside the survey or not, and its result (discovery/dry/unknown)
  3. a PROVISIONAL reservoir window from the sand-probability volume, to run the
     engine today; Ruthan confirms or replaces it from DUG Insight
  4. the exact precompute command to run next

Prints summaries only. Nothing is written or copied anywhere.
Set COPILOT_DATA_DIR to point it at another folder (e.g. the fake survey).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from engine import io, wells as W  # noqa: E402

OK, WARN, FAIL = "ok  ", "WARN", "FAIL"
problems: list[str] = []

# Byte pairs seen in the wild for inline / crossline, tried when 189/193 look wrong.
BYTE_PAIRS = [(189, 193), (9, 21), (5, 21), (9, 13), (17, 13), (13, 17), (221, 225), (233, 237)]


def say(tag: str, msg: str) -> None:
    print(f"  [{tag}] {msg}")
    if tag != OK:
        problems.append(msg)


def headers(path: Path, ib: int, xb: int):
    import segyio
    with segyio.open(str(path), "r", ignore_geometry=True) as f:
        il = np.asarray(f.attributes(ib)[:])
        xl = np.asarray(f.attributes(xb)[:])
        return il, xl, np.asarray(f.samples, float), f.tracecount


def grid_fill(il, xl) -> tuple[int, int, float]:
    n_il, n_xl = len(np.unique(il)), len(np.unique(xl))
    return n_il, n_xl, len(il) / max(n_il * n_xl, 1)


def best_bytes(path: Path):
    """Pair whose inline x crossline grid best explains the trace count."""
    best = None
    for ib, xb in BYTE_PAIRS:
        try:
            il, xl, _, _ = headers(path, ib, xb)
        except Exception:
            continue
        n_il, n_xl, fill = grid_fill(il, xl)
        if n_il < 2 or n_xl < 2 or fill > 1.0001:
            continue
        score = fill * min(n_il, n_xl)
        if best is None or score > best[0]:
            best = (score, ib, xb, n_il, n_xl, fill)
    return best


# --------------------------------------------------------------------------- 1. volumes
def check_volumes():
    print(f"\n1. Seismic volumes in {config.DATA_DIR}")
    ref = None
    found = {}
    for name, rel in config.VOLUMES.items():
        try:
            p = io.resolve(config.DATA_DIR, rel)
        except FileNotFoundError:
            say(FAIL, f"{name}: missing {rel}")
            continue
        try:
            il, xl, t, n = headers(p, config.ILINE_BYTE, config.XLINE_BYTE)
        except Exception as e:
            say(FAIL, f"{name}: segyio could not open it ({e})")
            continue
        n_il, n_xl, fill = grid_fill(il, xl)
        gb = p.stat().st_size / 1e9
        line = (f"{name:9s} {gb:5.1f} GB  t {t[0]:.0f}-{t[-1]:.0f} ms every {t[1]-t[0]:g}  "
                f"IL {il.min()}-{il.max()} ({n_il})  XL {xl.min()}-{xl.max()} ({n_xl})  fill {fill:.0%}")
        if n_il < 2 or n_xl < 2 or fill > 1.0001:
            say(FAIL, line + f"  <- bytes {config.ILINE_BYTE}/{config.XLINE_BYTE} do not hold IL/XL")
            b = best_bytes(p)
            if b:
                print(f"         try: export COPILOT_ILINE_BYTE={b[1]} COPILOT_XLINE_BYTE={b[2]}"
                      f"  (gives {b[3]} x {b[4]}, fill {b[5]:.0%})")
            continue
        sig = (il.min(), il.max(), xl.min(), xl.max(), len(t), t[0])
        if ref is None:
            ref = (name, sig)
        tag = OK if sig == ref[1] else WARN
        say(tag, line + ("" if tag == OK else f"  <- grid differs from {ref[0]}"))
        found[name] = p
    return found


# --------------------------------------------------------------------------- 2. wells
def survey_coords(path: Path):
    """cdp_x / cdp_y grid from trace headers only (same maths as io.read_segy)."""
    import segyio
    with segyio.open(str(path), "r", ignore_geometry=True) as f:
        il = np.asarray(f.attributes(config.ILINE_BYTE)[:])
        xl = np.asarray(f.attributes(config.XLINE_BYTE)[:])
        cx = np.asarray(f.attributes(segyio.TraceField.CDP_X)[:])
        cy = np.asarray(f.attributes(segyio.TraceField.CDP_Y)[:])
        sc = np.asarray(f.attributes(segyio.TraceField.SourceGroupScalar)[:])
    ilines, ii = np.unique(il, return_inverse=True)
    xlines, jj = np.unique(xl, return_inverse=True)
    x = np.full((len(ilines), len(xlines)), np.nan)
    y = np.full_like(x, np.nan)
    x[ii, jj] = io._scale_coords(cx, sc)
    y[ii, jj] = io._scale_coords(cy, sc)
    trace_of = np.full(x.shape, -1, int)
    trace_of[ii, jj] = np.arange(len(il))
    return x, y, ilines, xlines, trace_of


def check_wells(found):
    print("\n2. Wells")
    if "full" not in found:
        say(FAIL, "full stack unreadable, cannot place wells")
        return [], None
    x, y, ilines, xlines, trace_of = survey_coords(found["full"])
    print(f"  survey X {np.nanmin(x):.0f}-{np.nanmax(x):.0f}  Y {np.nanmin(y):.0f}-{np.nanmax(y):.0f}")
    if np.nanmax(x) - np.nanmin(x) < 1:
        say(FAIL, "trace headers carry no CDP X/Y, wells cannot be placed")
    rc = config.ROOT / "data" / "well_results.csv"
    wl = W.load_wells(config.DATA_DIR, x, y, rc if rc.exists() else None)
    for w in wl:
        if w.get("i") is None:
            say(FAIL, f"{w['name']:10s} no X/Y found in well list, deviation or LAS header")
            continue
        where = (f"IL {ilines[w['i']]} XL {xlines[w['j']]}  {w['grid_distance_m']:.0f} m from nearest trace  "
                 f"well X {w['x']:.0f} Y {w['y']:.0f}")
        tag = OK if w.get("inside_survey") else WARN
        say(tag, f"{w['name']:10s} {w['result']:9s} {where}"
                 + ("" if tag == OK else "  <- outside the survey"))
    counts = {r: sum(w["result"] == r for w in wl) for r in ("discovery", "dry", "unknown")}
    print(f"  results: {counts['discovery']} discovery, {counts['dry']} dry, {counts['unknown']} unknown")
    if counts["unknown"]:
        say(WARN, f"{counts['unknown']} wells have no result: copy data/well_results.example.csv "
                  "to data/well_results.csv and fill it in")
    return wl, (trace_of, ilines, xlines)


# --------------------------------------------------------------------------- 3. window
def suggest_window(found, wl, grid):
    print("\n3. Provisional reservoir window (from sand probability)")
    p = found.get("sand_prob")
    if p is None:
        say(FAIL, "sand probability volume unreadable")
        return None
    import segyio
    with segyio.open(str(p), "r", ignore_geometry=True) as f:
        t = np.asarray(f.samples, float)
        step = max(1, f.tracecount // 4000)
        sample = np.asarray(f.trace.raw[::step], np.float32)
        at_wells = []
        if grid is not None:
            trace_of = grid[0]
            for w in wl:
                if w.get("i") is not None and w.get("inside_survey"):
                    k = trace_of[w["i"], w["j"]]
                    if k >= 0:
                        at_wells.append(np.asarray(f.trace.raw[int(k)], np.float32))
    scale = 100.0 if np.nanmax(sample) > 1.5 else 1.0
    sand = sample / scale > 0.5
    frac = sand.mean(axis=0)
    wells_frac = (np.asarray(at_wells) / scale > 0.5).mean(axis=0) if at_wells else None
    if frac.max() == 0:
        say(WARN, "no sample above 0.5 sand probability; pick the window in DUG Insight")
        return None

    # text profile in ~20 bins across the time range
    nb = 20
    edges = np.linspace(0, len(t), nb + 1).astype(int)
    print(f"  share of traces with sand prob > 0.5 (survey sample of {len(sample)} traces"
          + (f", {len(at_wells)} wells" if at_wells else "") + ")")
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        v = frac[a:b].mean()
        bar = "#" * int(round(v / frac.max() * 30))
        wv = f"  wells {wells_frac[a:b].mean():4.0%}" if wells_frac is not None else ""
        print(f"  {t[a]:7.0f}-{t[b-1]:<7.0f} {v:5.1%} {bar:30s}{wv}")

    peak = int(np.argmax(frac))
    keep = frac >= 0.5 * frac[peak]
    lo = hi = peak
    while lo > 0 and keep[lo - 1]:
        lo -= 1
    while hi < len(t) - 1 and keep[hi + 1]:
        hi += 1
    t0, t1 = t[lo] - 20, t[hi] + 20
    if t1 - t0 < 80:
        mid = (t0 + t1) / 2
        t0, t1 = mid - 40, mid + 40
    if t1 - t0 > 250:
        t0, t1 = t[peak] - 125, t[peak] + 125
    t0, t1 = max(t0, t[0]), min(t1, t[-1])
    print(f"  sand peaks at {t[peak]:.0f} ms -> provisional window {t0:.0f} to {t1:.0f} ms")
    print("  This is a first guess from one attribute. Ruthan should check it on an inline in DUG Insight.")
    return round(t0), round(t1)


def main():
    try:
        import segyio  # noqa: F401
    except ImportError:
        print("segyio is not installed: pip install -r requirements.txt")
        return 2
    found = check_volumes()
    wl, grid = check_wells(found)
    win = suggest_window(found, wl, grid)

    print("\n4. Next")
    store = os.environ.get("COPILOT_STORE_DIR", "/data/epic20/APGCE/<team>/copilot_store")
    t0, t1 = win if win else ("<start_ms>", "<end_ms>")
    print(f"  export COPILOT_STORE_DIR={store}")
    print(f"  python -m engine.precompute --t0 {t0} --t1 {t1}")
    print("  uvicorn backend.app:app --host 127.0.0.1 --port 8800")
    hard = any(m.startswith(("full", "segyio")) or "missing" in m or "bytes" in m for m in problems)
    print(f"\n{len(problems)} issue(s) found." if problems else "\nAll checks passed.")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
