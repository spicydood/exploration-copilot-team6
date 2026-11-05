# Exploration Copilot

APGCE GeoHackathon 2026 · Challenge 1 · *Can an AI agent reason like an exploration geoscientist?*

Exploration Copilot integrates seismic stacks, inversion volumes and wells to find leads, classify
the trap (structural, stratigraphic, combination), score the petroleum system, and explain the
opportunity in plain language. Answers link to evidence; model drafts are checked for
citation and numerical consistency before display.

```
engine/      reads SEG-Y + LAS, builds attribute maps, finds and scores leads (precompute, run once)
backend/     FastAPI server, agent tools, Gemma 4 planner + writer, offline fallback reasoner
frontend/    plain HTML/CSS/JS UI (no build step) + build_standalone.py for an offline demo file
knowledge/   one-page geology cards the agent reads (Ruthan owns these)
eval/        test bank + harness that writes a scoring sheet
```

Backend work allocation, implementation order, and completion checks: [Atif and Edwin backend plan](docs/backend-plan.md).
Step-by-step setup for laptops and the HPC, including how to push from the HPC: [Team setup](docs/team-setup.md).

## Run it on a laptop (synthetic survey, no data, no LLM)

```bash
pip install -r requirements.txt
MOCK=1 python -m engine.precompute          # first run: builds store_mock/ from a fake survey
MOCK=1 uvicorn backend.app:app --port 8800  # open http://localhost:8800
```

Everyone can build UI, prompts and tools this way before touching the HPC.
Existing stores are never deleted by precompute. To rebuild, choose a new `--out` path and set
`COPILOT_STORE_DIR` to that path before starting the server.

## Run it on the DUG HPC (real data)

```bash
# Run from the cloned repo inside your team's HPC storage folder.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export MOCK=0
export LLM=offline
export CACHE=0
export COPILOT_DATA_DIR=/data/epic20/APGCE/input_data/challenge1_challenge2
export COPILOT_STORE_DIR="$PWD/../copilot_store_real_run1"

# Read headers and estimate cube memory without loading trace amplitudes.
python scripts/check_hpc.py
# Sample sand traces and inspect well placement/outcomes for Ruthan's review.
python scripts/check_real_data.py

# Replace START_MS and END_MS with Ruthan's reviewed interval.
python -m engine.precompute --t0 START_MS --t1 END_MS
python -m engine.render_instrument
#    optional: --horizon top_reservoir.txt   (X Y TIME export from DUG Insight)
#    optional: --sand-threshold 0.6          (calibrated at the wells)

# Open http://localhost:8800 in Firefox INSIDE the remote desktop.
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8800
```

Keep that output path for server restarts. For another build, use a new folder such as
`copilot_store_real_run2`; processing refuses to replace existing outputs. The reader currently
loads all nine full volumes, so compare the memory estimate with your team allocation first.

After Ruthan checks the real-data maps and wells, stop the server with Ctrl+C, run
`python scripts/check_hpc.py --check-llm`, set `export LLM=gemma`, and restart the server.
The Gemma answer is buffered until completion and mechanical evidence checks pass; progress
and tool events still stream. Interrupted or rejected drafts are replaced by one labelled
offline answer, and are not cached as successful model answers.

Well results: if `WellList_Information.xlsx` has no result column, copy
`data/well_results.example.csv` to `data/well_results.csv`, fill it in (Ruthan), and rerun precompute.
Use explicit `discovery`, `dry`, or `unknown` labels. Ambiguous notes such as `P&A`, `gas shows`,
or `no gas` stay unknown until reviewed. Older stores are normalised on load and their
outcome-dependent calibration summaries are rebuilt from confirmed labels.

**First run on real data: check these outputs before trusting anything**

1. `reading full: ...` prints for all 9 volumes. If a read fails or the grid looks wrong, the
   inline/crossline header bytes may differ: set `COPILOT_ILINE_BYTE` / `COPILOT_XLINE_BYTE`.
2. `store/wells.json`: every well has `i`, `j` and `inside_survey: true`. If not, the
   coordinate columns in the deviation or well-list files were not recognised (see `engine/wells.py`).
3. Open the app: compare well placement and interpreted reservoir features with DUG Insight.
4. Review the known-outcome comparisons without assuming that discoveries and dry wells must separate.
5. `/api/health` reports `mock: false` and `synthetic: false` for real-data work.

Scores remain provisional screening factors. Financial expected values are disabled until
calibrated probabilities are available. The blind well test is disabled in the UI and API
because independent exclusion of all held-out evidence is not implemented. Evidence checks
verify references and numerical consistency; they do not establish geological correctness.

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
The Executive mode disables financial expected values while scores remain uncalibrated.

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

### Regression checks

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/test_chat.mjs
```

The Python checks build a temporary synthetic survey and test ranking, exact coordinate lookup,
invalid-location responses, and section images without HPC access. The JavaScript checks verify
that each answer renders its own citation labels. Node is needed only for these JavaScript checks.

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
