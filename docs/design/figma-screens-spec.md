# Exploration Copilot — implementation spec from Figma

Source: Figma file `B25vcac1PnOk2b6ETax86g`, page **"Screens"** (17:13) — the source of truth. Desktop frames are 1440×900, phone frames 390×844.
Everything below was read from `get_design_context` (React/Tailwind reference code with Figma node ids), `get_variable_defs`, and the PNG screenshots in this folder (`<nodeid>.png`). Raw context JSON + parsed outlines are in `ctx/`. "Screens v2" screenshots used only for the diff section are in `v2/`.

Conventions: positions are `x,y` inside the parent (px); sizes `w×h`; padding `p`, `px/py`; radius `r`. Colours quoted as the Figma variable name with its resolved value.

---

## 1. Design tokens

### 1.1 Colour variables (hex + alpha)

| Variable | Value | Notes |
|---|---|---|
| `color/bg/canvas` | `#14110f` | page background |
| `color/bg/sunken` | `#0c0a09` | map / section panel fill |
| `color/bg/surface` | `#211a16` | memo modal fill |
| `color/bg/raised` | `#2e2520` | idle Send button on Welcome |
| `color/bg/scrim` | `#14110f` @ 0.90 (`#14110fe5`) | labels, time slider, view toggle, readouts |
| `color/bg/sheet` | `rgba(33,26,22,0.92)` | floating evidence card |
| `color/border/subtle` | `#3d322b` | table rules, stat dividers, pending tool-step ring |
| `color/glass/fill-subtle` | `#fff4e4` @ 0.06 (`#fff4e40f`) | header, chips, tab bar, scorecard rows |
| `color/glass/fill` | `#fff4e4` @ 0.10 (`#fff4e41a`) | copilot/evidence panels, chat bubble, bar tracks |
| `color/glass/fill-strong` | `#fff4e4` @ 0.14 (`#fff4e424`) | composer, selected segment/tab |
| `color/glass/stroke` | `#fff4e4` @ 0.14 (`#fff4e424`) | default 1px border |
| `color/glass/stroke-strong` | `#fff4e4` @ 0.22 (`#fff4e438`) | composer, selected segment, memo |
| `color/text/primary` | `#ede6da` | |
| `color/text/secondary` | `#b3a594` | body copy in answers |
| `color/text/faint` | `#9c8d7e` | placeholders, overlines, axis labels |
| `color/text/accent` | `#e8bd62` | overlines in answers, GCoS numbers, citation labels |
| `color/text/on-accent` | `#14110f` | text on ochre buttons |
| `color/icon/default` | `#ede6da` | |
| `color/icon/muted` | `#b3a594` | also neutral bar fills |
| `color/accent/primary` | `#d9a441` | ochre: primary buttons, active toggle, citation ID chip, selected row border |
| `color/accent/tint` | `#d9a441` @ 0.16 (`#d9a44129`) | citation pill bg, recommendation box, highlighted rows |
| `color/accent/border` | `#d9a441` @ 0.50 (`#d9a44180`) | citation pill border, busy composer, highlighted row |
| `color/status/discovery` | `#8fa67a` | sage: good scores, positive EMV, confirmed |
| `color/status/discovery-bg` | `rgba(143,166,122,0.18)` | done tool-step indicator, verdict card, reveal event |
| `color/status/dry` | `#d47a50` | terracotta: dry wells, fault lines |
| `color/status/warning` | `#d9a441` | = accent |
| `color/status/warning-bg` | `rgba(217,164,65,0.10)` | |
| `color/status/warning-border` | `rgba(217,164,65,0.40)` | |
| `color/status/error` | `#e0705a` | negative EMV, fizz-gas card, "no lead" chip |
| `color/status/error-bg` | `rgba(224,112,90,0.10)` | |
| `color/status/error-border` | `rgba(224,112,90,0.40)` | |
| `color/status/info` | `#6fa3a0` | teal |
| `color/trap/structural` | `#6fa3a0`; border `rgba(111,163,160,0.40)` | |
| `color/trap/stratigraphic` | `#d9a441`; border `rgba(217,164,65,0.40)`; bg `rgba(217,164,65,0.14)` | |
| `color/trap/combination` | `#d47a50`; border `rgba(212,122,80,0.40)` | |
| `color/instrument/grid` | `#ede6da` @ 0.40 (`#ede6da66`) | cross grid, locator grid |
| `color/instrument/guide` | `#ede6da` @ 0.55 (`#ede6da8c`) | crosshair guides, readout border, tile borders |
| `color/instrument/leader` | `#ede6da` @ 0.75 (`#ede6dabf`) | leader lines |
| `color/instrument/ring` | `#d9a441` @ 0.80 (`#d9a441cc`) | dashed lead ring |
| `color/instrument/measure` | `#d9a441` | "section below" tag, locator section line |

### 1.2 Spacing & radius variables

`space-1` 4 · `space-2` 8 · `space-3` 12 · `space-4` 16 · `space-6` 24
`radius-xs` 6 · `radius-sm` 8 · `radius-md` 12 · `radius-lg` 20 · `radius-full` 999
Other hard-coded radii seen: 4 (tiny tags), 5 (citation ID chip), 7 (citation pill), 9 (toggle/tab segment), 10 (map lead label, legend, scale, readout, formula, checked rows), 14 (tool-steps box, evidence card), 16 (stat cards, prediction/verdict cards, compact composer, recommendation box), 17 (34px round buttons), 18 (header, 36px round buttons, survey-stats bar, chat bubble), 24 (memo modal).

### 1.3 Type styles

Fonts: **Fraunces** (variable; `font-variation-settings: "SOFT" 0, "WONK" 1`), **Figtree**, **JetBrains Mono**.

| Style | Family / weight | Size / line-height / tracking |
|---|---|---|
| Display/Desktop | Fraunces Light 300 | 56 / 60 / −2% (code: −1.12px) |
| Heading/H1 Desktop | Fraunces Regular 400 | 40 / 46 / −1% (code: −0.4px) |
| Heading/H2 Desktop | Fraunces Regular 400 | 28 / 34 / −0.5% (code: −0.14px) |
| Heading/H3 Desktop | Fraunces SemiBold 600 | 20 / 26 / 0 |
| Body/Large | Figtree Regular 400 | 16 / 24 |
| Body/Default | Figtree Regular 400 | 14 / 21 |
| Body/Strong | Figtree SemiBold 600 | 14 / 21 |
| Label/Default | Figtree Medium 500 | 13 / 16 |
| Label/Button | Figtree SemiBold 600 | 14 / 16 |
| Caption | Figtree Regular 400 | 12 / 16 |
| Mono/Data | JetBrains Mono Regular 400 | 13 / 18 |
| Mono/Small | JetBrains Mono Regular 400 | 12 / 16 |
| Mono/Overline | JetBrains Mono Medium 500 | 11 / 14 / +8% (0.88px), UPPERCASE |

Ad-hoc sizes used in frames (no named style): Fraunces Regular 18 (brand wordmark), Fraunces Regular 24 (memo recommendation), Fraunces Light 30 (memo impact stats), Fraunces Light 40 (business-case impact stats), JetBrains Mono Medium 22 (welcome survey stats), JetBrains Mono Medium 26 (GCoS headline number, evidence-card value), JetBrains Mono Medium 18 (EMV values), JetBrains Mono 7.2–7.44 (mini well-log labels), mono 12 with tracking 4.8px (readout "spaced" ruler line).

### 1.4 Effects

