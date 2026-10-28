"""Find leads (candidate traps) on the attribute maps, classify the trap type,
score the petroleum system and compare leads with each other.

Every number the agent later quotes is produced here, so keep the rules
simple, explainable and calibrated by Ruthan at the wells.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage
from skimage import measure, morphology

from .attributes import fill_nan


@dataclass
class Params:
    sand_threshold: float | None = None   # None -> 80th percentile of the sand map
    min_area_px: int = 40
    closure_min_ms: float = 5.0           # boundary deeper than crest by this -> closure
    conformance_max_ms: float = 8.0
    elongation_channel: float = 3.0
    sinuosity_channel: float = 1.3
    fault_frac_min: float = 0.15
    bin_area_m2: float = 625.0            # 25 m x 25 m; precompute measures the real value
    extra: dict = field(default_factory=dict)


def _clip(v, lo=0.05, hi=0.95):
    return float(np.clip(v, lo, hi))


def _r(v, n=2):
    return None if v is None or not np.isfinite(v) else round(float(v), n)


def sand_threshold(sand: np.ndarray) -> float:
    """Otsu split between background and sand bodies (bimodal sand map).
    Override with --sand-threshold once Ruthan calibrates it at the wells."""
    from skimage.filters import threshold_otsu
    v = sand[np.isfinite(sand)]
    return float(max(threshold_otsu(v), np.percentile(v, 60)))


def fault_lines(disc: np.ndarray, thr: float, min_len_px: int = 40,
                min_elong: float = 5.0) -> np.ndarray:
    """Keep only long, thin high-discontinuity streaks (faults), not blobs
    (noise) or curved channel edges."""
    hi = np.nan_to_num(disc) > thr
    lab = measure.label(hi)
    keep = np.zeros_like(hi)
    for r in measure.regionprops(lab):
        L, W = r.axis_major_length, max(r.axis_minor_length, 1.0)
        if L >= min_len_px and L / W >= min_elong:
            keep |= lab == r.label
    return keep


def detect(maps: dict[str, np.ndarray], wells: list[dict], p: Params) -> list[dict]:
    sand = maps["sand"]
    valid = np.isfinite(sand)
    thr = p.sand_threshold if p.sand_threshold is not None else sand_threshold(sand)
    mask = np.nan_to_num(sand) >= thr
    mask = ndimage.binary_opening(mask, structure=morphology.disk(1))
    disc = maps.get("disc")
    disc_thr = float(np.nanpercentile(disc, 95)) if disc is not None else None
    if disc is not None:   # split sand bodies along faults: each fault block is its own lead
        fault_zone = ndimage.binary_dilation(fault_lines(disc, disc_thr), iterations=2)
        mask &= ~fault_zone
        fault_near = ndimage.binary_dilation(fault_zone, iterations=2)
    else:
        fault_near = None
    lab = measure.label(mask, connectivity=1)
    sizes = np.bincount(lab.ravel())
    small = sizes < p.min_area_px
    small[0] = False
    lab[small[lab]] = 0          # drop specks (version-independent remove_small_objects)
    lab = measure.label(lab > 0, connectivity=1)

    tt = ndimage.gaussian_filter(fill_nan(maps["top_time"]), 2) if "top_time" in maps else None
    gy, gx = (np.gradient(tt) if tt is not None else (None, None))

    g = {k: (np.nanmean(v), np.nanstd(v) or 1.0) for k, v in maps.items()}
    leads = []
    for reg in measure.regionprops(lab):
        region = lab == reg.label
        ring = ndimage.binary_dilation(region, structure=morphology.disk(4)) & ~region & valid
        boundary = region & ~ndimage.binary_erosion(region)

        def inside(k):
            return float(np.nanmean(maps[k][region])) if k in maps else np.nan

        def outside(k):
            return float(np.nanmean(maps[k][ring])) if k in maps and ring.any() else np.nan

        major = max(reg.axis_major_length, 1.0)
        minor = max(reg.axis_minor_length, 1.0)
        elong = major / minor
        skel = morphology.skeletonize(region)
        sinuosity = max(float(skel.sum()) / major, 1.0)

        # structure from the pseudo-horizon (smaller time = higher)
        closure_ms = conformance_ms = updip_sand = np.nan
        crest = None
        if tt is not None:
            vals = tt[region]
            ci = np.argmin(np.where(region, tt, np.inf))
            crest = np.unravel_index(ci, tt.shape)
            closure_ms = float(np.nanpercentile(tt[boundary], 10) - np.nanmin(vals))
            conformance_ms = float(np.nanstd(tt[boundary]))
            # walk up-dip (towards smaller time) from the crest until leaving the body
            d = -np.array([gy[crest], gx[crest]])
            if np.linalg.norm(d) > 1e-6:
                d = d / np.linalg.norm(d)
                pos = np.array(crest, float)
                samples = []
                for _ in range(60):
                    pos += d
                    i, j = int(round(pos[0])), int(round(pos[1]))
                    if not (0 <= i < sand.shape[0] and 0 <= j < sand.shape[1]):
                        break
                    if not region[i, j]:
                        samples.append(sand[i, j])
                        if len(samples) >= 4:
                            break
                if samples:
                    updip_sand = float(np.nanmean(samples))

        fault_frac = float(fault_near[boundary].mean()) if fault_near is not None else 0.0

        stats = {k: (inside(k), outside(k)) for k in ("sand", "vpvs", "pimp", "avo_diff", "rms_full")}
        z = {k: (stats[k][0] - stats[k][1]) / g[k][1] if k in g else np.nan for k in stats}

        strat = elong >= p.elongation_channel or sinuosity >= p.sinuosity_channel
        struct = (np.isfinite(closure_ms) and closure_ms >= p.closure_min_ms
                  and conformance_ms <= p.conformance_max_ms)
        faulted = fault_frac >= p.fault_frac_min
        if strat and (faulted or struct):
            trap, sub = "Combination", ("channel sand closed against a fault" if faulted
                                        else "channel sand draped over a structural high")
        elif strat:
            trap, sub = "Stratigraphic", "channel / point-bar sand body"
        elif struct and faulted:
            trap, sub = "Structural", "fault-dependent closure"
        elif struct:
            trap, sub = "Structural", "four-way dip closure"
        elif faulted:
            trap, sub = "Structural", "fault trap (needs fault-seal check)"
        else:
            trap, sub = "Unclassified", "sand body without a clear trapping geometry"

        # ---- petroleum-system scorecard (simple, explainable rules)
        p_res = _clip(0.35 + 1.2 * (stats["sand"][0] - 0.5))
        updip_shale = np.isfinite(updip_sand) and updip_sand < 0.6 * thr
        if trap == "Stratigraphic":
            p_trap = 0.55 if updip_shale else 0.35
            p_seal = 0.6 if updip_shale else 0.4
        elif trap == "Combination":
            p_trap = 0.6 if (updip_shale or struct) else 0.45
            p_seal = 0.5 if faulted else 0.6
        elif trap == "Structural":
            p_trap = _clip(0.3 + (closure_ms if np.isfinite(closure_ms) else 0) / 40, 0.2, 0.85)
            p_seal = 0.45 if faulted else 0.65
        else:
            p_trap, p_seal = 0.2, 0.4
        p_charge = _clip(0.35 - 0.12 * np.nan_to_num(z["vpvs"]) + 0.12 * np.nan_to_num(z["avo_diff"]), 0.1, 0.85)
        gcos = p_res * p_trap * p_seal * p_charge

        ii, jj = np.nonzero(region)
        in_wells = [w["name"] for w in wells
                    if w.get("i") is not None and region[w["i"], w["j"]]]
        near = None
        if wells:
            ci, cj = reg.centroid
            dist = [(np.hypot(w["i"] - ci, w["j"] - cj), w["name"]) for w in wells if w.get("i") is not None]
            if dist:
                near = min(dist)[1]

        contour = max(measure.find_contours(np.pad(region, 1).astype(float), 0.5), key=len) - 1
        step = max(1, len(contour) // 80)
        poly = [[_r(a, 1), _r(b, 1)] for a, b in contour[::step]]

        area_km2 = reg.area * p.bin_area_m2 / 1e6
        leads.append({
            "trap_type": trap, "subtype": sub,
            "drilled": bool(in_wells), "wells_inside": in_wells, "nearest_well": near,
            "centroid": [_r(reg.centroid[0], 1), _r(reg.centroid[1], 1)],
            "crest": [int(crest[0]), int(crest[1])] if crest is not None else None,
            "polygon": poly, "area_px": int(reg.area), "area_km2": _r(area_km2, 2),
            "shape": {"elongation": _r(elong), "sinuosity": _r(sinuosity)},
            "structure": {"closure_ms": _r(closure_ms, 1), "boundary_time_std_ms": _r(conformance_ms, 1),
                          "crest_time_ms": _r(float(tt[crest]) if crest is not None else np.nan, 1),
                          "updip_sand_prob": _r(updip_sand), "updip_is_shale": bool(updip_shale)},
            "fault_contact_frac": _r(fault_frac),
            "attributes": {k: {"inside": _r(v[0], 3), "outside": _r(v[1], 3), "z": _r(z[k])}
                           for k, v in stats.items()},
            "scorecard": {"reservoir": _r(p_res), "trap": _r(p_trap), "seal": _r(p_seal),
                          "charge": _r(p_charge)},
            "gcos": _r(gcos, 3), "risked_area_km2": _r(gcos * area_km2, 3),
            "flags": {"stratigraphic": bool(strat), "closure": bool(struct), "faulted": bool(faulted)},
            "_pixels": (ii, jj),
        })

    leads.sort(key=lambda d: -d["gcos"])
    for k, d in enumerate(leads, 1):
        d["id"] = f"L{k}"
        d["name"] = f"Lead {k}"
    _add_features(leads)
    return leads


FEATURES = ["sand_in", "vpvs_z", "avo_z", "pimp_z", "log_area", "elongation", "closure_ms"]


def _feature_row(d: dict) -> list[float]:
    a = d["attributes"]
    return [a["sand"]["inside"] or 0, a["vpvs"]["z"] or 0, a["avo_diff"]["z"] or 0,
            a["pimp"]["z"] or 0, float(np.log1p(d["area_km2"] or 0)),
            d["shape"]["elongation"] or 1, d["structure"]["closure_ms"] or 0]


def _add_features(leads: list[dict]) -> None:
    if not leads:
        return
    X = np.array([_feature_row(d) for d in leads], float)
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    for d, row, zrow in zip(leads, X, Z):
        d["features"] = {k: _r(v, 3) for k, v in zip(FEATURES, row)}
        d["features_z"] = [_r(v, 3) for v in zrow]


def similar(leads: list[dict], target_id: str, k: int = 5, pool: str = "undrilled") -> list[dict]:
    """Rank leads by cosine similarity of their standardized feature vectors.
    pool: 'undrilled' (find traps yet to be tested), 'drilled' (find analogs), 'all'."""
    by_id = {d["id"]: d for d in leads}
    t = np.array(by_id[target_id]["features_z"], float)
    out = []
    for d in leads:
        if d["id"] == target_id or (pool == "undrilled" and d["drilled"]) \
                or (pool == "drilled" and not d["drilled"]):
            continue
        v = np.array(d["features_z"], float)
        cos = float(t @ v / (np.linalg.norm(t) * np.linalg.norm(v) + 1e-9))
        close = [FEATURES[i] for i in range(len(FEATURES)) if abs(t[i] - v[i]) < 0.5]
        differ = [FEATURES[i] for i in range(len(FEATURES)) if abs(t[i] - v[i]) >= 1.0]
        out.append({"id": d["id"], "name": d["name"], "trap_type": d["trap_type"],
                    "drilled": d["drilled"], "wells_inside": d["wells_inside"],
                    "similarity": _r(cos, 3), "gcos": d["gcos"],
                    "matching_features": close, "different_features": differ})
    out.sort(key=lambda r: -r["similarity"])
    positive = [r for r in out if r["similarity"] > 0]
    return (positive or out[:1])[:k]   # negative cosine = not similar; keep at least one for context
