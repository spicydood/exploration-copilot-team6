# Working agreement for coding agents (Codex, Claude Code) and the team

Read this file before every task. It is the single source of truth for how Shane (frontend, HPC, setup) and Atif (backend) work on this repo right now. It replaces the task order in the playbook PDF and in `docs/backend-plan.md`. Those still explain the reasoning, but this file sets what happens next.

Event: APGCE GeoHackathon 2026, Challenge 1 "Exploration Copilot", hack days Wed 11 to Fri 13 Nov 2026. The judges want convincing geological reasoning that is traceable to measurements.

## How the system works

1. Laptops write code against a synthetic survey. Real data never leaves the HPC.
2. GitHub `main` holds code only. The HPC runs `git pull` and restarts the server.
3. On the HPC, `engine/precompute.py` reads the real SEG-Y and well files once and writes a store of measurements (maps, leads, wells, cubes) to `$COPILOT_STORE_DIR`.
4. For each question, `backend/agent.py` plans tool calls. `backend/tools.py` reads the store and returns evidence items E1, E2 and so on.
5. Gemma 4 (shared vLLM at `http://172.28.34.1:8000/v1`, reachable only from the HPC) writes the explanation from those evidence items. It never reads data files. When it fails, the offline reasoner writes the answer.

Chat stream events, in order: `status`, `tool`, `evidence`, `token`, optional `reset` (drop the tokens so far), then `done`. Do not add, rename or remove events or API fields without agreement (gate 3 below).

## Who owns what

| Area | Owner | Files |
| --- | --- | --- |
| Server, agent, tools, prompts, LLM client | Atif | `backend/`, `knowledge/`, `tests/test_backend_regressions.py` |
| Interface | Shane | `frontend/`, `tests/test_chat.mjs`, `scripts/check_ui.py` |
| Engine and real-data checks | Shane (with Ruthan), Atif may fix bugs | `engine/`, `scripts/check_real_data.py`, `scripts/make_fake_segy.py` |
| HPC runs, demo, docs | Shane | `docs/`, `README.md`, this file |

Touch a file outside your area only after agreeing it with the owner.

## The three gates: check before you build, check before you merge

Shane runs these checks with Claude Code.

1. **Before building.** Write a plan of five lines or fewer: the task ID, the files you will change, the approach, and the test you will add. Send it to Shane. Wait for a go before writing code.
2. **Before merging.** Open a pull request into `main`. Shane has it reviewed. Nobody merges their own pull request, and no agent pushes to `main`.
3. **Contract changes.** Any change to API routes, request or response fields, chat events or the store layout must be agreed by both of you first. It breaks the other person's half.

## Every task, step by step

```bash
git checkout main && git pull
git checkout -b atif/<task-id>-<short-name>      # or shane/...
# build, then run every laptop test below
git add <only the files you changed>
git commit -m "<what changed and why>"
git push -u origin atif/<task-id>-<short-name>
```

Then open the pull request with the task ID in its title.

## Tests to run before every pull request (laptop)

| # | Command | Must show |
| --- | --- | --- |
| 1 | `python -m unittest discover -s tests -p "test_*.py"` | All pass (25 today, more as tasks add tests) |
| 2 | `node --test tests/test_chat.mjs` | 3 pass |
| 3 | `python scripts/check_ui.py` | `All checks passed` |
| 4 | `MOCK=1 python -m engine.precompute` then `MOCK=1 uvicorn backend.app:app --port 8800` | App loads at http://localhost:8800, then walk the browser checklist |
| 5 | `MOCK=1 python eval/run_eval.py --questions eval/questions_mock.csv --tag <branch>` | 10 answers, none empty, no tracebacks |
| 6 | Only if `engine/` or store code changed: see the fake SEG-Y check in `docs/team-setup.md` | `All checks passed`, then the server answers |

On Windows PowerShell, set `MOCK` with `$env:MOCK="1"` once per terminal instead of the `MOCK=1` prefix.

