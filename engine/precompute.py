"""Run once (CPU is fine): read volumes + wells, build maps, find leads,
calibrate at wells, and write everything the app needs into STORE_DIR.

    # on the HPC, reservoir window chosen by Ruthan (ms):
    python -m engine.precompute --t0 2250 --t1 2350
    # on a laptop, synthetic survey:
    MOCK=1 python -m engine.precompute
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from engine import attributes as A  # noqa: E402
from engine import io, leads as L, wells as W  # noqa: E402

MAP_STYLE = {   # name: (label, unit, colormap, higher-is-better-for-hydrocarbons?)
    "sand":     ("Sand probability (max in window)", "0-1", "inferno", True),
    "vpvs":     ("Vp/Vs (min in window)", "ratio", "viridis_r", False),
    "pimp":     ("P-impedance (min in window)", "inversion units", "cividis_r", False),
    "avo_diff": ("Far minus Near RMS amplitude", "amplitude", "RdBu_r", True),
    "rms_full": ("Full-stack RMS amplitude", "amplitude", "magma", True),
    "disc":     ("Discontinuity (faults)", "0-1", "Greys", True),
    "top_time": ("Top-sand time (structure)", "ms", "terrain", False),
}


def build_maps(v: dict[str, io.Volume], t0: float, t1: float, top_thr: float | None) -> dict:
    ref = v["sand_prob"]
    sl = ref.window_index(t0, t1)
    maps = {
        # thin reservoirs: take the extreme value in the window, not the mean
        "sand": A.window_max(v["sand_prob"].data, sl),
        "vpvs": A.window_min(v["vpvs"].data, sl),
        "pimp": A.window_min(v["pimp"].data, sl),
        "rms_full": A.window_rms(v["full"].data, sl),
        # faults cut the whole section: measure over a longer window so thin
        # channel edges inside the reservoir do not look like faults
        "disc": A.discontinuity(v["full"].data, ref.window_index(t0 - 150, t1 + 150)),
    }
    maps.update(A.avo_maps(v["near"].data, v["far"].data, sl))
    maps.pop("avo_ratio", None)
    thr = top_thr if top_thr is not None else L.sand_threshold(maps["sand"])
    maps["top_time"] = A.top_time_map(v["sand_prob"].data, ref.times, sl, thr)
    return maps


def bin_area(v: io.Volume) -> float:
    dx = np.nanmedian(np.hypot(np.diff(v.cdp_x, axis=0), np.diff(v.cdp_y, axis=0)))
    dy = np.nanmedian(np.hypot(np.diff(v.cdp_x, axis=1), np.diff(v.cdp_y, axis=1)))
    return float(dx * dy) if np.isfinite(dx * dy) and dx * dy > 0 else 625.0


def render_map(a: np.ndarray, cmap: str, path: Path, contours: np.ndarray | None = None) -> tuple[float, float]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    lo, hi = np.nanpercentile(a, [2, 98])
    if cmap == "RdBu_r":
        m = max(abs(lo), abs(hi)); lo, hi = -m, m
    h, w = a.shape
    scale = max(1, int(round(900 / max(h, w))))
    fig = plt.figure(figsize=(w * scale / 100, h * scale / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.imshow(a, cmap=cmap, vmin=lo, vmax=hi, interpolation="nearest", aspect="auto")
    if contours is not None:
        cs = A.fill_nan(contours)
        ax.contour(cs, levels=12, colors="k", linewidths=0.4, alpha=0.6)
    fig.savefig(path, dpi=100); plt.close(fig)
    return float(lo), float(hi)


def horizon_to_grid(path: Path, v: io.Volume) -> np.ndarray:
    """Grid an exported horizon (text: X Y TIME columns, e.g. from DUG Insight)
    onto the seismic bins. Replaces the sand-based pseudo-horizon."""
    from scipy.spatial import cKDTree
    d = io.read_table_txt(path)
    cols = list(d.columns)
    xc = io.find_col(d, "x") or cols[0]
    yc = io.find_col(d, "y") or cols[1]
    zc = io.find_col(d, "time", "twt", "z") or cols[2]
    pts = np.c_[d[xc].astype(float), d[yc].astype(float)]
    tree = cKDTree(pts)
    ok = np.isfinite(v.cdp_x)
    dist, k = tree.query(np.c_[v.cdp_x[ok], v.cdp_y[ok]])
    out = np.full(v.cdp_x.shape, np.nan)
    out[ok] = np.where(dist < 60, d[zc].astype(float).values[k], np.nan)
    return out


def run(vols: dict[str, io.Volume], data_dir: Path, out: Path, t0: float, t1: float,
        params: L.Params, results_csv: Path | None, synthetic: bool,
        horizon: Path | None = None) -> dict:
    t = time.time()
    out = Path(out).resolve()
    source = Path(data_dir).resolve()
    if out == source or out in source.parents or source in out.parents:
        raise ValueError("The output store must be separate from the input data directory.")
    if out.exists():
        raise FileExistsError(f"Output store already exists: {out}. Choose a new --out directory; existing stores are never deleted.")
    if not np.isfinite(t0) or not np.isfinite(t1) or t0 >= t1:
        raise ValueError("The reservoir window must have finite start and end times with start < end.")
    ref = vols["sand_prob"]
    for name, volume in vols.items():
        if volume.data.shape != ref.data.shape or not all(np.array_equal(getattr(volume, axis), getattr(ref, axis))
                                                         for axis in ("ilines", "xlines", "times")):
            raise ValueError(f"Volume {name} does not share the reference grid and samples. Align inputs before processing.")
        if not (np.allclose(volume.cdp_x, ref.cdp_x, rtol=0, atol=0.001, equal_nan=True) and
                np.allclose(volume.cdp_y, ref.cdp_y, rtol=0, atol=0.001, equal_nan=True)):
            raise ValueError(f"Volume {name} has different map coordinates. Verify coordinate units and alignment.")
    if t0 < ref.times[0] or t1 > ref.times[-1]:
        raise ValueError("The requested reservoir window extends outside the available samples.")
    window = ref.window_index(t0, t1)
    if window.start >= window.stop:
        raise ValueError("The requested window contains no samples.")

    ref = vols["sand_prob"]
    maps = build_maps(vols, t0, t1, params.sand_threshold)
    valid_sand = maps["sand"][np.isfinite(maps["sand"])]
    if not len(valid_sand) or valid_sand.min() < 0 or valid_sand.max() > 1:
        raise ValueError("Sand probability must contain finite values on a 0 to 1 scale; verify null values and units.")
    if horizon:
        maps["top_time"] = horizon_to_grid(horizon, ref)
    params.bin_area_m2 = bin_area(ref)
    wells = W.load_wells(data_dir, ref.cdp_x, ref.cdp_y, results_csv)
    calib = W.calibrate(wells, maps)
    found = L.detect(maps, wells, params)

    (out / "maps").mkdir(parents=True)
    (out / "cubes").mkdir()
    meta_maps = {}
    for k, a in maps.items():
        np.save(out / "maps" / f"{k}.npy", a.astype(np.float32))
        label, unit, cmap, up = MAP_STYLE[k]
        lo, hi = render_map(a, cmap, out / "maps" / f"{k}.png",
                            contours=maps["top_time"] if k in ("sand", "top_time") else None)
        meta_maps[k] = {"label": label, "unit": unit, "cmap": cmap, "vmin": lo, "vmax": hi,
                        "higher_is_better": up}

    # cubes for section views: a padded window around the reservoir, float16
    pad = 150.0
    sl = ref.window_index(t0 - pad, t1 + pad)
    np.save(out / "cubes" / "full.npy", vols["full"].data[:, :, sl].astype(np.float16))
    np.save(out / "cubes" / "sand_prob.npy", vols["sand_prob"].data[:, :, sl].astype(np.float16))
    np.save(out / "cubes" / "times.npy", ref.times[sl])

    for d in found:
        d.pop("_pixels", None)
    meta = {
        "synthetic": synthetic, "built": time.strftime("%Y-%m-%d %H:%M"),
        "window_ms": [t0, t1], "shape": list(ref.data.shape[:2]),
        "ilines": [int(ref.ilines[0]), int(ref.ilines[-1])],
        "xlines": [int(ref.xlines[0]), int(ref.xlines[-1])],
        "il_values": [int(x) for x in ref.ilines], "xl_values": [int(x) for x in ref.xlines],
        "bin_area_m2": round(params.bin_area_m2, 1),
        "sand_threshold": round(params.sand_threshold if params.sand_threshold is not None else L.sand_threshold(maps["sand"]), 3),
        "maps": meta_maps, "n_leads": len(found), "n_wells": len(wells),
        "calibration": calib,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2))
    (out / "wells.json").write_text(json.dumps(wells, indent=2, default=float))
    (out / "leads.json").write_text(json.dumps(found, indent=2, default=float))
    print(f"store written to {out} in {time.time() - t:.1f}s: "
          f"{len(found)} leads, {len(wells)} wells, maps={list(maps)}")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--t0", type=float, help="reservoir window start (ms)")
    ap.add_argument("--t1", type=float, help="reservoir window end (ms)")
    ap.add_argument("--sand-threshold", type=float, default=None)
    ap.add_argument("--min-area-px", type=int, default=40)
    ap.add_argument("--results-csv", default=str(config.ROOT / "data" / "well_results.csv"))
    ap.add_argument("--out", default=str(config.STORE_DIR))
    ap.add_argument("--horizon", default=None,
                    help="optional X Y TIME text export of the reservoir-top horizon")
    a = ap.parse_args(argv)
    params = L.Params(sand_threshold=a.sand_threshold, min_area_px=a.min_area_px)

    if config.MOCK:
        from engine import mock_data
        vols, _ = mock_data.build()
        data_dir = mock_data.write_well_files(config.ROOT / "store_mock_input")
        t0 = a.t0 if a.t0 is not None else 1930.0
        t1 = a.t1 if a.t1 is not None else 2080.0
        return run(vols, data_dir, Path(a.out), t0, t1, params, None, synthetic=True)

    if a.t0 is None or a.t1 is None:
        ap.error("--t0 and --t1 are required on real data (ask Ruthan for the reservoir window)")
    vols = {}
    for name, rel in config.VOLUMES.items():
        p = io.resolve(config.DATA_DIR, rel)
        print(f"reading {name}: {p.name}", flush=True)
        vols[name] = io.read_segy(p, config.ILINE_BYTE, config.XLINE_BYTE)
    rc = Path(a.results_csv)
    return run(vols, config.DATA_DIR, Path(a.out), a.t0, a.t1, params,
               rc if rc.exists() else None, synthetic=False,
               horizon=Path(a.horizon) if a.horizon else None)


if __name__ == "__main__":
    main()
