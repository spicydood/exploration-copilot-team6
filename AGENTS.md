# Team 06 working agreement

Every person and every coding agent on this repo follows this file. That includes Codex, Claude Code, Cursor, GitHub Copilot and any other tool that reads `AGENTS.md`. Read it before every task. It replaces the task order in the playbook PDF and in `docs/backend-plan.md`. Those still explain the reasoning, but this file sets what happens next. The same plan for people is in `docs/team-plan.pdf`.

**Event.** APGCE GeoHackathon 2026, Challenge 1 "Exploration Copilot". Hack days run Wed 11 to Fri 13 Nov 2026 at Common Ground Bukit Bintang. The judges want convincing geological reasoning, traceable to measurements.

**Scoring.**

| Criterion | Weight | Who carries it |
| --- | --- | --- |
| Business impact | 20 % | Vincent, Ruthran |
| Technical design | 15 % | Atif, Edwin |
| Technical execution | 15 % | Atif, Edwin, Shane |
| User experience | 15 % | Shane |
| Solves the user's challenge | 15 % | Ruthran, Atif |
| Presentation and storytelling | 10 % | Vincent, Shane |
| Innovation and creativity | 10 % | Everyone |

## The team

| Person | GitHub | Role | Machine and agent | Owns |
| --- | --- | --- | --- | --- |
| Shane | `spicydood` | Product, interface, integration, HPC runs, final merges, drives the demo | Mac, Claude Code | `frontend/`, `docs/`, `README.md`, `AGENTS.md`, `scripts/check_ui.py`, `tests/test_chat.mjs` |
| Atif | `AtifAsrul` | Backend and AI agent | Windows, Codex | `backend/`, `eval/run_eval.py`, `tests/test_backend_regressions.py` |
| Edwin | `edwindows11` | Data and evidence engine | His laptop, any agent that reads this file | `engine/`, `config.py`, `scripts/check_real_data.py`, `scripts/make_fake_segy.py`, `tests/test_engine.py` |
| Ruthran | `ruthran22003223` | Geoscience lead and data QC. Has the final say on every geological claim. Works at DUG. | HPC remote desktop (DUG Insight), GitHub website | `knowledge/` cards, reservoir window, well results, reference answers, scoring |
| Vincent | `vinsoontian` | Presenter, slides, business case, question bank | Slides tool of his choice, GitHub website | The deck, the pitch script, the business-impact model, question drafts |

Touch a file outside your area only after agreeing it with its owner.

## How the system works, and who owns each step

1. **Edwin's engine** (`engine/precompute.py`) reads the real SEG-Y and well files on the HPC and writes a store of measurements: maps, leads, wells and cubes. The store lives in `$COPILOT_STORE_DIR`, outside the repo.
2. **Ruthran** sets the inputs that decide what the engine measures: the reservoir time window, the well results and the sand threshold. He checks the output against DUG Insight.
3. **Atif's server** (`backend/`) answers each question. The agent plans tool calls, and the tools read the store and return evidence items E1, E2 and so on.
4. **Gemma 4** writes the explanation from those evidence items. It is the shared vLLM endpoint at `http://172.28.34.1:8000/v1`, reachable only from the HPC. It never reads data files. When it fails, the offline reasoner answers instead.
5. **Shane's interface** (`frontend/`) streams the answer, links each evidence tag to the map and section, and runs on the HPC in Firefox.
6. **Vincent** turns it into a 10-minute story with the business case. **Ruthran** answers the geology questions in Q&A.

Laptops only ever use the synthetic survey (`MOCK=1`) or the fake SEG-Y files from `scripts/make_fake_segy.py`. Real data never leaves the HPC.

## Hand-offs between people

| Pair | What passes between them | Agreement needed before changing it |
| --- | --- | --- |
| Ruthran and Edwin | What to measure, the window, thresholds, well results, whether wells sit where DUG Insight shows them | Any change to the lead rules or scores in `engine/leads.py` |
| Edwin and Atif | The store layout: `meta.json`, `wells.json`, `leads.json`, maps, cubes | Any field added, renamed or removed (gate 3) |
| Atif and Shane | API routes and the chat events: `status`, `tool`, `evidence`, `token`, `reset`, `done` | Any field or event change (gate 3) |
| Ruthran and Vincent | The question bank: Vincent drafts questions, Ruthran writes reference answers and scores | None |
| Vincent and Shane | The demo script, the screenshots, the timing | None |

