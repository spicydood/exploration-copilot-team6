"""Read-only input/header check before processing real HPC data.

    python scripts/check_hpc.py
    python scripts/check_hpc.py --check-llm

No trace amplitudes are loaded and no stores are created or replaced.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config
from engine.io import resolve


def main():
    import segyio
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-llm", action="store_true")
    args = parser.parse_args()
    if config.MOCK:
        parser.error("This checks real HPC inputs. Set MOCK=0 first.")
    reference = None
    total = 0
    failures = []
    for name, relative in config.VOLUMES.items():
        try:
            path = resolve(config.DATA_DIR, relative)
            with segyio.open(str(path), "r", ignore_geometry=True) as handle:
                axes = (np.unique(handle.attributes(config.ILINE_BYTE)[:]),
                        np.unique(handle.attributes(config.XLINE_BYTE)[:]), np.asarray(handle.samples))
            if not all(len(axis) for axis in axes):
                raise ValueError("empty grid or samples")
            if reference is None:
                reference = axes
            elif not all(np.array_equal(axis, expected) for axis, expected in zip(axes, reference)):
                raise ValueError("grid or sample coordinates differ from the first volume")
            size = int(np.prod([len(axis) for axis in axes])) * 4
            total += size
            print(f"OK {name}: grid {len(axes[0])} x {len(axes[1])} x {len(axes[2])}; float32 cube {size / 1024**3:.2f} GiB")
        except (OSError, ValueError, RuntimeError) as error:
            failures.append(f"{name}: {error}")
    try:
        wells = resolve(config.DATA_DIR, config.WELL_DIR)
        if not list((wells / "las").glob("*.las")):
            failures.append("No LAS files found in well_data/las.")
    except FileNotFoundError as error:
        failures.append(str(error))
    if args.check_llm:
        import requests
        try:
            response = requests.get(f"{config.LLM_BASE_URL}/models", timeout=10)
            response.raise_for_status()
            models = [model["id"] for model in response.json().get("data", [])]
            if config.LLM_MODEL not in models:
                failures.append("The configured LLM_MODEL was not listed by the service.")
            else:
                print("OK configured model is listed by the shared service.")
        except (requests.RequestException, ValueError, KeyError) as error:
            failures.append(f"LLM check failed: {type(error).__name__}")
    print(f"Combined float32 cube estimate: {total / 1024**3:.2f} GiB, excluding reader copies and processing buffers.")
    print("The current reader loads complete volumes. Check the memory allowance before precompute.")
    print("Coordinate units, well placement, reservoir interval and geological interpretations require review in DUG Insight.")
    for failure in failures:
        print(f"ERROR {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
