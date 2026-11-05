"""Write the synthetic survey as real SEG-Y + LAS files in the HPC folder layout.

Lets a laptop exercise the real-data path (check_real_data.py, engine.precompute
without MOCK) before anyone touches the HPC. Nothing written here is real data.

    python scripts/make_fake_segy.py /tmp/fake_c1
    COPILOT_DATA_DIR=/tmp/fake_c1 python scripts/check_real_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from engine import mock_data  # noqa: E402


def write_volume(path: Path, v, coord_scalar: int = -100) -> None:
    import segyio

    n_il, n_xl, n_t = v.data.shape
    spec = segyio.spec()
    spec.format = 5                       # IEEE float
    spec.samples = v.times
    spec.tracecount = n_il * n_xl
    path.parent.mkdir(parents=True, exist_ok=True)
    with segyio.create(str(path), spec) as f:
        dt_us = int(round((v.times[1] - v.times[0]) * 1000))
        f.bin.update(hdt=dt_us, hns=n_t)
        k = 0
        for a, il in enumerate(v.ilines):
            for b, xl in enumerate(v.xlines):
                f.header[k] = {
                    config.ILINE_BYTE: int(il), config.XLINE_BYTE: int(xl),
                    segyio.TraceField.CDP_X: int(round(v.cdp_x[a, b] * abs(coord_scalar))),
                    segyio.TraceField.CDP_Y: int(round(v.cdp_y[a, b] * abs(coord_scalar))),
                    segyio.TraceField.SourceGroupScalar: coord_scalar,
                    segyio.TraceField.DelayRecordingTime: int(v.times[0]),
                    segyio.TraceField.TRACE_SAMPLE_INTERVAL: dt_us,
                    segyio.TraceField.TRACE_SAMPLE_COUNT: n_t,
                }
                f.trace[k] = np.nan_to_num(v.data[a, b]).astype(np.float32)
                k += 1


def main(out: str) -> None:
    root = Path(out)
    vols, _ = mock_data.build()
    for name, rel in config.VOLUMES.items():
        write_volume(root / rel, vols[name])
        print("wrote", rel)
    wd = mock_data.write_well_files(root) / "well_data"
    # match the HPC file name
    (wd / "Mock_WellList_Information.xlsx").rename(wd / "Challenge1_Challenge2_WellList_Information.xlsx")
    print("wrote well_data/ (LAS, deviations, well list)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fake_c1")