| Style | Definition |
|---|---|
| Glass/Panel | background blur 32; inner shadow `#FFF4E4` @0.10, 0 1 0 0; drop shadow `#000` @0.35, 0 16 48 0. (Reference code renders panels with `backdrop-blur 16px` + `shadow 0 16 48 rgba(0,0,0,.35)` + `inset 0 1 0 rgba(255,244,228,.10)`) |
| Glass/Chip | background blur 16; inner shadow `#FFF4E4` @0.10, 0 1 0 0 |
| Elevation/Floating | drop `#000` @0.50, 0 24 64 0 + drop `#000` @0.30, 0 2 6 0 (memo modal, evidence card) |
| Header shadow | drop 0 16 24 rgba(0,0,0,.35), backdrop blur 16 |
| Accent glow | drop 0 0 14 rgba(217,164,65,.45) (active tool-step ring, evidence highlight box); scan line 0 0 14 rgba(217,163,64,.70) |
| Texture/Grain | full-frame overlay, 50×50 tile (`grain` asset), `mix-blend-mode: overlay`, opacity 5% |
| Workspace backdrop | blurred map image 1600×1280 at (−80,−190), blur 15px, opacity 18% |
| Welcome backdrop | map 1520×1216 at (−40,−150), blur 3px, opacity 55% + radial vignette (center transparent → rgba(20,17,15,.8) at edge) + vertical gradient rgba(20,17,15,.35) → .80 @60% → .95 |
| Map panel "Top shade" | 920×96 gradient rgba(20,17,15,.9) → 0 at the top of the map |

### 1.5 Icons

All icons are 24px-grid, 1.5px stroke. `Icon/UI/*` are Lucide (plus, layers, mic, arrow-up, sparkle, chevron-down, file-text, eye-off, share, download, x, check, alert-triangle). `Icon/Geo/*` are custom geology icons: section, well-discovery, well-dry, prospect (untested), combination, channel (stratigraphic), anticline (four-way closure), fizz-gas, analog (similarity), reservoir, seal, charge. Rendered at 12 (chevron), 14 (segment/pill/tag), 15 (mode toggle), 16 (buttons, scorecard rows), 18 (well markers, banners), 32 (empty states).

### 1.6 Image assets (`_Image assets` frame 17:646, hidden, on page "Screens")

Rendered engine outputs the screens embed. Rounded-rect 400×320 placeholders: `map_interp`, `map_base`, `section_il1110`, `section_il1040`, `map_vpvs`, `map_avo`, `section_il1080`. Frames 400×300: `volume`, `stack_l3`, `grain`, `sm_vpvs`, `sm_sand`, `sm_avo_diff`. In the screens the map is placed as a 992×793.6 image at (−73,−246) inside the 920×468 map panel (so it is cropped/zoomed); the section as 888×388.5 at (15,−30) inside the 920×324 section panel; volume render 435.789×276; stack render 200.323×276; small multiples 140×112 each.

---

## 2. Desktop shell (common to D2–D8, D10)

Canvas 1440×900, bg `bg/canvas`, grain overlay on top of everything.

| Region | x | y | w | h | r | Fill / border |
|---|---|---|---|---|---|---|
| App header | 16 | 12 | 1408 | 56 | 18 | glass fill-subtle + blur 16, stroke, header shadow, inset highlight |
| Map panel | 16 | 80 | 920 | 468 | 20 | bg/sunken, stroke, overflow clip |
| Bottom-left panel (section / volume / stack / compare / business case / blind test) | 16 | 560 | 920 | 324 | 20 | bg/sunken, stroke |
| Copilot panel | 948 | 80 | 476 | 476 | 20 | glass fill (0.10) + blur 16, stroke, panel shadow; p 12 (v) × 18 (h), column gap 10 |
| Evidence panel | 948 | 566 | 476 | 318 | 20 | glass fill (0.10) + blur 16, stroke, panel shadow; p 12 (v) × 14 (h), column gap 10 |

Gutters: 16 outside; 12 between the two columns (936→948) and between map and bottom panel (548→560); 10 between copilot and evidence (556→566); 16 bottom. Column split 920 : 476.

### 2.1 App header (component `AppHeader`, 23:692; variant `mode = Geoscientist | Executive`)
Row, `pl 14 pr 8`, gap 12, three zones:
1. **Brand** (flex 1, gap 10): logo 28×28 · "Exploration Copilot" Fraunces 18 primary · **Block** chip (`Block SK-07` Mono/Small primary + chevron-down 12; `pl 10 pr 8 py 5`, r 8, stroke border) · **Health** (7px dot teal `status/info` + `Gemma 4 · 0.8 s` Mono/Small secondary, gap 6).
2. **ModeToggle** (23:652): container glass fill-subtle, stroke, p 3, gap 2, r 12. Two segments `pl 12 pr 14 py 6`, r 9, gap 6, icon 15 + Label/Default: **Geoscientist** (Icon/Geo/section) and **Executive** (Icon/UI/file-text). Active segment: `accent/primary` bg, text `text/on-accent`; inactive: transparent, text secondary.
3. **Actions** (flex 1, justify end, gap 8): **Blind well test** (eye-off 16 + Label/Button primary; glass fill 0.10, stroke-strong, `pl 12 pr 14 py 8`, r 12) · **Committee memo** (file-text 16 + Label/Button on-accent; accent bg, same padding, r 12). Active Blind-well-test state (D8): bg `accent/tint`, border `accent/primary`.

