"""A small synthetic survey that looks like the brief's example: a meandering
gas-charged channel cut by a sealing fault, a domal four-way closure, a second
undrilled channel, and a wet sand bar. Lets the whole app run on a laptop.

Nothing here is real data. Well names are invented.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .io import Volume

N_IL, N_XL, N_T, DT, T0 = 160, 200, 120, 4.0, 1800.0
BIN = 25.0


def _ricker(f=30.0, dt=DT / 1000, n=31):
    t = (np.arange(n) - n // 2) * dt
    a = (np.pi * f * t) ** 2
    return (1 - 2 * a) * np.exp(-a)


def _fault_j(i):
    return 125 + 0.35 * (i - 80)


def build(seed: int = 7) -> tuple[dict[str, Volume], dict]:
    rng = np.random.default_rng(seed)
    I, J = np.mgrid[0:N_IL, 0:N_XL].astype(float)

    # structure: regional dip to the east, a dome in the north-west, fault throw on the east
    top = 1990 + 0.18 * J
    top -= 40 * np.exp(-((I - 45) ** 2 + (J - 38) ** 2) / (2 * 14 ** 2))
    east = J > _fault_j(I)
    top += np.where(east, 16.0, 0.0)

    # sand bodies (map view)
    cl1 = 95 + 22 * np.sin(I / 13.0) + 8 * np.sin(I / 5.0)      # main channel centreline (along inlines)
    ch1 = np.abs(J - cl1) < 4.5
    cl2 = 168 + 9 * np.sin((I - 20) / 8.0)                      # second channel, south-east, undrilled
    ch2 = (np.abs(J - cl2) < 3.5) & (I > 70) & (I < 150)
    dome = (I - 45) ** 2 + (J - 38) ** 2 < 14 ** 2
    bar = ((I - 130) / 9) ** 2 + ((J - 40) / 6) ** 2 < 1         # wet sand bar
    sand2d = np.clip(0.18 + 0.08 * rng.standard_normal((N_IL, N_XL)), 0, 1)
    for m, v in ((ch1, 0.86), (ch2, 0.84), (dome, 0.8), (bar, 0.78)):
        sand2d = np.where(m, v + 0.05 * rng.standard_normal((N_IL, N_XL)), sand2d)
    sand2d = np.clip(sand2d, 0, 1)

    # charge: channel west of the fault (sealed against it), dome, second channel
    gas = (ch1 & ~east) | dome | ch2
    wet_sand = (sand2d > 0.6) & ~gas

    times = T0 + DT * np.arange(N_T)
    T = times[None, None, :]
    in_res = (T >= top[..., None]) & (T < top[..., None] + 20)

    sand = np.where(in_res, sand2d[..., None], 0.12)
    sand = np.clip(sand + 0.03 * rng.standard_normal(sand.shape), 0, 1).astype(np.float32)
    vpvs2d = np.where(gas & (sand2d > 0.6), 1.78, np.where(wet_sand, 2.05, 2.32))
    vpvs = np.where(in_res, vpvs2d[..., None], 2.35) + 0.03 * rng.standard_normal(sand.shape)
    pimp2d = np.where(gas & (sand2d > 0.6), 5850.0, np.where(wet_sand, 6450.0, 7050.0))
    # layered background that follows structure, so traces correlate laterally
    bg_t = np.arange(-400, 600, DT)
    bg = 7100 + np.convolve(rng.standard_normal(bg_t.size) * 260, np.ones(3) / 3, mode="same")
    rel = T - (top[..., None] - 1990.0)
    bg3 = np.interp(rel - 1800.0, bg_t, bg)
    pimp = np.where(in_res, pimp2d[..., None], bg3) + 25 * rng.standard_normal(sand.shape)
    simp = pimp / vpvs

    # angle stacks from impedance contrasts; gas sands brighten with angle
    ai = pimp
    refl = np.zeros_like(ai)
    refl[..., 1:] = (ai[..., 1:] - ai[..., :-1]) / (ai[..., 1:] + ai[..., :-1])
    w = _ricker()
    conv = lambda r: np.apply_along_axis(lambda tr: np.convolve(tr, w, mode="same"), 2, r)
    gas3 = (gas & (sand2d > 0.6))[..., None] & in_res
    near = conv(refl)
    mid = conv(refl * np.where(gas3, 1.35, 1.0))
    far = conv(refl * np.where(gas3, 1.8, 0.92))
    ufar = conv(refl * np.where(gas3, 2.1, 0.85))
    full = (near + mid + far) / 3
    noise = lambda a: (a + 0.004 * rng.standard_normal(a.shape)).astype(np.float32)
    # fault zone: scramble a 2-trace band so the discontinuity attribute sees it
    fz = np.abs(J - _fault_j(I)) < 1.2
    full = np.where(fz[..., None], full * 0.3 + 0.01 * rng.standard_normal(full.shape), full)

    il = np.arange(1000, 1000 + N_IL)
    xl = np.arange(2000, 2000 + N_XL)
    cx = 400000 + J * BIN
    cy = 600000 + I * BIN
    mk = lambda d: Volume(d.astype(np.float32), il, xl, times, cx, cy)
    vols = {"full": mk(noise(full)), "near": mk(noise(near)), "mid": mk(noise(mid)),
            "far": mk(noise(far)), "ultrafar": mk(noise(ufar)), "pimp": mk(pimp),
            "simp": mk(simp), "vpvs": mk(vpvs), "sand_prob": mk(sand)}
    truth = {"top": top, "gas": gas, "east": east}
    return vols, truth


# (name, inline index, crossline index, result, has sand, has gas)
MOCK_WELLS = [
    ("kenari-1", 40, None, "Gas discovery", True, True),     # main channel, west of fault
    ("kenari-2", 14, None, "Dry - water-wet sand", True, False),  # main channel, east of fault
    ("merbau-1", 45, 38, "Gas discovery", True, True),        # dome crest
    ("merbau-2", 66, 30, "Dry - no reservoir", False, False),  # dome flank, outside closure
    ("seraya-1", 130, 40, "Dry - water-wet sand", True, False),  # wet bar
    ("jati-1", 20, 170, "Dry - no reservoir", False, False),  # background
    ("meranti-1", 80, None, "Gas discovery", True, True),     # main channel, mid section, west of fault
]


def _channel_j(i):
    return int(round(95 + 22 * np.sin(i / 13.0) + 8 * np.sin(i / 5.0)))


def write_well_files(root: Path, seed: int = 3) -> Path:
    """Write LAS, deviation and well-list files in the same layout as the HPC."""
    rng = np.random.default_rng(seed)
    wd = root / "well_data"
    (wd / "las").mkdir(parents=True, exist_ok=True)
    (wd / "deviations").mkdir(parents=True, exist_ok=True)
    rows = []
    for name, i, j, result, has_sand, has_gas in MOCK_WELLS:
        j = _channel_j(i) if j is None else j
        if name == "kenari-2":
            j = _channel_j(i)
        x, y = 400000 + j * BIN, 600000 + i * BIN
        rows.append({"Well Name": name.upper(), "X Coordinate": x, "Y Coordinate": y,
                     "Result": result, "TD (m MD)": 2600})
        # vertical well: deviation file with X Y TVD MD columns
        md = np.arange(0, 2601, 100.0)
        dev = pd.DataFrame({"MD": md, "X": x, "Y": y, "TVD": md, "INC": 0.0, "AZI": 0.0})
        dev.to_csv(wd / "deviations" / f"{name}_Deviation.txt", sep=" ", index=False)
        # logs: shale background, a 20 m reservoir at 2300-2320 m
        depth = np.arange(1800, 2600, 0.5)
        res = (depth >= 2300) & (depth < 2320) & has_sand
        gr = np.where(res, 38, 105) + 6 * rng.standard_normal(depth.size)
        rt = np.where(res, 45 if has_gas else 1.2, 2.5) * np.exp(0.15 * rng.standard_normal(depth.size))
        rhob = np.where(res, 2.12 if has_gas else 2.28, 2.45) + 0.02 * rng.standard_normal(depth.size)
        nphi = np.where(res, 0.14 if has_gas else 0.25, 0.32) + 0.01 * rng.standard_normal(depth.size)
        dtc = np.where(res, 112 if has_gas else 98, 92) + 2 * rng.standard_normal(depth.size)
        lines = ["~Version", " VERS. 2.0 : CWLS LAS 2.0", " WRAP. NO :", "~Well",
                 f" WELL. {name.upper()} : WELL NAME", " NULL. -999.25 : NULL VALUE",
                 "~Curve", " DEPT.M : Depth", " GR.API : Gamma ray", " RT.OHMM : Resistivity",
                 " RHOB.G/CC : Bulk density", " NPHI.V/V : Neutron porosity", " DTC.US/FT : Sonic",
                 "~ASCII"]
        for row in zip(depth, gr, rt, rhob, nphi, dtc):
            lines.append(" ".join(f"{v:.4f}" for v in row))
        (wd / "las" / f"{name}.las").write_text("\n".join(lines) + "\n")
    pd.DataFrame(rows).to_excel(wd / "Mock_WellList_Information.xlsx", index=False)
    return root
