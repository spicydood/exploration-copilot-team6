"""Static renders for the bottom-left "Volume" and "Stack" views.

    MOCK=1 python -m engine.render_instrument          # writes store_mock/renders/{volume,stack_L1..}.png
    python -m engine.render_instrument                 # real store (keep the output on the HPC)

Every mark encodes an engine value:
  volume.png   isometric wireframe of the survey box, the reservoir-top pseudo-horizon (maps/top_time.npy)
               coloured by Vp/Vs (maps/vpvs.npy), and the base mesh where sand_prob >= sand_threshold
               (deepest such sample per bin, from cubes/sand_prob.npy + cubes/times.npy).
               Display smoothing: Gaussian sigma = 3 bins (the raw pseudo-horizon has bin-to-bin steps).
  stack_<L>.png exploded risk stack for one lead: four slabs (charge, reservoir, trap, seal) drawn as
               isometric plates; the reservoir plate carries the sand-probability map cropped to the lead
               and the lead outline; seal and charge plates are schematic (no engine surface exists) and
               say so in the UI caption. Opacity of each plate = that pillar's probability.
Transparent background so the UI's own surface shows through; lines are >= 1.2 px for RustDesk streams.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

# Isometric projection of bin coordinates (i = inline index, j = crossline index) and time t (ms):
#   sx = (j - i) * COS30 ;  sy = (i + j) * SIN30 + (t - t0) * ZSCALE      (screen y grows downward)
COS30, SIN30 = 0.8660254, 0.5
INK = (0.929, 0.902, 0.855)          # #ede6da, the on-scrim text colour the UI uses over dark wells
OCHRE = (0.851, 0.643, 0.255)        # #d9a441


def project(i: np.ndarray, j: np.ndarray, t: np.ndarray, t0: float, zscale: float) -> tuple[np.ndarray, np.ndarray]:
    return (j - i) * COS30, (i + j) * SIN30 + (t - t0) * zscale


def smooth(a: np.ndarray, sigma: float) -> np.ndarray:
    from scipy import ndimage
    mask = np.isfinite(a)
    filled = np.where(mask, a, np.nanmean(a))
    s = ndimage.gaussian_filter(filled, sigma)
    return np.where(mask, s, np.nan)


def render_volume(store: Path, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    meta = json.loads((store / "meta.json").read_text())
    top = np.load(store / "maps" / "top_time.npy").astype(float)
    vpvs = np.load(store / "maps" / "vpvs.npy").astype(float)
    cube = np.load(store / "cubes" / "sand_prob.npy", mmap_mode="r")
    times = np.load(store / "cubes" / "times.npy")
    thr = float(meta.get("sand_threshold", 0.5))
    ni, nj = top.shape
    t0, t1 = float(meta["window_ms"][0]), float(meta["window_ms"][1])

    # base = deepest sample where sand_prob >= thr (NaN where the bin never reaches the threshold)
    hit = np.asarray(cube) >= thr
    idx = np.where(hit.any(axis=2), hit.shape[2] - 1 - np.argmax(hit[:, :, ::-1], axis=2), -1)
    base = np.where(idx >= 0, times[np.clip(idx, 0, len(times) - 1)], np.nan)

    top_s, base_s = smooth(top, 3.0), smooth(base, 3.0)
    zscale = 0.9 * (ni + nj) * SIN30 / max(t1 - t0, 1.0) * 0.35   # low vertical exaggeration
    step = 8
    I, J = np.meshgrid(np.arange(0, ni, step), np.arange(0, nj, step), indexing="ij")

    fig, ax = plt.subplots(figsize=(12, 7.6), dpi=100)
    fig.patch.set_alpha(0.0); ax.set_axis_off(); ax.set_facecolor((0, 0, 0, 0))

    def wire(z: np.ndarray, color, lw: float, alpha: float, cmap=None, cvals=None):
        segs, cols = [], []
        for a in range(I.shape[0]):
            for b in range(I.shape[1] - 1):
                i0, j0, i1, j1 = I[a, b], J[a, b], I[a, b + 1], J[a, b + 1]
                if np.isfinite(z[i0, j0]) and np.isfinite(z[i1, j1]):
                    x0, y0 = project(i0, j0, z[i0, j0], t0, zscale); x1, y1 = project(i1, j1, z[i1, j1], t0, zscale)
                    segs.append([(x0, y0), (x1, y1)]); cols.append(cvals[i0, j0] if cvals is not None else 0)
        for b in range(I.shape[1]):
            for a in range(I.shape[0] - 1):
                i0, j0, i1, j1 = I[a, b], J[a, b], I[a + 1, b], J[a + 1, b]
                if np.isfinite(z[i0, j0]) and np.isfinite(z[i1, j1]):
                    x0, y0 = project(i0, j0, z[i0, j0], t0, zscale); x1, y1 = project(i1, j1, z[i1, j1], t0, zscale)
                    segs.append([(x0, y0), (x1, y1)]); cols.append(cvals[i0, j0] if cvals is not None else 0)
        lc = LineCollection(segs, linewidths=lw, alpha=alpha)
        if cmap is not None:
            lc.set_array(np.array(cols)); lc.set_cmap(cmap); lc.set_clim(float(np.nanmin(cvals)), float(np.nanmax(cvals)))
        else:
            lc.set_color(color)
        ax.add_collection(lc)

    # survey box edges (top at t0, bottom at t1)
    corners = [(0, 0), (0, nj - 1), (ni - 1, nj - 1), (ni - 1, 0)]
    for t in (t0, t1):
        pts = [project(np.array(i), np.array(j), np.array(t), t0, zscale) for i, j in corners]
        ax.plot([p[0] for p in pts] + [pts[0][0]], [p[1] for p in pts] + [pts[0][1]], color=INK, lw=1.2, alpha=0.55)
    for i, j in corners:
        (x0, y0), (x1, y1) = project(np.array(i), np.array(j), np.array(t0), t0, zscale), project(np.array(i), np.array(j), np.array(t1), t0, zscale)
        ax.plot([x0, x1], [y0, y1], color=INK, lw=1.2, alpha=0.55)

    # floor reference grid at t1 (faint), every 16 bins: gives the eye a plane to read heights against
    for i in range(0, ni, 16):
        x, y = project(np.full(2, i, float), np.array([0.0, nj - 1.0]), np.full(2, t1), t0, zscale); ax.plot(x, y, color=INK, lw=0.8, alpha=0.22)
    for j in range(0, nj, 16):
        x, y = project(np.array([0.0, ni - 1.0]), np.full(2, j, float), np.full(2, t1), t0, zscale); ax.plot(x, y, color=INK, lw=0.8, alpha=0.22)
    # the pseudo-horizon exists only where sand was called, so draw its bins as cells, not a wire
    ii, jj = np.mgrid[0:ni:2, 0:nj:2]
    ok = np.isfinite(top_s[::2, ::2])
    bx, by = project(ii[ok].astype(float), jj[ok].astype(float), base_s[::2, ::2][ok] if np.isfinite(base_s[::2, ::2][ok]).all() else np.where(np.isfinite(base_s[::2, ::2][ok]), base_s[::2, ::2][ok], top_s[::2, ::2][ok] + 18), t0, zscale)
    ax.scatter(bx, by, s=9, marker="s", color=INK, alpha=0.22, linewidths=0)            # base mesh (sand_prob >= thr)
    tx, ty = project(ii[ok].astype(float), jj[ok].astype(float), top_s[::2, ::2][ok], t0, zscale)
    sc = ax.scatter(tx, ty, s=11, marker="s", c=vpvs[::2, ::2][ok], cmap="viridis_r", alpha=0.95, linewidths=0,
                    vmin=float(np.nanmin(vpvs)), vmax=float(np.nanmax(vpvs)))         # top, coloured by Vp/Vs
    # lead outlines at their crest time, in the trap colour the UI uses
    trap_col = {"Structural": (0.435, 0.639, 0.627), "Stratigraphic": (0.498, 0.651, 0.851), "Combination": (0.831, 0.478, 0.314)}
    leads = json.loads((store / "leads.json").read_text())
    for d in leads:
        poly = np.array(d["polygon"], float); tc = float(d.get("structure", {}).get("crest_time_ms") or np.nanmedian(top))
        px, py = project(poly[:, 0], poly[:, 1], np.full(len(poly), tc), t0, zscale)
        ax.plot(np.r_[px, px[0]], np.r_[py, py[0]], color=trap_col.get(d["trap_type"], INK), lw=1.6, alpha=0.95,
                linestyle="-" if d["drilled"] else (0, (5, 3)))
    ax.set_aspect("equal"); ax.autoscale(); ax.invert_yaxis()
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "volume.png", transparent=True, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    print(f"volume.png  ({ni}x{nj} bins, top {np.nanmin(top):.0f}-{np.nanmax(top):.0f} ms, base reaches threshold in "
          f"{int(np.isfinite(base).mean() * 100)}% of bins)")


def render_stacks(store: Path, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    leads = json.loads((store / "leads.json").read_text())
    sand = np.load(store / "maps" / "sand.npy").astype(float)
    ni, nj = sand.shape
    pillars = [("charge", (0.55, 0.47, 0.40)), ("reservoir", OCHRE), ("trap", (0.44, 0.64, 0.63)), ("seal", (0.61, 0.58, 0.53))]
    for d in leads:
        poly = np.array(d["polygon"], dtype=float)
        pad = 12
        i0, i1 = max(0, int(poly[:, 0].min()) - pad), min(ni - 1, int(poly[:, 0].max()) + pad)
        j0, j1 = max(0, int(poly[:, 1].min()) - pad), min(nj - 1, int(poly[:, 1].max()) + pad)
        h, w = i1 - i0 + 1, j1 - j0 + 1
        lift = 0.55 * (h + w) * SIN30
        fig, ax = plt.subplots(figsize=(5.2, 7.2), dpi=100)
        fig.patch.set_alpha(0.0); ax.set_axis_off()
        for k, (name, col) in enumerate(pillars):
            p = float(d["scorecard"].get(name, 0.5))
            dz = -k * lift
            corners = [(i0, j0), (i0, j1), (i1, j1), (i1, j0)]
            pts = [project(np.array(i), np.array(j), np.array(dz), 0.0, 1.0) for i, j in corners]
            ax.add_patch(Polygon(pts, closed=True, facecolor=(*col, 0.15 + 0.6 * p), edgecolor=INK, lw=1.2))
            if name == "reservoir":
                crop = sand[i0:i1 + 1, j0:j1 + 1]
                yy, xx = np.mgrid[i0:i1 + 1, j0:j1 + 1]
                sx, sy = project(yy.astype(float), xx.astype(float), np.full(yy.shape, dz), 0.0, 1.0)
                ax.scatter(sx, sy, c=crop, cmap="inferno", s=6, marker="s", alpha=0.9, linewidths=0, vmin=0, vmax=1)
                px, py = project(poly[:, 0], poly[:, 1], np.full(len(poly), dz), 0.0, 1.0)
                ax.plot(np.r_[px, px[0]], np.r_[py, py[0]], color=OCHRE, lw=2.0)
        ax.set_aspect("equal"); ax.autoscale(); ax.invert_yaxis()
        fig.savefig(out / f"stack_{d['id']}.png", transparent=True, bbox_inches="tight", pad_inches=0.1)
        plt.close(fig)
        print(f"stack_{d['id']}.png  (plates at scorecard probabilities {d['scorecard']})")


def main() -> int:
    store = Path(config.STORE_DIR)
    out = store / "renders"
    render_volume(store, out)
    render_stacks(store, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
