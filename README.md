# Exploration Copilot

APGCE GeoHackathon 2026 · Challenge 1 · *Can an AI agent reason like an exploration geoscientist?*

Exploration Copilot integrates seismic stacks, inversion volumes and wells to find leads, classify
the trap (structural, stratigraphic, combination), score the petroleum system, and explain the
opportunity in plain language. **Every number it states is cited to a measured fact.**

```
engine/      reads SEG-Y + LAS, builds attribute maps, finds and scores leads (precompute, run once)
backend/     FastAPI server, agent tools, Gemma 4 planner + writer, offline fallback reasoner
frontend/    plain HTML/CSS/JS UI (no build step) + build_standalone.py for an offline demo file
knowledge/   one-page geology cards the agent reads (Ruthan owns these)
eval/        test bank + harness that writes a scoring sheet
```

## Run it on a laptop (synthetic survey, no data, no LLM)

```bash
pip install -r requirements.txt
MOCK=1 python -m engine.precompute          # builds store_mock/ from a fake survey
MOCK=1 uvicorn backend.app:app --port 8800  # open http://localhost:8800
```

Everyone can build UI, prompts and tools this way before touching the HPC.

## Run it on the DUG HPC (real data)

```bash
# 1. once: environment
python3 -m venv ~/copilot-env && source ~/copilot-env/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
export COPILOT_STORE_DIR=/data/epic20/APGCE/<your_team>/copilot_store

# 2. Ruthan picks the reservoir window (two-way time, ms) in DUG Insight, then:
python -m engine.precompute --t0 <start_ms> --t1 <end_ms>
#    optional: --horizon top_reservoir.txt   (X Y TIME export from DUG Insight)
#    optional: --sand-threshold 0.6          (calibrated at the wells)

# 3. serve on the login node and open http://localhost:8800 in Firefox on the remote desktop
uvicorn backend.app:app --host 127.0.0.1 --port 8800
```

Well results: if `WellList_Information.xlsx` has no result column, copy
`data/well_results.example.csv` to `data/well_results.csv`, fill it in (Ruthan), and rerun precompute.

**First run on real data: check these outputs before trusting anything**

1. `reading full: ...` prints for all 9 volumes. If a read fails or the grid looks wrong, the
   inline/crossline header bytes may differ: set `COPILOT_ILINE_BYTE` / `COPILOT_XLINE_BYTE`.
2. `store/wells.json`: every well has `i`, `j` and `inside_survey: true`. If not, the
   coordinate columns in the deviation or well-list files were not recognised (see `engine/wells.py`).
3. Open the app: wells sit where DUG Insight shows them, and discoveries land on sand.
4. `meta.json -> calibration`: discovery wells should differ from dry wells on Vp/Vs and sand.

## Front end

`frontend/` is plain HTML, CSS and JS with no build step, so it runs from the FastAPI static mount on the
HPC and inlines into the standalone demo file. Layout and every value come from the Figma "Screens" page
(`docs/design/figma-screens-spec.md`, PNGs beside it); the deviations from Figma that the anti-slop rules
required are listed there in section 8.8 of the plan.

```
frontend/index.html   doctype, landmarks, skip link, header (audience + theme), the shell, two <dialog>s
frontend/styles.css   one file, cascade layers: tokens (light + dark, Audience modes) → base → layout → components → states → print
frontend/app.js       boot, selection, demo states;  js/api.js also holds EC.util / EC.bus / EC.S (loads first)
frontend/js/map.js    canvas overlay (grid, outlines, ring, wells, pin, readout) + DOM labels + keyboard twin
frontend/js/section.js bottom panel: Section / Volume / Stack / Compare views and the view registry
frontend/js/chat.js   SSE streaming, run-in headings, evidence tags, evidence dialog, banners
frontend/js/views.js  scorecard / devil's advocate / similar traps, Executive mode + business case, blind well test, memo
frontend/fonts/       Figtree, Fraunces, JetBrains Mono (OFL), subset WOFF2 from scripts/fetch_fonts.py
frontend/icons.svg    Lucide subset (ISC), inlined into index.html
```

Rules the code follows: every number with a unit is set in JetBrains Mono (`.num`); colours come only from the
semantic tokens in `styles.css`; strokes ≥ 1 px at ≥ 40 % and text ≥ 12 px so the RustDesk stream keeps them;
no `backdrop-filter`, no looping motion; Firefox ESR safe (no Popover API, no `@starting-style`, no `:has()`).

```bash
.venv/bin/python scripts/fetch_fonts.py           # once: download + subset the fonts
MOCK=1 python -m engine.render_instrument         # volume + risk-stack renders for the bottom panel
.venv/bin/python scripts/check_ui.py              # contrast matrix, colour-literal / grid / slop / CDN gates
```

Demo states for screenshots and the walkthrough: `?lead=L3`, `?state=offline`, `?state=unreachable`,
`?state=refusal`, `?state=empty`, `?state=executive`, `?state=blind`, `?state=memo`, `?state=imagefail`.
The Executive mode's dollar figures come only from the two assumption inputs (dry-hole cost, value if it
works); nothing is shown until the asset team enters them.

## LLM settings

| Variable | Default | Meaning |
|---|---|---|
| `LLM` | `gemma` (`offline` when `MOCK=1`) | `offline` = rule-based reasoner, no network |
| `LLM_BASE_URL` | `http://172.28.34.1:8000/v1` | shared Gemma 4 vLLM endpoint |
| `LLM_MODEL` | `google/gemma-4-26B-A4B-it` | exact model name |
| `CACHE` | `0` | `1` = record and replay answers (turn on for the live demo) |

If Gemma is slow or down, the planner and writer fall back to the offline reasoner automatically,
and the answer footer says so.

## Evaluate

```bash
MOCK=1 python eval/run_eval.py --questions eval/questions_mock.csv
python eval/run_eval.py --questions eval/questions.csv --tag gemma-v1
```

Writes `eval/results/<time>-<tag>.csv` with empty score columns (grounded 0-3, correct 0-3,
alternatives 0-2, clear 0-2). Ruthan scores; track the average per version.

## Offline demo file

```bash
MOCK=1 python frontend/build_standalone.py   # dist/exploration-copilot-prototype.html
```

A single HTML file with maps, sections and recorded answers, no server needed. Built from real
data it contains the data, so **keep that version on the HPC** (data must not leave it).

## Rules we follow

- Never commit data or derived stores: see `.gitignore`.
- Never copy data off the HPC.
- `main` always runs; work on branches; push at least hourly (the HPC has no backups).
