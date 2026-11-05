"""Load the 13 Challenge 1 wells, place them on the seismic grid, summarise
their logs and calibrate the seismic attributes against well results."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from . import io
from .outcomes import classify_result

GR_KEYS = ("GR",)
RES_KEYS = ("RES", "RT", "ILD", "LLD", "RD", "AT90", "RDEP")
DEN_KEYS = ("RHOB", "DEN", "RHOZ")
NEU_KEYS = ("NPHI", "NEU", "TNPH")
SON_KEYS = ("DTC", "DT", "SON")
def _curve(df, keys):
    for k in keys:
        for c in df.columns:
            if str(c).upper().startswith(k):
                return c
    return None


def log_summary(df) -> dict:
    out = {"curves": [str(c) for c in df.columns],
           "depth_range": [float(np.nanmin(df.index)), float(np.nanmax(df.index))]}
    gr = _curve(df, GR_KEYS)
    res = _curve(df, RES_KEYS)
    if gr:
        g = df[gr].astype(float)
        cut = float(np.nanpercentile(g, 30))
        sandy = g < cut
        out["gr_median"] = round(float(np.nanmedian(g)), 1)
        out["gr_sand_cutoff"] = round(cut, 1)
        out["sand_fraction"] = round(float(sandy.mean()), 2)
        if res:
            r = df[res].astype(float)
            out["res_in_sand_p90"] = round(float(np.nanpercentile(r[sandy], 90)), 2) if sandy.any() else None
            out["res_in_shale_median"] = round(float(np.nanmedian(r[~sandy])), 2) if (~sandy).any() else None
    for name, keys in (("res_curve", RES_KEYS), ("den_curve", DEN_KEYS),
                       ("neu_curve", NEU_KEYS), ("sonic_curve", SON_KEYS), ("gr_curve", GR_KEYS)):
        c = _curve(df, keys)
        if c:
            out[name] = str(c)
    return out


def load_wells(data_dir: Path, cdp_x: np.ndarray, cdp_y: np.ndarray,
               results_csv: Path | None = None) -> list[dict]:
    wd = io.resolve(data_dir, "well_data")
    wells: dict[str, dict] = {}

    # 1) well list spreadsheet (names, maybe coordinates and results)
    xlsx = next((p for p in wd.iterdir() if p.suffix.lower() in (".xlsx", ".xls")), None)
    if xlsx:
        df = io.read_well_list(xlsx)
        nc = io.find_col(df, "well", "name")
        xc = io.find_col(df, "x coord", "easting", "surface x", "x")
        yc = io.find_col(df, "y coord", "northing", "surface y", "y")
        rc = io.find_col(df, "result", "status", "outcome", "fluid")
        for _, row in df.iterrows():
            name = str(row[nc]).strip().lower() if nc else None
            if not name or name == "nan":
                continue
            w = wells.setdefault(name, {"name": name})
            if xc and yc:
                try:
                    w["x"], w["y"] = float(row[xc]), float(row[yc])
                except (TypeError, ValueError):
                    pass
            if rc:
                w["result_text"] = str(row[rc])
            w["well_list"] = {str(k): (None if str(v) == "nan" else str(v)) for k, v in row.items()}

    # 2) deviation files: use the lower part of the path as the reservoir location
    dev_dir = wd / "deviations" if (wd / "deviations").exists() else None
    if dev_dir:
        for f in sorted(dev_dir.glob("*.txt")):
            name = f.name.split("_")[0].lower()
            try:
                d = io.read_table_txt(f)
            except Exception:
                continue
            xc, yc = io.find_col(d, "x"), io.find_col(d, "y")
            w = wells.setdefault(name, {"name": name})
            if xc and yc:
                xs, ys = d[xc].astype(float).values, d[yc].astype(float).values
                k = max(1, len(xs) // 3)
                w["x"], w["y"] = float(np.nanmean(xs[-k:])), float(np.nanmean(ys[-k:]))

    # 3) LAS summaries
    las_dir = wd / "las" if (wd / "las").exists() else None
    if las_dir:
        for f in sorted(las_dir.glob("*.las")):
            name = f.stem.lower()
            w = wells.setdefault(name, {"name": name})
            try:
                df, hdr = io.read_las(f)
                w["logs"] = log_summary(df)
                for key in ("XCOORD", "X", "XWELL"):
                    if "x" not in w and key in hdr:
                        try:
                            w["x"] = float(hdr[key]); w["y"] = float(hdr[key.replace("X", "Y")])
                        except (KeyError, ValueError):
                            pass
            except Exception as e:  # keep going; report in the summary
                w["logs"] = {"error": str(e)}

    # 4) manual results from Ruthan (overrides spreadsheet text)
    if results_csv and Path(results_csv).exists():
        with open(results_csv) as fh:
            for row in csv.DictReader(fh):
                n = row["well"].strip().lower()
                if n in wells:
                    wells[n]["result_text"] = row.get("result", "")
                    wells[n]["notes"] = row.get("notes", "")

    place_on_grid(list(wells.values()), cdp_x, cdp_y)
    for w in wells.values():
        w["result"] = classify_result(w.get("result_text"))
    return sorted(wells.values(), key=lambda w: w["name"])


def place_on_grid(wells: list[dict], cdp_x: np.ndarray, cdp_y: np.ndarray) -> None:
    ok = np.isfinite(cdp_x) & np.isfinite(cdp_y)
    ii, jj = np.nonzero(ok)
    tree = cKDTree(np.c_[cdp_x[ok], cdp_y[ok]])
    for w in wells:
        if "x" in w and "y" in w:
            dist, k = tree.query([w["x"], w["y"]])
            w["i"], w["j"] = int(ii[k]), int(jj[k])
            w["grid_distance_m"] = round(float(dist), 1)
            w["inside_survey"] = bool(dist < 100)
        else:
            w["i"] = w["j"] = None


def calibrate(wells: list[dict], maps: dict[str, np.ndarray]) -> dict:
    """Attribute values at each well, and averages for discoveries vs dry wells."""
    rows = []
    for w in wells:
        if w.get("i") is None or not w.get("inside_survey", True):
            continue
        vals = {k: float(np.nanmean(v[max(w["i"] - 1, 0): w["i"] + 2,
                                       max(w["j"] - 1, 0): w["j"] + 2]))
                for k, v in maps.items() if k != "top_time"}
        w["attributes_at_well"] = {k: round(v, 3) for k, v in vals.items()}
        rows.append((w["result"], vals))
    summary = {}
    for res in ("discovery", "dry"):
        sel = [v for r, v in rows if r == res]
        if sel:
            summary[res] = {k: round(float(np.mean([s[k] for s in sel])), 3) for k in sel[0]}
            summary[res]["n_wells"] = len(sel)
    return summary