### 2.2 Map panel internals (Opportunity map)
- Map image 992×793.6 at (−73,−246). Four `instrument/cross grid` tiles 448×320 at (−1,−1), (447,−1), (−1,319), (447,319): one 7px cross every 64px = 8 IL/XL bins. Top shade 96px.
- **Panel head** at (15,11), gap 10: "Opportunity map" H3 + `IL 1000–1159 · XL 2000–2199` Mono/Small faint.
- **Attribute switcher** at (15,45): scrim bg + blur 8, stroke, p 4, gap 2, r 12. Segments (`Segment` 7:116/7:118) `px 12 py 7` r 8 Label/Default: `Sand probability` · `Vp/Vs` · `Far − Near` · `P-impedance` · `Structure` · `Faults`. Selected: glass fill-strong + stroke-strong, text primary; unselected text secondary.
- **Time slider** at (603,9), 300×(32): scrim, stroke, r 12, `pl 12 pr 10 py 7`, gap 10: `TWT` Mono/Overline faint · track (flex, h 18: rail 150×3 r 2 glass fill-strong at y 7.5; window 52×3 accent at x 58; knob 14×14 at x 75, y 2) · `2004 ms` Mono/Small primary.
- **Legend** at (556,423): stroke, `px 12 py 7`, r 10, gap 12, panel shadow, scrim+blur. Items gap 5: 12×3 swatch (r 1) + Caption secondary: `Structural` (#6fa3a0) · `Stratigraphic` (#d9a441) · `Combination` (#d47a50) · `Fault` (12×2, #d47a50).
  - Vp/Vs variant (D4, D5) at (537,423): `Vp/Vs` Caption + 120×6 ramp (r 3) + `1.73 gas → 2.30 brine` Mono/Small faint.
- **Scale** at (11,425): `px 10 py 6`, r 10, gap 10: north arrow 12×16 · bar 64×5 · `320 m` Mono/Small secondary.
- **Lead ring** `instrument/ring` 143.88×143.88 at (697.02,227.04): dashed ring, colour `instrument/ring`; diameter = lead equivalent radius (carries data). Centre dot inside.
- **Well markers** (gap 6): icon 18 + label (scrim, `px 6 py 2`, r 6, Mono/Small primary). `meranti-1` (well-discovery, sage) at (364.4,141.8); `seraya-1` (well-dry, terracotta) at (116.4,389.8).
- **Map lead label** (12:3xx instances): scrim + blur 8, border = trap border colour, `px 10 py 8`, r 10, gap 4. Row 1 (gap 8): trap icon 14 + `L1` Mono/Data primary + `COMBINATION` Mono/Overline in trap colour. Row 2 (gap 8, Mono/Small): `GCoS` faint · `0.25` accent · `0.64 km²` secondary.
  - L1 · COMBINATION · GCoS 0.25 · 0.64 km² at (404.72,164.42)
  - L3 · STRATIGRAPHIC · GCoS 0.22 · 0.34 km² at (749,218.98) (739 in D6/D7)
  - L5 · UNCLASSIFIED (anticline icon, structural teal) · GCoS 0.03 · 0.10 km² at (165.4,318.8) (D2, D7 only)
- `IL 1080 · section below` tag (D3/D4) at (11,126.8): scrim, `px 6 py 2`, r 4, Mono/Small in `instrument/measure`; paired with a horizontal `instrument/guide` crosshair at y 150.8.

### 2.3 Bottom-left panel chrome
- Header band 44px (bg/sunken) covering the top of the image; **Panel head** at (15,11): H3 title + Mono/Small faint subtitle (gap 10).
- `instrument/view toggle` (38:900) at (696,7): scrim, stroke, p 3, gap 2, r 12; Segments `Section` · `Volume` · `Stack` (`px 12 py 7` r 8). "Switches the bottom-left panel between the 2D section, the wireframe survey volume and the exploded risk stack for the selected lead."
- Section view: image 888×388.5 at (15,−30); **Time axis** at (21,55), column gap 40, Mono/Small faint: `1900 ms` `1950 ms` `2000 ms` `2050 ms` `2100 ms`; lead tags scrim + 1px trap-colour border `px 6 py 2` r 6 Mono/Small: `L1` at (356.84,139), `L3` at (784.44,139); `fault` tag (terracotta text) at (580.44,63); well path 2×260 primary at (413.6,51) with `meranti-1` label at (331.6,51).

### 2.4 Copilot panel internals
- **Head** (gap 10): Core orb 31.2×31.2 (gradient sphere asset) + title column: `Copilot` H3, `Answers cite measured evidence` Caption secondary.
- **Chat message** (user): right-aligned bubble, glass fill 0.10, stroke, `px 16 py 9`, radii tl 18 / tr 18 / br 6 / bl 18, Body/Large primary.
- **Answer** block (column gap 7): Mono/Overline in `text/accent` section headings; Body/Default secondary paragraphs with **Body/Strong primary** spans for key terms; **Citations** row (wrap, gap 6).
- **CitationPill** (23:875; `state = Default | Active`): `accent/tint` bg, `accent/border`, `pl 3 pr 8 py 3`, r 7, gap 6: ID chip (accent bg, `px 5`, r 5, Mono/Small on-accent, e.g. `E3`) + label Mono/Small accent (e.g. `Vp/Vs 1.745`). Active: solid accent bg, no border (D4 after clicking E3).
- Spacer (flex 1) pushes the **Composer** to the bottom: glass fill-strong, stroke-strong, r 16, `pl 14 pr 6 py 6`, gap 8: placeholder `Ask a follow-up…` Body/Default faint · Mic button 34 round (glass fill-subtle, mic 16) · Send button 34 round accent (arrow-up 16). **Busy state** (D3): border `accent/border`, text shows the sent question in primary, Send shows an 11×11 r 3 stop square in on-accent.

### 2.5 Evidence panel internals
- **EvidenceTabs** (23:802; `active = Scorecard | Devils advocate | Similar traps`): glass fill-subtle, p 3, gap 4, r 12. Tabs `pl 10 pr 12 py 6`, r 9, gap 6, icon 14 + Label/Default: `Scorecard` (anticline) · `Devil's advocate` (fizz-gas) · `Similar traps` (analog). Active: glass fill-strong + stroke-strong, text primary.
- **GCoS line** (`px 4`, gap 10): lead column (`L3 · East channel` H3 + `Weakest element: trap 0.55` Caption secondary) · `0.22` JetBrains Mono Medium 26 accent · `GCOS` Mono/Overline faint.
- **Scorecard** (column gap 6) of **Scorecard row** (23:888 ok / 23:901 warning): `px 12 py 7`, r 12, gap 4. Top row gap 10: status light 10×10 · geo icon 16 · label Body/Strong w 64 · track h 6 r 3 glass fill 0.10 with fill (sage for good, warning ochre for weak; fill ≈ 212px × score: 170 for 0.80, 110 for 0.55) · value Mono/Data (primary, or warning colour on weak rows). Warning rows use warning-bg/-border and add a **Reason row** `pl 46` Caption secondary. Selected/hovered row (D4 Charge): border `accent/primary`.
  - Reservoir 0.80 (sage) · Trap 0.55 "No structural closure; channel geometry only" · Seal 0.60 "Relies on up-dip clay plug, not yet imaged" · Charge 0.85 (sage).

---

## 3. Desktop frames

### D1 · Welcome (18:652) — `18-652.png`
Purpose: first screen, empty session; invites the first question.
Layout: no panels; header as §2.1 (Geoscientist active). Welcome backdrop (§1.4). **Hero** column at x 293.5, y 150, gap 28, centre-aligned:
- `CoreOrb` state Idle 120×120.
- Headline (gap 12): `What is the opportunity in this block?` Display/Desktop primary; sub `I have measured every sand body in the seismic and checked it against the wells. Ask me anything; every answer shows its evidence.` Body/Large secondary, w 620, centred.
- **Composer** (9:62, state Idle) w 680: glass fill-strong + blur 16, stroke-strong, r 20, p 16, column gap 14, header-style drop shadow. Placeholder `Ask about a lead, a well or the whole survey…` Body/Large faint. Actions row gap 8: `Attach` chip (plus 16 + Label/Default secondary; glass fill-subtle, stroke, `pl 10 pr 12 py 6`, r full) · `Map view` chip (layers 16) · spacer · Mic 36 round glass fill-subtle (mic 18) · Send 36 round `bg/raised` (arrow-up 18) — idle Send is NOT accent.
- **Prompts** w 720, wrap, gap 10, centred — `SuggestedPrompt` (7:102): sparkle 14 + Label/Default primary, glass fill-subtle, stroke, `px 16 py 8`, r full: `What is the geological opportunity, and why?` · `Rank the leads` · `Find similar traps yet to be tested` · `Why did kenari-2 come up dry?`
- **Survey stats** bar at (411.5,783): glass fill-subtle + blur 16, stroke, r 18, `py 14`, panel shadow; cells `px 28`, gap 2, left border `border/subtle` between cells; value JetBrains Mono Medium 22 primary + Caption secondary: `9` seismic volumes · `7` wells, 3 discoveries · `5` leads measured · `1` undrilled opportunity (value in `text/accent`).
States implied: idle composer; chips hover; prompts clickable (send as the user message → D3).

### D2 · Workspace · Geoscientist (26:1355) — `26-1355.png`
Purpose: the answered state of "What is the geological opportunity here, and why?" with the survey volume view.
- Map: Sand probability selected; labels L1, L3, L5; ring on L3; trap legend.
- Bottom-left **Survey volume** panel: head `Survey volume` + `IL 1000–1159 · XL 2000–2199 · 1930–2080 ms`; view toggle **Volume** active. `view/volume` (39:791) 888×276 at (15,43): wireframe render 435.789×276 at (0,0); lead tags (5px dot + scrim label `px 5 py 1` r 4 Mono/Small): `L1 · 0.25` (179.88,132.99) · `L2 · 0.23` (184.05,59.42) · `L3 · 0.22` accent (261.7,174.83) · `L4 · 0.09` (307.67,113.49) · `L5 · 0.03` (87.71,121.23); axis labels Mono/Small faint: `IL 1000 · XL 2000 · 1930 ms` (184.69,0) · `IL 1159` (10.1,89.41) · `XL 2199` (365.69,85.28) · `2080 ms` (369.69,193.71). **Small multiples** at (451.79,0), gap 8: three tiles (map 140×112 r 4 border `instrument/guide` + `instrument/gradient legend` w 140 gap 6: Mono/Overline secondary label, ramp h 6 r 1, ends Mono/Small faint): `VP/VS` 1.70 gas → 2.25 brine · `SAND PROBABILITY` 0 shale → 1 sand · `FAR − NEAR` −0.013 → +0.013 gas. Caption at (451.79,228) w 420 Mono/Small faint: `Top: reservoir-top pseudo-horizon (top_time). Lower mesh: base where sand_prob ≥ 0.5. Colour: Vp/Vs. Display smoothing σ = 3 bins.`
- Copilot: user `What is the geological opportunity here, and why?`; answer:
  - OPPORTUNITY — `L3 is an **undrilled stratigraphic trap** east of the fault: a sinuous channel sand sealed up-dip by an abandoned, clay-filled loop.` Pills `E1 Sand 0.87` `E2 Sinuosity 1.6`.
  - WHY IT SHOULD HOLD GAS — `Low Vp/Vs and far-stack brightening, the same signature as the **meranti-1** and **kenari-1** discoveries.` Pills `E3 Vp/Vs 1.745` `E4 AVO +3.7σ` `E9 Disc. 1.74`.
  - NEXT STEP — `**Carry L3 forward;** de-risk the up-dip seal first.`
  - Composer idle `Ask a follow-up…`.
- Evidence: Scorecard tab; `L3 · East channel` / `Weakest element: trap 0.55` / `0.22 GCOS`; rows Reservoir 0.80, Trap 0.55, Seal 0.60, Charge 0.85 (§2.5).
Numbers: GCoS L1 0.25, L2 0.23, L3 0.22, L4 0.09, L5 0.03; areas 0.64 / 0.34 / 0.10 km²; TWT 2004 ms; scale 320 m.

### D3 · Copilot at work (26:1723) — `26-1723.png`
Purpose: streaming/loading state while tools run.
- Map: only L3 label; horizontal guide at y 150.8 + `IL 1080 · section below` tag; **scan line** 220×3 r 2 at (658.96,338.98) with ochre glow (animated sweep over L3).
- Bottom-left: `Seismic section · IL 1080` + `loading lead window…`; toggle **Section**; section image with time axis, L1/L3/fault tags, well path (no E3 highlight yet).
- Copilot: user bubble; **Tool steps** box (glass fill-subtle, `px 14 py 12`, r 14, column gap 10) of `ToolStep` (9:17x, `state = Done | Active | Pending`): row gap 10, Indicator 18 round + text column (Label/Default + Mono/Small faint):
  1. Done — `Planned 3 tool calls` / `Gemma 4 · 1.1 s` (indicator discovery-bg with check 12)
  2. Done — `Measured lead L3` / `lead_evidence · 9 facts`
  3. Active — `Comparing with drilled analogs` / `similar_leads · pool: drilled` (indicator 1px `accent/primary` ring + glow 0 0 14 rgba(217,164,65,.45); spinner in screenshot)
  4. Pending — `Writing the answer` / `Gemma 4 · cites facts only` (ring `border/subtle`, all text faint)
  - `FACTS SO FAR` Mono/Overline faint; pills `E1 Sand 0.87` `E2 Sinuosity 1.6` `E3 Vp/Vs 1.745` `E4 AVO +3.7σ` (arrive incrementally).
  - Composer busy (§2.4): text `What is the geological opportunity here, and why?`, stop button.
- Evidence: Scorecard tab; `L3 · East channel` / `Computing chance of success…` / `—` GCOS; **Skeleton** (12:528) p 24, r 20, gap 12: bars 120×10 r 5 · 260×22 r 10 · 332×10 r 5 · 300×10 r 5 · 332×48 r 10 (shimmer).
States: loading (skeleton, scan line, spinner), streaming facts.

### D4 · Evidence linked (27:1313) — `27-1313.png`
Purpose: clicking citation E3 pins its measurement on map and section.
- Map: **Vp/Vs** attribute selected (teal/bronze render); guides: horizontal `instrument/guide` at y 150.8 and y 298.98, vertical at x 767.96 (full-bleed crosshair through the pinned point); **Evidence pin** 16×16 at (746.96,320.98); L1 label only (L3 label hidden behind card). **Evidence card** at (649,119) w 250: `bg/sheet`, border `accent/border`, `px 14 py 12`, r 14, gap 8, Elevation/Floating: top row (ID chip `E3` accent `px 6` r 5 + `VP/VS · LEAD_EVIDENCE` Mono/Overline faint); value `1.745` JetBrains Mono Medium 26 + `inside L3` Caption; three comparison bars (Caption label w 84 · bar h 5 r 3 glass fill with coloured fill · Mono/Small value): `Around L3` 2.272 (muted fill 72px) · `Discovery avg` 1.740 (sage 33.6px) · `Dry-well avg` 2.147 (terracotta 65.6px); note Caption faint w 222 `Mean over the L3 polygon, 1930–2080 ms. Lower than the background, matching both discoveries.` **Readout** `instrument/readout` (38:836) at (11,190.98): scrim, border `instrument/guide`, `px 12 py 10`, r 10, gap 4: `PINNED · E3 · L3 CENTROID` Mono/Overline accent · `IL 1110   XL 2170` Mono/Data primary · `Vp/Vs 1.745   crest 2,034.3 ms` Mono/Small secondary · `1 1 1 0 · 2 1 7 0` Mono/Small faint tracking 4.8 ("ruler texture", repeats the same IL/XL). Legend Vp/Vs variant.
- Bottom-left: `Seismic section · IL 1080` + `E3 highlighted · Vp/Vs window`; **Evidence highlight** 46×44 r 8 at (773.44,159), 1px accent border + glow; `E3 · measured here` accent tag (`px 6 py 2` r 6, Mono/Small on-accent) at (623.44,171); **Well log** mini card at (426.6,51) (component scaled 0.6: p 6, r 7.2, gap 4.8; head icon 8.4 + `meranti-1` 7.2px; two tracks `GR`/`RES` 33.6×180 r 3.6 glass fill-subtle with horizontal rules at 45/90/135 and a sand band 16.38 tall at y 81.84 in accent tint; curves; axis labels; verdict chip `44 Ω·m · pay` accent tint / text accent).
- Copilot: same answer as D2 but citation **E3 is Active** (solid accent).
- Evidence: Scorecard as D2; Charge row shows accent border (selected/hover).
Numbers: E3 Vp/Vs 1.745 inside L3; around 2.272; discovery avg 1.740; dry avg 2.147; IL 1110 XL 2170; crest 2,034.3 ms; window 1930–2080 ms.

### D5 · Devil's advocate (27:1688) — `27-1688.png`
Purpose: "What could make L3 wrong?" — alternatives and the risk stack.
- Map: Vp/Vs selected; L3 label only.
- Bottom-left **Risk stack · L3** + `each layer = one chance factor`; toggle **Stack** active. `view/stack` (39:843) 888×276 at (15,43): exploded-layer render 200.323×276; four `instrument/leader label` (38:812; anchor dot 5, leader 56×1 `instrument/leader`, text `pl 8` gap 2: name Label/Default primary + value Mono/Small secondary) at x 187.09, y 44.88 / 96.96 / 149.02 / 201.11: `Seal` P 0.60 · schematic surface · `Trap` P 0.55 · pinch-out, no closure · `Reservoir` P 0.80 · sand 0.87 · Vp/Vs 1.745 · `Charge` P 0.85 · schematic surface. **Product** block at (600,40), gap 6: `L3 · STRATIGRAPHIC · UNDRILLED` Mono/Overline accent · `0.80 × 0.55 × 0.60 × 0.85` Mono/Data secondary · `GCoS 0.224` H2 · Body/Default secondary w 270 `Weakest link: trap. The engine measures 0.1 ms of structural closure, so gas stays only if the up-dip shale (sand 0.25) seals the channel.` Footnote at (600,228) w 270 Mono/Small faint `Trap, reservoir: engine surfaces. Seal, charge: schematic. Rings: Vp/Vs < 1.80.`
- Copilot: user `What could make L3 wrong?`; answer: BEST ALTERNATIVE: FIZZ GAS — `A few percent of gas in water gives the same low Vp/Vs and far-stack brightening as a commercial accumulation. Nothing in the seismic alone rules it out.` pills `E3 Vp/Vs 1.745` `E4 AVO +3.7σ`; SECOND: SEAL FAILS UP-DIP — `The clay plug that closes L3 is **inferred** from channel shape, not imaged. If it is sandy, gas leaks north.` pills `E2 Sinuosity 1.6` `E7 Seal 0.60`; CHEAPEST TEST — `Model the AVO response at **meranti-1** (known pay) and compare with L3 on the UltraFar stack.`
- Evidence: **Devil's advocate** tab active; cards (`px 12 py 10`, r 12, gap 6; top row icon 16 + Body/Strong flex + Mono/Small delta): `Fizz gas` (error-bg/border; `GCoS 0.22 → 0.10` in error) / `Same signal, no commercial gas. If true, charge drops 0.85 → 0.40.` · `Up-dip seal leaks` (warning-bg/border; `GCoS 0.22 → 0.12`) / `Clay plug inferred from geometry only. If sandy, trap drops 0.55 → 0.30.` · `De-risk before drilling` (glass fill-subtle, check icon) / Mono/Small lines `1 AVO model at meranti-1 vs L3 on UltraFar` · `2 Map amplitude conformance to the channel edge`.
Numbers: P seal 0.60, trap 0.55, reservoir 0.80, charge 0.85 → GCoS 0.224; closure 0.1 ms; up-dip sand 0.25; Vp/Vs ring threshold 1.80; alternatives GCoS 0.10 / 0.12; charge 0.85→0.40; trap 0.55→0.30.

### D6 · Similar untested traps (29:1724) — `29-1724.png`
Purpose: analog search against drilled leads.
- Map: Sand probability; L1 and L3 labels; dashed **Analog link** (237.905 wide) from L1 to L3 with **Similarity badge** at (512.84,241.7): accent bg, `px 8 py 4`, r 8, analog icon 14 + `0.45 match` Mono/Small on-accent.
- Bottom-left **Compare panel**: `L3 vs drilled analog L1` + `standardised features · cosine similarity 0.45`; no view toggle. **Feature table** at (15,51) w 888: header row (glass fill-subtle, border-b subtle, `px 10 py 7`, Mono/Overline faint) columns w 220 / 170 / 170 / 328: `FEATURE` · `L3 · UNDRILLED` · `L1 · 2 DISCOVERIES` · `VERDICT`. Rows `px 10 py 7` border-b subtle: label Body/Default primary, values Mono/Data secondary, verdict Mono/Data sage (✓) or warning (✕):
  - Sand probability inside · 0.873 · 0.892 · ✓ same reservoir quality
  - Vp/Vs inside · 1.745 · 1.746 · ✓ same charge signature
  - Far − near (AVO) · +0.012 · +0.012 · ✓ same brightening
  - Channel geometry · sinuous, elongate · sinuous, elongate · ✓ same depositional system
  - Structural closure · none · yes · ✕ L3 relies on stratigraphic seal
  - Fault contact · none · none · ✓ no fault-seal risk
- Copilot: user `Find untested traps similar to the meranti-1 discovery`; ONE STRONG LOOK-ALIKE — `**L3** is the only undrilled lead that matches the trap meranti-1 found in L1 (similarity **0.45**). Same sand quality, same gas signature, same channel system.` pills `E11 Similarity 0.45` `E3 Vp/Vs 1.745` `E9 Disc. 1.74`; THE DIFFERENCE THAT MATTERS — `L1 has **structural closure**; L3 does not. L3 depends on its up-dip clay seal, which is why its odds are lower (0.22 vs 0.25).` pill `E7 Seal 0.60`.
- Evidence: **Similar traps** tab; `Look-alikes for L3 · ranked by similarity` Caption; **Ranking** rows (`px 12 py 8`, r 12, gap 10): Name column w 150 (Body/Strong + Caption) · diverging bar (h 6 r 3, glass fill; zero line 1×10 faint at x 75 of a 150px bar, i.e. 75px = 1.0; positive fill accent to the right, negative muted to the left) · value Mono/Data:
  - `L1 · Main channel` / `Combination · 2 discoveries` / `+0.45` (row bg accent tint + accent border; fill 33.75px)
  - `L2 · Four-way dome` / `Structural · 1 discovery` / `−0.21` (15.75px left)
  - `L4 · North channel` / `Combination · dry · kenari-2` / `−0.44` (33px)
  - `L5 · Isolated bar` / `Unclassified · dry · seraya-1` / `−0.57` (42.75px)

### D7 · Executive mode (29:2033) — `29-2033.png`
Purpose: Audience mode **Executive** — same shell, economics instead of geoscience.
- Header: ModeToggle **Executive** active (file-text icon).
- Map head `Opportunity map · value view` + `labels show expected value`; **no attribute switcher, no time slider**; trap legend + scale kept. Lead labels switch their metric row to `EMV` faint · value (sage if positive, `status/error` if negative) · `odds NN%` secondary: L1 `+$49.3M odds 25%` · L3 `+$14.9M odds 22%` · L5 `−$18.1M odds 3%`.
- Bottom-left **Decision panel** `Business case` + `illustrative economics · replace with mentor figures`. **Stats** at (15,55) gap 12: four `Impact stat` cards w 213 (glass fill-subtle, stroke, `px 18 py 16`, r 16, gap 6): Mono/Overline faint · Fraunces Light 40 · Caption secondary w 204:
  - `SCREENING TIME` · `< 2 h` · `to rank 5 leads; was 2–3 weeks by hand`
  - `DRY HOLE AT STAKE` · `$20M` · `per offshore well (confirm benchmark)`
  - `BEST UNDRILLED BET` · `+$15M` (sage) · `EMV of L3 at 22% odds`
  - `AVOIDED BY TESTING` · `$20M` (accent) · `if the AVO check exposes fizz gas`
  **Formula** bar at (15,249): glass fill-subtle, `px 12 py 8`, r 10, gap 10: `EMV` Mono/Overline accent + Mono/Small secondary `= odds × value if it works − (1 − odds) × dry-hole cost  ·  L3: 0.224 × $136M − 0.776 × $20M = +$14.9M`.
- Copilot: user `Is L3 worth drilling?`; SHORT ANSWER — `**Yes, after one cheap test.** About a 1-in-5 chance of success, worth roughly $136M if it works.` pill `E3 Gas signature matches discoveries`; THE RISK — `A failed well costs about **$20M**. The main danger is a weak gas signal that only looks commercial. An AVO study costing far less than a well can rule it out first.` pills `E7 Seal risk 40%` `E4 Fizz-gas check`.
- Evidence panel (no tabs): head (`px 4`) `Leads by expected value` H3 + `odds · EMV` Mono/Small faint; **EMV list** gap 4 of `EMV row` (23:1000/1006; `px 12 py 5`, r 12, gap 12): name col (Body/Strong + Caption) · odds Mono/Data secondary · EMV JetBrains Mono Medium 18 (sage / error):
  - `L1 · Main channel` / `Drilled · 2 discoveries · appraise` / 25% / +$49.3M
  - `L2 · Four-way dome` / `Drilled · 1 discovery · appraise` / 23% / +$20.4M
  - `L3 · East channel` / `Undrilled · best new well` / 22% / +$14.9M (row accent tint + accent border)
  - `L4 · North channel` / `Drilled dry · drop` / 9% / −$13.6M
  - `L5 · Isolated bar` / `Drilled dry · drop` / 3% / −$18.1M
What changes Geoscientist → Executive: toggle; map subtitle and label metric (GCoS/area → EMV/odds); attribute switcher + TWT slider removed; bottom-left becomes Business case; evidence tabs replaced by EMV ranking; answer language is plain-English economics; citations become sentences, not raw measurements. Blind well test / Committee memo buttons unchanged.

### D8 · Blind well test (31:2052) — `31-2052.png`
Purpose: leave-one-out validation of a drilled well.
- Header **Blind well test** button in active state (accent tint, accent border).
- Map: `meranti-1` marker swaps to `Icon/Geo/prospect` with an **accent label** `meranti-1 · hidden` (on-accent text); L1 label only; no ring. **Survey locator** at (667,55) 240×204: scrim, stroke, r 12; inner `instrument/survey locator` (38:842) 232×196 at (3,3): survey outline 200×160 at (16,18) border `instrument/guide` (1px per bin); grid lines at x 66/116/166 and y 58/98/138 (`instrument/grid`); section line IL 1080 accent at y 98; 6px well dots (sage discovery / terracotta dry): jati-1 (183,35) · kenari-1 (117,55) · kenari-2 (130,29) · meranti-1 (103,95) · merbau-1 (51,60) · merbau-2 (43,81) · seraya-1 (53,145); hollow ochre 9px `Lead L3 (undrilled)` at (181.5,123.5); labels Mono/Small faint `IL 1000 · XL 2000` (16,0) and `IL 1159 · XL 2199` (93,180).
- Bottom-left **Blind test panel** (border `accent/border`): `Blind well test · meranti-1` + `well removed from all evidence before predicting`; **Steps** at (685,11) gap 6 (`pl 8 pr 10 py 4`, r 8, Mono/Small number + Label/Default): `1 Hide` · `2 Predict` (glass fill-subtle, faint/secondary) · `3 Reveal` (accent bg, on-accent) — current step. **Prediction card** at (15,51) w 400 (glass fill-subtle, stroke, `px 16 py 14`, r 16, gap 8): `COPILOT PREDICTION · BEFORE REVEAL` Mono/Overline faint · `Gas-charged sand near 2,300 m` H3 · rows (Caption faint label w 70 + Mono/Small secondary): `Reservoir` sand · probability 0.89 at well · `Charge` Vp/Vs 1.743 vs dry-well avg 2.147 · `Fluid` gas · far-stack brightening · `Lead` inside L1 (combination). **Well log** card at (439,51) (scale 0.62: tracks 34.72×186; `44 Ω·m · pay`) with `REVEALED` accent tag (Mono/Overline on-accent, `px 6 py 2`, r 6) at (446.8,59). **Verdict card** at (545.8,51) w 357.2: discovery-bg, border `status/discovery`, `px 16 py 14`, r 16, gap 10: check 18 + `Prediction confirmed` H3 · Body/Default secondary `Gamma ray drops to 21 API at 2,300–2,320 m (sand). Resistivity jumps to 44 Ω·m (hydrocarbon). Same sand in dry kenari-2 reads 1.2 Ω·m (water).` · Mono/Small faint `Leave-one-out on all 7 wells · run on HPC`.
- Copilot: user `Blind test: hide meranti-1 and predict what it found`; PREDICTION · MERANTI-1 HIDDEN — `From seismic alone: a **gas-charged channel sand** near 2,300 m. Vp/Vs at the location matches the other discoveries, not the dry wells.` pills `E3 Vp/Vs 1.743` `E9 Disc. 1.74` `E10 Dry 2.147`; **Reveal event** row (discovery-bg, `px 12 py 10`, r 12, gap 8): eye-off 16 + Body/Default primary `Log revealed: 44 Ω·m pay in sand at 2,300 m. Prediction matched.`; composer placeholder `Try another well…`.
- Evidence (no tabs): `What was checked` H3; rows (glass fill-subtle, `px 12 py 9`, r 10, gap 10): check 16 · Body/Strong w 80 · Mono/Small secondary flex · Mono/Small sage: `Reservoir` predicted sand · GR 21 API · `Charge` predicted hydrocarbon · RES 44 Ω·m · `Depth` predicted ~2,300 m · 2,300–2,320 m · `Trap type` predicted combination · L1 · combination.
States: step 1 Hide / 2 Predict / 3 Reveal; pre-reveal the log card and verdict are absent.

### D9 · Committee memo (31:2326) — `31-2326.png`
Purpose: exportable one-page memo (modal over the dimmed workspace).
- **Dim** overlay 1440×900 `rgba(12,10,9,0.72)` above header. **Memo** at (300,80) w 840 (height auto ≈ 668): `bg/surface`, stroke-strong, r 24, `px 36 py 28`, column gap 18, Elevation/Floating.
  - **Top** row gap 10: title column (gap 4) `COMMITTEE MEMO · BLOCK SK-07 · 29 OCT 2026` Mono/Overline accent + `Lead L3 · East channel` H1 (40/46, tracking −0.4) · `Copy link` button (share 16; glass fill 0.10, stroke-strong, `pl 12 pr 14 py 8`, r 12, Label/Button) · `Download PDF` (download 16; accent) · Close 36 round glass fill-subtle (x 16).
  - **Recommendation** box: accent tint, accent border, `px 20 py 16`, r 16, gap 14: `RECOMMENDATION` overline accent + Fraunces Regular 24 w 560 `Carry forward. Run an AVO study before committing a well.` + `TrapTag` (7:68) `Stratigraphic` (channel icon 14 + Label/Default in trap colour; trap-stratigraphic bg/border, `px 8 py 4`, r 6).
  - **Numbers** row gap 12, four `Impact stat` flex-1 (`px 18 py 16`, r 16, gap 6; Mono/Overline faint · Fraunces Light 30 · Caption w 204): `CHANCE OF SUCCESS` 22% `GCoS 0.22 · 1 in 5` · `EXPECTED VALUE` +$15M (sage) `after $20M dry-hole risk` · `AREA` 0.34 km² `risked 0.08 km²` · `SCREENED IN` < 2 h (accent) `vs 2–3 weeks manual`.
  - **Two columns** gap 16: `Petroleum system` (flex 1) H3 + rows gap 8 (9px dot sage/ochre · Body/Strong w 78 · Body/Default secondary flex · Mono/Data coloured): Reservoir · Channel sand, probability 0.87 · 0.80 · Trap · Stratigraphic, no closure · 0.55 · Seal · Up-dip clay plug, inferred · 0.60 · Charge · Gas signature = discoveries · 0.85. `Main risk and how to retire it` (w 330) H3 + Body/Default `**Fizz gas** could mimic the gas signature (odds would fall to 10%). An AVO model at meranti-1, compared with L3 on the UltraFar stack, separates the two for a fraction of a well's cost.`
  - **Evidence** section: border-top subtle, `pt 12`, gap 6: `EVIDENCE` overline faint; pills `E1 Sand 0.87 vs 0.24` `E2 Sinuosity 1.6` `E3 Vp/Vs 1.745 vs 2.272` `E4 AVO +3.7σ` `E9 Discovery avg 1.74` `E11 Analog L1 · 0.45`; footer Caption faint `Generated by Exploration Copilot · every number traced to measured evidence · synthetic survey · economics illustrative`.

### D10 · Honest states (31:2492) — `31-2492.png`
Purpose: degraded-model banner, refusal, and empty panels.
- Map: Sand probability; L1 label only; **Query point** chip at (68,238): error-bg, 1px `status/error` border, `pl 6 pr 8 py 4`, r 8, alert-triangle 14 + Mono/Small error `IL 1100 · XL 2030 · no lead`.
- Bottom-left: `Seismic section` + `no lead selected`; **Empty** state centred at (341,129), gap 10: section icon 32 + Body/Default secondary `Pick a lead or a well to load its section`.
- Copilot: **Banner** (12:364, `type = Warning | Error`; `px 16 py 12`, r 12, gap 12, alert-triangle 18, Body/Strong title + Caption secondary): warning `Gemma is busy, using the offline reasoner` / `Same evidence, template wording. Retrying in the background.` → user `Is there oil at inline 1100, crossline 2030?` → error banner `Not enough evidence` / `No measurement supports oil at IL 1100 · XL 2030. Try a lead or a well.` → WHAT I CAN SAY — `Sand probability there is 0.18: background shale, not reservoir. No lead covers this point; the nearest is L5, a dry bar to the south. **I won't call oil without evidence.**` pills `E1 Sand 0.18` `E5 Nearest lead L5`.
- Evidence: tabs (Scorecard active) + **Empty** (`pt 50`, gap 10, centred): anticline icon 32 + `No lead selected` H3 + Body/Default secondary centred w 320 `Click an outline on the map or ask about a lead to see its petroleum-system scorecard.`

---

## 4. Component index (page "Screens" / Design System)

| Component | Figma id | Variants / props |
|---|---|---|
| AppHeader | 23:692 | mode: Geoscientist, Executive |
| ModeToggle | 23:652 | mode |
| Composer (hero) | 9:62 | state Idle |
| SuggestedPrompt | 7:102 | prompt, state Default |
| CoreOrb | 7:137 | state Idle (120) / 31.2 in panel head |
| Chat message bubble | 9:148 | user |
| CitationPill | 23:875 | ref, label, state Default / Active |
| ToolStep | 9:17x | state Done / Active / Pending |
| Skeleton | 12:528 | — |
| Banner | 12:364 | type Warning / Error |
| EvidenceTabs | 23:802 | active Scorecard / Devils advocate / Similar traps |
| Scorecard row | 23:888 / 23:901 | ok / warning (+reason) |
| EMV row | 23:1000 / 23:1006 | positive / negative |
| Impact stat | 23:1013 | — (w 213 in Business case; flex in memo) |
| Map lead label | 12:291 / 12:305 / 12:317 / 12:349 | structural / stratigraphic / combination / hidden |
| Well marker | 12:335 / 12:342 | discovery / dry |
| Well log | 23:943 | mini GR/RES card |
| TrapTag | 7:68 | type Stratigraphic |
| Segment | 7:116 / 7:118 | selected |
| instrument/cross grid | 38:800 | 448×320 tile |
| instrument/ring | 38:807 | diameter = lead radius |
| instrument/guide | 38:804 | horizontal; rotate 90° for vertical |
| instrument/readout | 38:836 | overline, position, values, spaced |
| instrument/leader label | 38:812 | name, value, side Right |
| instrument/gradient legend | 38:878 | ramp Vp/Vs / Sand probability / Far − Near |
| instrument/view toggle | 38:900 | view Section / Volume / Stack |
| instrument/survey locator | 38:842 | — |
| view/volume | 39:791 | — |
| view/stack | 39:843 | — |

Variable defs were also pulled from the "Instrument" section 38:795: it adds `Heading/H1 Desktop`, `Heading/H2 Desktop`, `color/bg/surface` to the set above (no additional colours beyond §1.1).

---

## 5. Phone frames (390×844) — screenshot + short note only (no design context pulled)

Shared phone shell (all six): iOS status bar (`9:41`) on dark canvas; a floating **bottom tab bar** (glass, r ≈ 24, 4 tabs with icon + Caption label: `Map` · `Chat` · `Leads` · `Wells`; active tab = ochre tint pill with accent icon/text); home indicator. Non-welcome screens have a compact header: 36px core orb + title H3 + Caption subtitle, and a small **mode toggle** at top-right (two icon-only segments: section icon = Geoscientist, file-text = Executive; active = accent). Composer is a full-width pill (`Ask the copilot…` / `Ask a follow-up…`) with Mic + accent Send.

### P1 · Welcome (33:2488) — `33-2488.png`
Hero stacked: orb (~72px) → Display headline `What is the opportunity in this block?` (3 lines, Fraunces ~40) → `Every answer shows its evidence.` → three stat chips `5 leads` · `7 wells` · `1 undrilled` (mono number + caption, pill r full) → three suggested-prompt pills stacked left-aligned (`What is the geological opportunity, and why?` · `Find similar traps yet to be tested` · `Why did kenari-2 come up dry?`) → composer `Ask the copilot…` → tab bar with **Chat** active.
Differs from D1: no app header at all (no block chip / mode toggle / Blind well test / Committee memo); subtitle shortened; survey stats become 3 chips (9 seismic volumes dropped); `Rank the leads` prompt dropped; no Attach / Map view chips in the composer; Send is accent (not bg/raised).

### P2 · Map + lead sheet (33:2583) — `33-2583.png`
Header: orb + `Block SK-07` H3 + `Opportunity map · sand probability`; mode toggle top-right. Map fills the top ~half: attribute chips `Sand` · `Vp/Vs` · `AVO` · `Faults` (4, abbreviated; selected = glass fill-strong pill), L3 lead label (same component) and the dashed ring. **Bottom sheet** (drag handle) over the map: `L3 · East channel` H3 + `Stratigraphic` TrapTag on the left, `0.22` mono 26 accent + `GCoS · undrilled` on the right; four score tiles in a row (status dot · mono value · caption label): `0.80 Res` · `0.55 Trap` · `0.60 Seal` · `0.85 Charge`; two buttons `✦ Ask about L3` (accent, full) + `Section` (glass, section icon). Tab bar **Map** active.
Differs from D2: evidence scorecard collapses into a bottom sheet with 4 tiles instead of bars; attribute switcher trimmed from 6 to 4 chips (`Far − Near`→`AVO`, no P-impedance/Structure); no TWT slider, legend or scale bar; no survey-volume view; copilot lives on the Chat tab.

### P3 · Chat answer (33:2724) — `33-2724.png`
Header `Copilot` / `Block SK-07 · Gemma 4 live`. User bubble right-aligned `What is the opportunity here, and why?`. Answer card (glass, r 16): `Stratigraphic` TrapTag + `GCoS 0.22` mono; OPPORTUNITY — `L3 is an **undrilled stratigraphic trap**: a channel sand sealed up-dip by an abandoned clay-filled loop.` pills `E1 Sand 0.87` `E2 Sinuosity 1.6`; WHY GAS — `Same low Vp/Vs and far-stack brightening as the **meranti-1** and **kenari-1** discoveries.` pills `E3 Vp/Vs 1.745` `E4 AVO +3.7σ`; NEXT STEP — `**Carry forward;** test the up-dip seal first.` Follow-up chips `✦ What could make L3 wrong?` · `✦ Scorecard`. Composer `Ask a follow-up…`. Tab **Chat**.
Differs from D2 copilot panel: answer is wrapped in a card with a TrapTag + GCoS header; copy shortened (`WHY IT SHOULD HOLD GAS`→`WHY GAS`; `E9 Disc. 1.74` dropped; "east of the fault" dropped); suggested follow-up chips added under the answer; no map/section visible.

### P4 · Evidence sheet (34:2712) — `34-2712.png`
Header `Copilot`; user bubble `Show the L3 scorecard`. Full-height bottom sheet: EvidenceTabs (`Scorecard` active · `Devil's advocate` · `Similar traps`); `L3 · East channel` / `Weakest element: trap 0.55` + `0.22` accent; a **risk-stack thumbnail** (view/stack render ~150px) with four leader labels `Seal 0.60 · schematic` · `Trap 0.55 · no closure` · `Reservoir 0.80 · Vp/Vs 1.745` · `Charge 0.85 · schematic`; four Scorecard rows (same component as desktop, full width, each with a reason line): Reservoir 0.80 `Sand 0.87 inside vs 0.24 around` · Trap 0.55 `No closure; channel geometry only` (warning) · Seal 0.60 `Up-dip clay plug inferred, not imaged` (warning) · Charge 0.85 `Vp/Vs 1.745 vs 2.272 around`; footer mono `0.80 × 0.55 × 0.60 × 0.85 = 0.22`. No tab bar visible (sheet covers it).
Differs from D2/D5: merges the Scorecard tab and the Risk stack view into one sheet; every row carries a reason line (desktop only on warning rows); product formula shown inline; GCoS printed as 0.22 (desktop stack shows 0.224).

### P5 · Executive mode (34:2852) — `34-2852.png`
Header `Leads by value` / `Block SK-07 · illustrative economics`; mode toggle with **Executive** (file-text) active. Highlight card (accent tint + border): `BEST UNDRILLED BET` overline, `L3 · East channel` H3, `+$15M` Fraunces ~30 sage, body `1-in-5 odds · worth ~$136M if it works · $20M at risk. Run an AVO study first.` EMV rows (name Body/Strong + caption; odds; EMV mono 18): `L1 · Main channel` Drilled · appraise 25% +$49.3M · `L2 · Four-way dome` Drilled · appraise 23% +$20.4M · `L4 · North channel` Drilled dry · drop 9% −$13.6M · `L5 · Isolated bar` Drilled dry · drop 3% −$18.1M. Two impact stats side by side: `SCREENING` `< 2 h` `was 2–3 weeks` · `DRY HOLE` `$20M` `per well at stake`. Tab **Leads** active.
Differs from D7: no value-view map, no Business-case panel with four stats (only two), no EMV formula bar, no chat; L3 is pulled out of the list into a hero card; captions shortened (`· 2 discoveries` dropped).

### P6 · Blind well test (34:2963) — `34-2963.png`
Header `Blind test` / `meranti-1 hidden from all evidence`. Steps row `1 Hide` · `2 Predict` · `3 Reveal` (3 active, accent). Prediction card: `PREDICTION · BEFORE REVEAL` overline, `Gas-charged sand near 2,300 m` H3, pills `E3 Vp/Vs 1.743` `E10 Dry avg 2.147`. Row: mini well-log card (`meranti-1`, GR/RES tracks, sand band, `44 Ω·m · pay`) beside a **Confirmed** card (discovery bg/border, check icon, H3 `Confirmed`, body `GR 21 API = sand. RES 44 Ω·m = hydrocarbon. Dry kenari-2 reads 1.2 Ω·m in the same sand.`). Full-width accent button `eye-off Test another well`. Tab **Wells** active.
Differs from D8: no map / survey locator; no copilot chat; `What was checked` list dropped; prediction rows (Reservoir/Charge/Fluid/Lead) reduced to two pills; `E9 Disc. 1.74` dropped; `Leave-one-out on all 7 wells · run on HPC` dropped; `Try another well…` composer replaced by a primary button.

---

## 6. What "Screens v2" (60:826) added that this older page lacks

Compared from `v2/60-830.png` (D1 · Start of day), `v2/61-1796.png` (D9 · Approver mode), `v2/61-2057.png` (D10 · WP&B summary) (+ `v2/60-1020.png`, `v2/60-1349.png`, `v2/61-1650.png` kept for reference).

- **Audience naming**: v2 renames the second mode **Executive → Approver** (toggle "Geoscientist / Approver"); header right side shows `Day 4 of 10 · 29/10/2026 · 14:05 MYT` and a single **WP&B summary** button; the **Blind well test** and **Committee memo** buttons are gone. Block chip reads `Block SK3XX · synthetic`; health reads `Gemma 4 · live on HPC`.
- **Start of day (v2 D1)** replaces the hero Welcome: it opens straight into the workspace with the map, a **Go-forward list** panel (`DAY 4 OF 10` progress bar, `0 of 1 candidate decided`; an `UNDRILLED · CANDIDATE` card for L3 with GCoS 0.224 / area 0.34 km² / analog L1 · 0.453 and **Go forward / Hold / Drop** decision buttons + `copilot suggests: go forward`; a `DRILLED · CALIBRATION, NOT CANDIDATES` list L1 kenari-1, meranti-1 0.251 DISCOVERY · L2 merbau-1 0.235 DISCOVERY · L4 kenari-2 0.094 DRY · L5 seraya-1 0.032 DRY), and the Copilot panel as a full-height right column with a `START HERE` intro and four suggested questions (`What is the geological opportunity here, and why?`, `What could make L3 wrong?`, `Which drilled lead is most like L3?`, `Is there gas at IL 1100 XL 2030?`). The old page has no decision workflow (go-forward/hold/drop), no day counter, and no drilled-vs-candidate separation.
- **Approver mode (v2 D9)** is a different layout from the old Executive mode: a wide left card `WHAT YOU ARE APPROVING · L3` + `SMALL BACKEND ADD` tag, H1 `A study on L3, not a well`, numbered plain-words reasons each with evidence pills (E13, E23, E12, E18, E17 — a richer evidence numbering than the old E1–E11), three stat tiles (`ODDS IT WORKS 22 in 100`, `THE ONE RISK Trap`, `COST OF THE STUDY —` with `AVAILABLE NOW` / `NOT IN BACKEND` availability tags), a `WHAT WOULD CHANGE OUR MIND · alternatives[]` strip, a small map inset `Where L3 sits`, and two audience cards `FOR THE RESERVOIR ENGINEER` / `FOR THE ASSET MANAGER`. The old Executive mode instead keeps the map and shows $ EMV economics (`$20M`, `+$15M`, EMV formula); v2 drops dollar EMV entirely (cost shown as `USD · MYR, from the asset team`, `not returned yet`, `not in the challenge data`) and reframes odds as "22 in 100".
- **WP&B summary (v2 D10)** replaces the Committee memo: a centred document card `WP&B INPUT · EXPLORATION · DRAFT`, `L3 maturation study · Block SK3XX (synthetic)`, three tiles ASK `Study, not a well` / ODDS `22 in 100 · E5` / COST `USD — · MYR —`, RECOMMENDATION / WHY (numbered, inline evidence ids) / MAIN RISK sections, footer `Evidence: Exploration Copilot run, synthetic store · cited E5 E12 E13 E17 E18 E21 E23 · economics not in model`. No Copy link / Download PDF / stat cards / petroleum-system table as in the old memo.
- **Backend-honesty tags** (`AVAILABLE NOW`, `NOT IN BACKEND`, `SMALL BACKEND ADD`, "not returned yet") are new in v2; the old page only has the "Not enough evidence" refusal and "Gemma is busy" banner.
- Old page features **absent** from v2 (from the three v2 frames seen): Blind well test flow, Committee memo modal, Survey volume / Risk stack views, EMV economics, TWT slider (v2 D1 still has it), hero Welcome screen.

---

## 7. Frames not fully read / caveats

- All ten desktop frames: screenshot + design context + styles captured. Nothing unverified on desktop.
- `get_design_context` for D9 (31:2326) and D10 (31:2492) returned inline (smaller frames) — no `ctx/*.json` file for them; their values above come from that inline code.
- All six phone frames: screenshots captured (after many retries); design context was NOT requested for them (per instruction: screenshot + short note only), so phone sizes/paddings in §5 are read off the PNGs and are approximate.
- Variable defs: pulled on 26:1355 and 38:795 only; status-error / bg-sheet / trap-stratigraphic-bg / radius-xs / space-1/2/6 values come from the reference code's CSS-variable fallbacks, not from `get_variable_defs`.
- Scorecard track fill widths (170 / 110 px) are the Figma fixed widths, not a computed ratio; implement as `score × track width`.
