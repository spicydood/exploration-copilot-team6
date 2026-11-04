"""Download the three OFL faces the UI uses and subset them to WOFF2 for self-hosting.

    .venv/bin/python scripts/fetch_fonts.py          # writes frontend/fonts/*.woff2 + OFL.txt

The HPC allows no external requests at runtime, so fonts ship with the app. Each face is a
variable font; we keep the weight axis (and Fraunces' optical-size axis), subset to Latin plus
the symbols the copy uses, and report which symbols survive. Numbers with units are always set
in JetBrains Mono because Figtree and Fraunces lack Ω σ ≈ Δ ′ √ (measured).
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "fonts"
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FACES = {
    "Figtree": ("figtree/Figtree%5Bwght%5D.ttf", "figtree/OFL.txt"),
    "Fraunces": ("fraunces/Fraunces%5BSOFT%2CWONK%2Copsz%2Cwght%5D.ttf", "fraunces/OFL.txt"),
    "JetBrainsMono": ("jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf", "jetbrainsmono/OFL.txt"),
}
# Latin + Latin-1 + General Punctuation + the data symbols the engine's copy uses.
UNICODES = "U+0000-00FF,U+0100-017F,U+2000-206F,U+20A0-20CF,U+2122,U+2190-2199,U+2212,U+2215,U+221A,U+2248,U+2264,U+2265,U+00B2,U+00B3,U+00D7,U+00B7,U+0394,U+03A9,U+03C3,U+2032,U+2033,U+25CF,U+25CB,U+2713,U+2717"
SYMBOLS = "Ω σ ≈ Δ ′ √ ² ³ × − · … – — ≥ ≤ →"


def fetch(path: str) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.read()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    licences = []
    for name, (ttf_path, ofl_path) in FACES.items():
        print(f"{name}: downloading")
        raw = fetch(ttf_path)
        licences.append(f"==== {name} ====\n" + fetch(ofl_path).decode("utf-8"))
        font = TTFont(io.BytesIO(raw))
        if name == "Fraunces":
            # Pin the two stylistic axes (defaults) and keep weight + optical size: 4 axes -> 2.
            from fontTools.varLib import instancer
            font = instancer.instantiateVariableFont(font, {"SOFT": 0, "WONK": 1, "wght": (300, 700), "opsz": (14, 72)})
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["*"]  # keep kern, liga, tnum, ss*, case, etc.
        opts.name_IDs = ["*"]
        opts.notdef_outline = True
        opts.recalc_bounds = True
        # Keep the variation axes; Fraunces' SOFT/WONK stay at default via CSS.
        s = subset.Subsetter(opts)
        s.populate(unicodes=subset.parse_unicodes(UNICODES))
        s.subset(font)
        cmap = font.getBestCmap()
        missing = [c for c in SYMBOLS.split() if ord(c) not in cmap]
        out = OUT / f"{name}.woff2"
        font.save(out)
        print(f"  -> {out.name} {out.stat().st_size // 1024} KB; missing symbols: {' '.join(missing) or 'none'}")
    (OUT / "OFL.txt").write_text("\n\n".join(licences), encoding="utf-8")
    print("licences written to frontend/fonts/OFL.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