Every bug fix adds a test that fails before the fix and passes after it.

**Browser checklist (about 3 minutes):**

1. The welcome screen loads and opens the workspace.
2. Clicking a lead updates the map, the scorecard and the section.
3. "What is the geological opportunity, and why?" streams an answer with evidence tags.
4. Clicking an evidence tag opens its dialog and pins the map.
5. "Rank the leads", with a lead selected, gives a table of all leads.
6. "Is there gas at inline 5000, crossline 2050?" answers "Location unavailable".
7. Executive mode, the blind well test and the committee memo open without errors.
8. The browser console shows no red errors.

## Tests on the HPC (Shane, after each merge)

```bash
cd /data/epic20/APGCE/apgce_team_06/exploration-copilot-team6
source /data/epic20/APGCE/apgce_team_06/copilot-env/bin/activate
export COPILOT_STORE_DIR=/data/epic20/APGCE/apgce_team_06/copilot_store
git pull
python scripts/check_real_data.py                  # only if engine/ changed
python -m engine.precompute --t0 <ms> --t1 <ms>    # only if engine/ changed
python -m engine.render_instrument                 # only if engine/ changed
uvicorn backend.app:app --host 127.0.0.1 --port 8800
curl -s http://127.0.0.1:8800/api/health           # in a second terminal
```

`/api/health` must show `"mock":false`, `"llm_mode":"gemma"` and `"llm_reachable":true`. Then walk the browser checklist in the HPC's Firefox. Answers should say "Gemma 4" in their footer.

## Current tasks (status kept here, newest first)

| ID | Owner | Task | Estimate | Status |
| --- | --- | --- | --- | --- |
| S0 | Shane | Clone and set up on the HPC | 30 min | To do |
| A0 | Atif | Pull `main`, read this file, run laptop tests 1 to 5 | 20 min | To do |
| S1 | Shane | `check_real_data.py` on the HPC, fix any FAIL with Claude | 0.5 to 2 h | To do |
| S2 | Shane | First real precompute and server run, Gemma smoke test | 1 h | To do |
| A1 | Atif | "Opportunity" means an undrilled lead, even when a drilled lead is selected | 2 h | To do |
| A2 | Atif | "Winding" only when sinuosity is at least 1.3 (`backend/agent.py`) | 30 min | To do |
| A3 | Atif | Rebuild the store safely: build into a new folder, swap only on success (`engine/precompute.py`) | 1.5 h | To do |
| A4 | Atif + Shane | Gemma on the HPC: planner output, timeouts, eval run | 2 to 3 h | To do, needs an HPC slot |
| A5 | Atif + Shane | Follow-up questions remember the last question and lead (contract change, gate 3) | 3 to 4 h | To do |
| S3 | Shane + Ruthan | Ruthan's window and well results, rerun precompute | 1 h + waiting | To do |
| A6 | Atif | Blind well test: `hide_wells` honoured by every tool, then health says `hide_wells: true` | 4 to 6 h | To do |
| S4 | Shane + Ruthan | 30-question bank in `eval/questions.csv` (HPC only, ignored by git), Gemma eval, Ruthan scores | 3 h | To do |
| S5 | Shane | Freeze Tue 10 Nov evening: standalone build, backup video, rehearsal | 3 h | To do |

Details for each task are in the plan PDF Shane shares. When a task's status changes, update this table in the same pull request.

## Never

- Commit seismic, well or store files, screenshots of real maps, HPC logins, the HPC manual, the RustDesk key, tokens or `.env` files. The repo is public. Run `git status` before every commit.
- Copy challenge data or answers built from it off the HPC. `eval/results/` from the HPC stays on the HPC.
- Push to `main`, merge your own pull request, or rewrite history on `main`.
- Invent numbers in answers or in the UI. Every number comes from the store or the user's own inputs.
- Edit code on the HPC without pushing it straight away.
- Run a second server on the HPC. There is one shared desktop and one port 8800.
