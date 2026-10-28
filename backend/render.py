"""On-demand seismic section images (inline or crossline) with the sand body
outlined and nearby wells drawn. Cached as PNG in the store."""
from __future__ import annotations

import io as _io
from pathlib import Path

import numpy as np

from .store import Store


def section_png(store: Store, inline: int | None = None, crossline: int | None = None) -> bytes:
    cache = Path(store.root) / "sections"
    cache.mkdir(exist_ok=True)
    key = f"il{inline}" if inline is not None else f"xl{crossline}"
    path = cache / f"{key}.png"
    if path.exists():
        return path.read_bytes()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    times = store.cube_times
    if inline is not None:
        i = store.il_index(inline)
        amp = np.asarray(store.cube_full[i, :, :], dtype=np.float32).T
        sand = np.asarray(store.cube_sand[i, :, :], dtype=np.float32).T
        axis_vals = store.meta["xl_values"]
        wells = [(w["j"], w["name"]) for w in store.wells if w.get("i") is not None and abs(w["i"] - i) <= 2]
        title, xlab = f"Inline {inline}", "Crossline"
    else:
        j = store.xl_index(crossline)
        amp = np.asarray(store.cube_full[:, j, :], dtype=np.float32).T
        sand = np.asarray(store.cube_sand[:, j, :], dtype=np.float32).T
        axis_vals = store.meta["il_values"]
        wells = [(w["i"], w["name"]) for w in store.wells if w.get("i") is not None and abs(w["j"] - j) <= 2]
        title, xlab = f"Crossline {crossline}", "Inline"

    clip = np.nanpercentile(np.abs(amp), 98) or 1.0
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=110)
    fig.patch.set_facecolor("#0f1720")
    ax.set_facecolor("#0f1720")
    ext = [axis_vals[0], axis_vals[-1], times[-1], times[0]]
    ax.imshow(amp, cmap="seismic", vmin=-clip, vmax=clip, aspect="auto", extent=ext, interpolation="bilinear")
    thr = store.meta.get("sand_threshold", 0.5)
    xs = np.linspace(axis_vals[0], axis_vals[-1], amp.shape[1])
    ax.contour(xs, times, np.nan_to_num(sand), levels=[thr], colors="#ffd166", linewidths=1.4)
    w0, w1 = store.meta["window_ms"]
    ax.axhspan(w0, w1, color="#ffd166", alpha=0.06)
    for k, name in wells:
        x = axis_vals[int(k)]
        ax.axvline(x, color="#e5e7eb", lw=1.2)
        ax.text(x, times[0] + 0.03 * (times[-1] - times[0]), f" {name}", color="#e5e7eb", fontsize=8, va="top")
    ax.set_title(title + "  ·  yellow = sand above threshold", color="#e5e7eb", fontsize=10, loc="left")
    ax.set_xlabel(xlab, color="#9ca3af"); ax.set_ylabel("Time (ms)", color="#9ca3af")
    ax.tick_params(colors="#9ca3af", labelsize=8)
    for sp in ax.spines.values():
        sp.set_color("#374151")
    fig.tight_layout()
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    path.write_bytes(buf.getvalue())
    return buf.getvalue()
