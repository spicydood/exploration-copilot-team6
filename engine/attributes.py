"""Turn 3D volumes into 2D map attributes over the reservoir time window.

All functions take (n_il, n_xl, n_t) arrays and return (n_il, n_xl) maps.
Ruthan sets the window (t0, t1) around the reservoir interval.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def window_mean(cube: np.ndarray, sl: slice) -> np.ndarray:
    return np.nanmean(cube[:, :, sl], axis=2)


def window_min(cube: np.ndarray, sl: slice) -> np.ndarray:
    return np.nanmin(cube[:, :, sl], axis=2)


def window_max(cube: np.ndarray, sl: slice) -> np.ndarray:
    return np.nanmax(cube[:, :, sl], axis=2)


def window_rms(cube: np.ndarray, sl: slice) -> np.ndarray:
    return np.sqrt(np.nanmean(cube[:, :, sl] ** 2, axis=2))


def avo_maps(near: np.ndarray, far: np.ndarray, sl: slice) -> dict[str, np.ndarray]:
    """Far vs near amplitude. Gas sands in young clastic basins often brighten
    with angle, so a positive far-minus-near (or ratio > 1) is a charge hint.
    Calibrate the sign and cut-off at the wells before trusting it."""
    rn, rf = window_rms(near, sl), window_rms(far, sl)
    return {
        "avo_diff": rf - rn,
        "avo_ratio": rf / np.where(rn > 1e-9, rn, np.nan),
    }


def top_time_map(prob: np.ndarray, times: np.ndarray, sl: slice,
                 threshold: float) -> np.ndarray:
    """Pseudo-horizon: first time in the window where sand probability exceeds
    the threshold (NaN where it never does). Smaller time = structurally higher.
    Replace with a horizon picked in DUG Insight when Ruthan exports one."""
    sub = np.nan_to_num(prob[:, :, sl])
    hit = sub >= threshold
    k = np.argmax(hit, axis=2)
    any_hit = hit.any(axis=2)
    dt = times[1] - times[0]
    # linear interpolation between the sample before and at the crossing
    kp = np.clip(k - 1, 0, sub.shape[2] - 1)
    v1 = np.take_along_axis(sub, k[..., None], 2)[..., 0]
    v0 = np.take_along_axis(sub, kp[..., None], 2)[..., 0]
    frac = np.where((k > 0) & (v1 > v0), (threshold - v0) / np.maximum(v1 - v0, 1e-9), 1.0)
    t = times[sl][0] + (k - 1 + np.clip(frac, 0, 1)) * dt
    t = np.where(k == 0, times[sl][0], t)
    return np.where(any_hit, t, np.nan)


def fill_nan(a: np.ndarray) -> np.ndarray:
    """Nearest-neighbour fill so smoothing / gradients behave at gaps."""
    mask = np.isnan(a)
    if not mask.any():
        return a
    idx = ndimage.distance_transform_edt(mask, return_distances=False,
                                         return_indices=True)
    return a[tuple(idx)]


def discontinuity(full: np.ndarray, sl: slice, size: int = 3) -> np.ndarray:
    """Cheap fault attribute: 1 - average correlation of each trace with its
    inline and crossline neighbours over the window (0 = continuous, 1 = broken).
    Good enough to flag faults cutting a lead; Ruthan's picks are better."""
    seg = np.nan_to_num(full[:, :, sl])
    seg = seg - seg.mean(axis=2, keepdims=True)
    norm = np.sqrt((seg ** 2).sum(axis=2)) + 1e-9
    out = np.zeros(seg.shape[:2])
    cnt = np.zeros(seg.shape[:2])
    for axis in (0, 1):
        a = seg
        b = np.roll(seg, -1, axis=axis)
        nb = np.roll(norm, -1, axis=axis)
        corr = (a * b).sum(axis=2) / (norm * nb)
        valid = np.ones_like(corr, bool)
        if axis == 0:
            valid[-1, :] = False
        else:
            valid[:, -1] = False
        out += np.where(valid, 1 - corr, 0)
        cnt += valid
    d = out / np.maximum(cnt, 1)
    return ndimage.uniform_filter(d, size=size)


def standardize(a: np.ndarray) -> np.ndarray:
    m, s = np.nanmean(a), np.nanstd(a)
    return (a - m) / (s if s > 0 else 1)