There is a 15-minute stand-up once a day, online is fine. Each person says what they did yesterday, what they're doing today and what blocks them.

## The three gates

Shane runs gates 1 and 2 with Claude Code.

1. **Before building.** Send Shane a plan of five lines or fewer: task ID, files, approach, the test you will add, estimate. Wait for a go.
2. **Before merging.** Open a pull request into `main` with the task ID in its title and the test results in its description. Shane has it reviewed, and nobody merges their own pull request. Atif or Edwin reviews Shane's own pull requests.
3. **Contract changes.** API fields, chat events and the store layout are shared contracts. Both sides agree before anyone writes code.

```text
Gate 1 - E2 - plan
Files: engine/io.py, engine/precompute.py
Approach: read only the samples inside the window, one volume at a time
Test: tests/test_engine.py - windowed read equals the full read inside the window
Estimate: 2.5 h
```

## Every coding task, step by step

```bash
git checkout main
git pull
git checkout -b <name>/<task-id>-<short-name>      # e.g. edwin/e2-windowed-read
# build, then run every laptop test below
git status                                          # only code files, never data
git add <only the files you changed>
git commit -m "<what changed and why>"
git push -u origin <name>/<task-id>-<short-name>
```

Open the pull request on GitHub. Change the task's status in the table at the bottom of this file in the same pull request.

## Your machine

### Shane: Mac, Claude Code

- Claude Code reads this file through `CLAUDE.md`. Use it for gates 1 and 2. Paste a plan or name a pull request, and it checks the work against this file and the code.
- Port 22 is blocked on Shane's network, so push over HTTPS:
  `GIT_CONFIG_GLOBAL=/dev/null git -c credential.helper= -c credential.helper='!gh auth git-credential' push https://github.com/spicydood/exploration-copilot-team6.git <branch>`
- Shane is the only person who starts the server on the HPC, unless he hands the slot over.

### Atif: Windows, Codex

- Codex reads this file automatically from the repo root. Start each session with: "Follow AGENTS.md. Task <ID>. Work on branch atif/<task-id>-<name>. Never push to main."
- In PowerShell, set environment variables once per terminal, for example `$env:MOCK="1"`, instead of using the `MOCK=1` prefix.
- Activate the environment with `.venv\Scripts\Activate.ps1`.
- Gemma is only reachable from the HPC. Book a slot with Shane to test it (task A4).

### Edwin: laptop, any agent

- First time:
  ```bash
  git clone https://github.com/spicydood/exploration-copilot-team6.git
  cd exploration-copilot-team6
  python -m venv .venv
  .venv\Scripts\Activate.ps1          # Windows
  source .venv/bin/activate           # Mac or Linux
  pip install -r requirements-dev.txt
  ```
- Your daily loop is the fake SEG-Y survey. It is laid out exactly like the HPC folder, so engine changes can be tested without real data:
  ```bash
  python scripts/make_fake_segy.py fake_c1
  # Windows: $env:COPILOT_DATA_DIR="fake_c1"; $env:COPILOT_STORE_DIR="fake_store"; $env:LLM="offline"
  # Mac or Linux: export COPILOT_DATA_DIR=fake_c1 COPILOT_STORE_DIR=fake_store LLM=offline
  python scripts/check_real_data.py
  python -m engine.precompute --t0 1976 --t1 2056
  uvicorn backend.app:app --port 8800
  ```
- Run real data on the HPC in a slot agreed with Shane. There is one shared desktop and one server port.
- If your agent is not Codex or Claude Code, check that it reads `AGENTS.md`. Cursor and GitHub Copilot do. Otherwise paste this file into its instructions.

### Ruthran: HPC remote desktop and the GitHub website

- No code setup is needed. Work in DUG Insight on the team 06 remote desktop, session `Challenge1_Challenge2_InputData`.
- Send the window, the well results and reviews to Shane or Edwin in the team chat. The well results go into `data/well_results.csv` on the HPC only. That file is ignored by git and must stay there.
- To edit a knowledge card, open the file in `knowledge/` on github.com, click the pencil, make the change, then choose "Create a new branch and start a pull request". Shane merges it after a check.
- The question bank with your reference answers lives in `eval/questions.csv` on the HPC only. It is ignored by git, because the answers describe real data.

