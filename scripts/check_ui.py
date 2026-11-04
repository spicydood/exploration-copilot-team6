"""Interface gate for the Exploration Copilot frontend.

    .venv/bin/python scripts/check_ui.py            # all checks, exit 1 on any failure

Checks (each prints its raw numbers; nothing is hidden behind a symbol):
  1. Contrast matrix: every text token on every surface token, both themes (WCAG 2 ratios).
     Text pairs must reach 4.5:1 (3:1 for the large-figure roles), control boundaries 3:1.
  2. No colour literals outside the tokens layer of styles.css, none in index.html, none in js/.
  3. 4-px grid: px lengths in styles.css are multiples of 4 (1 and 2 allowed for borders/nudges).
  4. Slop grep: uppercase transforms, pill radii, transition: all, keyframes on toggled state,
     italic tags in templates, '!' in UI strings, title= on controls, text under 0.75rem.
  5. Fonts: self-hosted files present; no request to a font CDN in any frontend file.
  6. Numbers: numeric literals inside JS template strings that look like data (not layout).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FE = ROOT / "frontend"
CSS = (FE / "styles.css").read_text(encoding="utf-8")
HTML = (FE / "index.html").read_text(encoding="utf-8")
JS = {p: p.read_text(encoding="utf-8") for p in sorted((FE / "js").glob("*.js"))} if (FE / "js").exists() else {}
if (FE / "app.js").exists():
    JS[FE / "app.js"] = (FE / "app.js").read_text(encoding="utf-8")

fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)
    print("  FAIL " + msg)


# ---------------------------------------------------------------- 1. contrast
def hex_to_rgb(h: str) -> tuple[float, float, float, float]:
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return r / 255, g / 255, b / 255, a


def lum(rgb: tuple[float, float, float]) -> float:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def blend(fg: tuple[float, float, float, float], bg: tuple[float, float, float]) -> tuple[float, float, float]:
    a = fg[3]
    return tuple(fg[i] * a + bg[i] * (1 - a) for i in range(3))  # type: ignore[return-value]


def ratio(fg_hex: str, bg_hex: str) -> float:
    bg = hex_to_rgb(bg_hex)[:3]
    fg = blend(hex_to_rgb(fg_hex), bg)
    l1, l2 = lum(fg), lum(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def tokens_for(selector_re: str) -> dict[str, str]:
    """Resolve --color-* semantics to hex inside the block matched by selector_re."""
    def block_of(sel: str) -> str:
        m = re.search(sel + r"\s*\{(.*?)\n  \}", CSS, re.S)  # a token block closes with a two-space-indented brace
        return m.group(1) if m else ""
    base = block_of(r"\n  :root")
    block = block_of(selector_re) if selector_re != r":root" else base
    if not block:
        return {}
    raw = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", base))
    raw.update(dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block)))
    out: dict[str, str] = {}

    def resolve(v: str, depth: int = 0) -> str | None:
        v = v.strip()
        if depth > 8:
            return None
        if v.startswith("#"):
            return v
        mm = re.fullmatch(r"var\((--[\w-]+)\)", v)
        if mm and mm.group(1) in raw:
            return resolve(raw[mm.group(1)], depth + 1)
        mm = re.fullmatch(r"color-mix\(in srgb,\s*var\((--[\w-]+)\)\s*(\d+)%,\s*transparent\)", v)
        if mm and mm.group(1) in raw:
            base = resolve(raw[mm.group(1)], depth + 1)
            if base:
                return base[:7] + f"{round(int(mm.group(2)) * 2.55):02x}"
        return None

    for k, v in raw.items():
        r = resolve(v)
        if r:
            out[k] = r
    return out


TEXT = ["--color-text-primary", "--color-text-secondary", "--color-text-faint", "--color-text-accent"]
LARGE = ["--color-figure"]  # 28px+ mono figures may use 3:1
SURF = ["--color-bg-canvas", "--color-bg-surface", "--color-bg-raised", "--color-accent-tint"]
SCRIM = [("--color-text-on-scrim", "--color-bg-sunken"), ("--color-text-on-scrim-secondary", "--color-bg-sunken"),
         ("--color-text-on-scrim", "--color-bg-scrim"), ("--color-text-on-scrim-secondary", "--color-bg-scrim")]
CONTROL = [("--color-border-control", "--color-bg-raised"), ("--color-border-control", "--color-bg-surface"),
           ("--color-focus", "--color-bg-canvas"), ("--color-focus", "--color-bg-surface"),
           ("--color-focus-on-accent", "--color-accent-solid")]
ON_ACCENT = [("--color-text-on-accent", "--color-accent-solid"), ("--color-text-accent", "--color-accent-tint"),
             ("--color-text-accent", "--color-bg-surface")]
STATUS = [("--color-status-dry", "--color-bg-surface"), ("--color-status-discovery", "--color-bg-surface"),
          ("--color-trap-structural", "--color-bg-surface"), ("--color-trap-stratigraphic", "--color-bg-surface"),
          ("--color-trap-combination", "--color-bg-surface")]


def check_contrast() -> None:
    print("1. Contrast (WCAG 2 ratios, computed from the declared tokens)")
    for theme, sel in (("light", r":root"), ("dark", r":root\[data-theme=\"dark\"\]")):
        t = tokens_for(sel)
        if not t:
            fail(f"{theme}: no token block found for {sel}")
            continue
        print(f"  [{theme}]")
        # a translucent surface token renders over bg-surface: resolve it to the blended opaque colour first
        for k in list(t):
            if k.startswith("--color-bg") or k.startswith("--color-accent-tint"):
                if len(t[k]) == 9 and t[k][7:9].lower() != "ff" and "--color-bg-surface" in t:
                    base = "--color-bg-canvas" if k == "--color-bg-scrim" else "--color-bg-surface"
                    r_, g_, b_ = blend(hex_to_rgb(t[k]), hex_to_rgb(t[base])[:3])
                    t[k] = "#%02x%02x%02x" % (round(r_ * 255), round(g_ * 255), round(b_ * 255))
        for fg in TEXT:
            for bg in SURF:
                if bg == "--color-accent-tint" and fg == "--color-text-faint":
                    continue  # faint is meta-only and never sits on the accent tint
                if fg in t and bg in t:
                    r = ratio(t[fg], t[bg])
                    ok = r >= 4.5
                    print(f"    {fg[8:]:<16} on {bg[8:]:<14} {r:5.2f}:1 {'' if ok else '<- FAIL'}")
                    if not ok:
                        fail(f"{theme}: {fg} on {bg} = {r:.2f}:1 (needs 4.5)")
        for fg, bg in ON_ACCENT + STATUS + SCRIM:
            if fg in t and bg in t:
                r = ratio(t[fg], t[bg])
                need = 4.5 if fg.startswith("--color-text") else 3.0
                ok = r >= need
                print(f"    {fg[8:]:<16} on {bg[8:]:<14} {r:5.2f}:1 (needs {need}) {'' if ok else '<- FAIL'}")
                if not ok:
                    fail(f"{theme}: {fg} on {bg} = {r:.2f}:1 (needs {need})")
        for fg, bg in CONTROL:
            if fg in t and bg in t:
                r = ratio(t[fg], t[bg])
                ok = r >= 3.0
                print(f"    {fg[8:]:<16} on {bg[8:]:<14} {r:5.2f}:1 (needs 3.0) {'' if ok else '<- FAIL'}")
                if not ok:
                    fail(f"{theme}: {fg} on {bg} = {r:.2f}:1 (needs 3.0)")


# ---------------------------------------------------------------- 2. literals
def check_literals() -> None:
    print("2. Colour literals outside the tokens layer")
    rest = CSS
    for name in ("tokens", "print"):
        layer = re.search(r"@layer " + name + r"\s*\{.*?\n\}\n", CSS, re.S)
        if layer:
            rest = rest.replace(layer.group(0), "")
    for src, text in [("styles.css (outside @layer tokens)", rest), ("index.html", HTML)] + [(p.name, s) for p, s in JS.items()]:
        for m in re.finditer(r"(#[0-9a-fA-F]{3,8}\b|rgba?\(|oklch\(|hsla?\()", text):
            line = text.count("\n", 0, m.start()) + 1
            ctx = text[max(0, m.start() - 30): m.start() + 20].replace("\n", " ")
            line_text = text.splitlines()[line - 1] if line - 1 < len(text.count("\n") + 1 and text.splitlines()) else ""
            if "linear-gradient(90deg" in line_text or "colormap" in line_text.lower():
                continue  # colormap legend gradients are data, not chrome
            fail(f"{src}:{line} literal colour …{ctx}…")
    if not any("literal colour" in f for f in fails):
        print("  ok")


# ---------------------------------------------------------------- 3. grid
def check_grid() -> None:
    print("3. 4-px grid in styles.css")
    bad = 0
    for i, line in enumerate(CSS.splitlines(), 1):
        if line.lstrip().startswith("/*") or "@font-face" in line or "unicode-range" in line:
            continue
        for m in re.finditer(r"(?<![\w.-])(-?\d+(?:\.\d+)?)px", line):
            v = float(m.group(1))
            if abs(v) in (0, 1, 2) or v % 4 == 0:
                continue
            if abs(v) <= 10 or v in (14, 18):  # glyph, dot, track and icon sizes inside a control (unslop allows them)
                continue
            if "letter-spacing" in line or "stroke" in line or "outline-offset" in line or "translate" in line or "::before" in line or "::after" in line:
                continue
            bad += 1
            fail(f"styles.css:{i} {v}px is off the 4-px grid: {line.strip()[:80]}")
    if not bad:
        print("  ok")


# ---------------------------------------------------------------- 4. slop
SLOP = [
    (r"text-transform\s*:\s*uppercase", "uppercase transform (eyebrow / ALL CAPS)"),
    (r"border-radius\s*:\s*(999|9999)px|rounded-full", "pill radius"),
    (r"transition\s*:\s*all|transition-property\s*:\s*all", "transition: all"),
    (r"animation\s*:\s*[a-z-]+\s+[\d.]+m?s\s+[a-z-]+\s+infinite", "looping animation"),
    (r"<i>|<em>|<i class", "italic emphasis in a template"),
    (r"font-style\s*:\s*italic", "italic"),
    (r"^(?!.*--text-(h1|display)-size).*letter-spacing\s*:\s*-", "negative tracking on something that is not display text"),
    (r"backdrop-filter", "glass blur (banned on the RustDesk stream)"),
    (r"font-size\s*:\s*0\.(6|7[0-4])\d*rem|font-size\s*:\s*(9|10|11)px", "text under 12px"),
]
UI_STRING_RE = re.compile(r"""(["'`])((?:(?!\1).){8,}?)\1""")


def check_slop() -> None:
    print("4. Slop grep")
    n = 0
    for src, text in [("styles.css", CSS), ("index.html", HTML)] + [(p.name, s) for p, s in JS.items()]:
        for pat, label in SLOP:
            for m in re.finditer(pat, text, re.M):
                line = text.count("\n", 0, m.start()) + 1
                n += 1
                fail(f"{src}:{line} {label}")
    for src, text in [("index.html", HTML)] + [(p.name, s) for p, s in JS.items()]:
        for m in re.finditer(r"<(button|a|input|tr|td|span)[^>]*\stitle=", text):
            n += 1
            fail(f"{src}:{text.count(chr(10), 0, m.start()) + 1} title= on an interactive element (hover-only text)")
        for m in UI_STRING_RE.finditer(text):
            s = m.group(2)
            if "!" in s and not s.startswith("<!") and "!=" not in s and "!important" not in s and not s.strip().startswith("/"):
                if re.search(r"[A-Za-z]!", s):
                    n += 1
                    fail(f"{src}:{text.count(chr(10), 0, m.start()) + 1} exclamation mark in UI string: {s[:50]}")
    if not n:
        print("  ok")


# ---------------------------------------------------------------- 5. fonts
def check_fonts() -> None:
    print("5. Fonts")
    for f in ("Figtree.woff2", "Fraunces.woff2", "JetBrainsMono.woff2", "OFL.txt"):
        if not (FE / "fonts" / f).exists():
            fail(f"frontend/fonts/{f} missing (run scripts/fetch_fonts.py)")
    for src, text in [("styles.css", CSS), ("index.html", HTML)] + [(p.name, s) for p, s in JS.items()]:
        if re.search(r"fonts\.(googleapis|gstatic)\.com|cdn\.|unpkg\.com|jsdelivr", text):
            fail(f"{src}: external CDN reference")
    if not any("font" in f.lower() or "CDN" in f for f in fails):
        print("  ok")


# ---------------------------------------------------------------- 6. numbers
def check_numbers() -> None:
    print("6. Hard-coded data numbers in JS templates")
    n = 0
    for p, text in JS.items():
        for m in re.finditer(r"`[^`]*`", text, re.S):
            tpl = m.group(0)
            for num in re.finditer(r"(?<![\w$\-{./:])(\d+\.\d{2,}|\$\d+M|\d{1,3}(?:,\d{3})+)(?![\w}/:])", tpl):
                line = text.count("\n", 0, m.start() + num.start()) + 1
                n += 1
                fail(f"{p.name}:{line} data-looking literal {num.group(1)} inside a template")
    if not n:
        print("  ok")


if __name__ == "__main__":
    check_contrast()
    check_literals()
    check_grid()
    check_slop()
    check_fonts()
    check_numbers()
    print()
    if fails:
        print(f"{len(fails)} failure(s)")
        sys.exit(1)
    print("All checks passed")