### Vincent: slides and the GitHub website

- No code setup is needed. Keep the deck outside the repo, in Google Slides, Canva or PowerPoint.
- Screenshots for slides come from the synthetic demo file. Ask Shane for `dist/exploration-copilot-prototype.html` and open it in any browser. Screenshots of the real survey go in the slides only once the organisers confirm in writing that it's allowed (task V4).
- Every number in the business case is either sourced, with the source on the slide, or labelled as an assumption. The app's executive mode works the same way: the asset manager types in the costs.

## Tests before every pull request (laptops)

| # | Command | Must show | Who runs it |
| --- | --- | --- | --- |
| 1 | `python -m unittest discover -s tests -p "test_*.py"` | All pass (25 today, more as tasks add tests) | Shane, Atif, Edwin |
| 2 | `node --test tests/test_chat.mjs` | 3 pass | Shane, Atif |
| 3 | `python scripts/check_ui.py` | `All checks passed` | Shane, and anyone who touched `frontend/` |
| 4 | `MOCK=1 python -m engine.precompute`, then `MOCK=1 uvicorn backend.app:app --port 8800` | The app loads at http://localhost:8800 and the browser checklist passes | Shane, Atif, Edwin |
| 5 | `MOCK=1 python eval/run_eval.py --questions eval/questions_mock.csv --tag <branch>` | 10 answers, none empty, no tracebacks | Atif, and anyone who touched `backend/` |
| 6 | The fake SEG-Y loop in Edwin's section | `All checks passed`, then the server answers | Edwin, and anyone who touched `engine/` or `config.py` |
| 7 | `MOCK=1 python frontend/build_standalone.py` | The file is written and opens with no network | Shane, after `frontend/` changes |

Every bug fix adds a test that fails before the fix and passes after it.

**Browser checklist, about 3 minutes:**

1. The welcome screen loads and opens the workspace.
2. Clicking a lead updates the map, the scorecard and the section.
3. "What is the geological opportunity, and why?" streams an answer with evidence tags.
4. Clicking an evidence tag opens its dialog and pins the map. Escape closes it.
5. "Rank the leads", with a lead selected, gives a table of all leads.
6. "Is there gas at inline 5000, crossline 2050?" answers "Location unavailable".
7. Executive mode, the blind well test, the committee memo and the light theme open without errors.
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

`/api/health` must show `"mock":false`, `"llm_mode":"gemma"` and `"llm_reachable":true`. Then walk the browser checklist in the HPC's Firefox. Answer footers should say "Gemma 4", and Ruthran confirms that the wells and leads match DUG Insight.

## Tasks

Priorities:

- **Must have for the demo:** S0, S1, E1, E2, R1, R2, A1, A4, E3 and V1.
- **Should have:** A5, E5, R4, V2 and V3.
- **Nice to have:** A6. Show the blind well test only if the hidden result is provably excluded.

| ID | Owner | Task | Estimate | Day | Status |
| --- | --- | --- | --- | --- | --- |
| S0 | Shane | Clone and set up on the HPC (`docs/team-setup.md`) | 30 min | Thu 5 | To do |
| A0 | Atif | Pull `main`, read this file, run laptop tests 1 to 5 | 20 min | Thu 5 | To do |
| E0 | Edwin | Clone, set up, run laptop tests 1, 4 and 6 | 30 min | Thu 5 | To do |
| V4 | Vincent | Email the organisers: may slides show real-data screenshots, is the demo on our laptop or theirs, is Gemma guaranteed during judging | 15 min | Thu 5 | To do |
| A2 | Atif | Say "winding" only when sinuosity is at least 1.3 (`backend/agent.py`) | 30 min | Thu 5 | To do |
| S1 | Shane + Edwin | `check_real_data.py` on the HPC, fix any FAIL, first precompute, Gemma smoke test with 3 questions | 1.5 to 3 h | Fri 6 | To do |
| E1 | Edwin + Ruthran | Wells sit where DUG Insight shows them. Fix the placement if not (`engine/wells.py`) | 1 to 2 h | Fri 6 | To do |
| R1 | Ruthran | The reservoir window in ms, from an inline in DUG Insight, plus each well's result (discovery, dry, unknown) | 1 h | Fri 6 | To do |
| A1 | Atif | "Opportunity" means an undrilled lead, even when a drilled lead is selected | 2 h | Fri 6 | To do |
| E2 | Edwin | Read only the samples inside the window, one volume at a time. Today `engine/io.py` loads every full volume into memory | 2 to 3 h | Fri 6 | To do |
| V1 | Vincent | Deck skeleton as the handbook requires (team, challenge, solution overview, demo screenshots, repo link) and a timed 10-minute script | 3 h | Fri 6 to Sat 7 | To do |
| E3 | Edwin | Rebuild the store safely: build into a new folder and swap only on success (`engine/precompute.py`) | 1.5 h | Sat 7 | To do |
| E4 | Edwin + Atif | Store provenance in `meta.json`: window, thresholds, build time, git commit. Shown in `/api/meta` (gate 3) | 1 h | Sat 7 | To do |
| A4 | Atif + Shane | Gemma on the HPC: planner output, timeouts, latency, 10-question run | 2 to 3 h | Sat 7 | To do |
| R2 | Ruthran | QC the real-data map, wells, leads and scorecard reasons against DUG Insight. List what's wrong | 1 to 2 h | Sat 7 | To do |
| V2 | Vincent | Business case: time saved per block, risked value versus one avoided dry hole. Sourced or labelled numbers only | 3 h | Sat 7 to Sun 8 | To do |
| A5 | Atif + Shane | Follow-up questions remember the last question and lead (gate 3: optional `history` on `/api/chat`) | 3 to 4 h | Sun 8 | To do |
| E5 | Edwin + Ruthran | Calibrate the sand threshold at the wells. Pass `--sand-threshold` through to the top-sand surface, which `build_maps` ignores today | 1.5 h | Sun 8 | To do |
| E6 | Edwin | `tests/test_engine.py`: reader, windowing, well placement and safe rebuild on the fake SEG-Y survey | 1.5 h | Sun 8 | To do |
| V3 + R4 | Vincent + Ruthran | 30 questions in `eval/questions.csv` on the HPC with reference answers, using `eval/questions_template.csv` columns | 3 h | Sun 8 | To do |
| A6 | Atif | Blind well test: `hide_wells` honoured by every tool and prompt, then health reports `hide_wells: true` | 4 to 6 h | Mon 9 | To do |
| S4 + R4 | Shane + Ruthran | Gemma eval on the HPC. Ruthran scores blind. The three lowest answers become tasks | 3 h | Mon 9 | To do |
| R3 | Ruthran | Review the knowledge cards and lead rules. Add a card for any trap or pitfall the copilot gets wrong | 2 h | Mon 9 | To do |
| S3 | Shane | Freeze at 8 pm, standalone build, backup screen video of the full demo on the HPC | 3 h | Tue 10 | To do |
| V5 | Vincent + all | Three timed rehearsals, the last on the real remote desktop. Q&A drill with Ruthran and Atif | 2 h | Tue 10 to Thu 12 | To do |
| R5 | Ruthran | Check every geological claim in the slides. Prepare Q&A answers on calibration and trap types | 1 h | Tue 10 | To do |
| V6 | Vincent | Submit the slides and the repo link once the organisers share the submission link on day 3 | 15 min | Fri 13 | To do |

Hack days: on day 1, test the venue connection and RustDesk, and show mentors the copilot. On day 2, fix what mentors flag and re-record the backup video in the evening. On day 3, hold two rehearsals, submit, present for 10 minutes, then 5 minutes of Q&A.

## Never

- Commit seismic, well or store files, `data/well_results.csv`, `eval/questions.csv`, screenshots of real maps, HPC logins, the HPC manual, the RustDesk key, tokens or `.env` files. The repo is public. Run `git status` before every commit.
- Copy challenge data, or anything derived from it, off the HPC. That includes answers, eval sheets and screenshots, until the organisers allow screenshots (V4).
- Push to `main`, merge your own pull request, or rewrite history on `main`. Coding agents work on branches only.
- Invent numbers in answers, on screen or in slides. Every number comes from the store, the user's own inputs or a named source.
- Edit code on the HPC without pushing it straight away, or start a second server there.
- Start a task without a gate 1 go, or change a shared contract without gate 3.
