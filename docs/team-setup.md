# Team setup: laptops and the HPC

Two places run the copilot:

- **Laptops** build and test with a synthetic survey. No real data ever goes to a laptop.
- **The HPC** (team 06 remote desktop) runs it on the real survey with Gemma 4. Only the HPC can reach Gemma.

Rules for everyone:

- Never commit seismic, wells, `store/`, screenshots of HPC logins, the HPC manual or access keys. `.gitignore` blocks the data formats, but run `git status` before every commit anyway. The repo is public.
- Work on a branch and open a pull request. Someone else reviews it before it is merged into `main`.
- Pull `main` before you start, and push at least every hour. The HPC has no backups.

## Laptop setup (Atif, Edwin, anyone)

Commands are for Windows PowerShell. On a Mac or Linux, use the second line wherever two are given.

### 1. Get the latest code

First time only:

```bash
git clone https://github.com/spicydood/exploration-copilot-team6.git
cd exploration-copilot-team6
```

Every time after that:

```bash
git checkout main
git pull
```

### 2. Make the Python environment (first time only)

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1            # Windows
source .venv/bin/activate             # Mac / Linux
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Activate it again in every new terminal with the `Activate.ps1` or `source` line.

### 3. Check everything works

```bash
python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_chat.mjs
```

You should see 25 Python tests and 3 JavaScript tests pass. Node is needed only for the second line.

### 4. Run the app on the synthetic survey

```bash
$env:MOCK="1"                          # Windows (once per terminal)
export MOCK=1                          # Mac / Linux
python -m engine.precompute
uvicorn backend.app:app --port 8800
```

Open http://localhost:8800. Stop the server with Ctrl+C.

Without a model, answers come from the offline reasoner. Gemma can only be tested on the HPC.

### 5. Test the real-data path on a laptop (optional)

This writes the synthetic survey as SEG-Y and LAS files laid out like the HPC, then runs the same commands the HPC runs. Open a new terminal without `MOCK` set.

```bash
python scripts/make_fake_segy.py fake_c1
$env:COPILOT_DATA_DIR="fake_c1"; $env:COPILOT_STORE_DIR="fake_store"; $env:LLM="offline"        # Windows
export COPILOT_DATA_DIR=fake_c1 COPILOT_STORE_DIR=fake_store LLM=offline                       # Mac / Linux
python scripts/check_real_data.py
python -m engine.precompute --t0 1976 --t1 2056
uvicorn backend.app:app --port 8800
```

`fake_c1/` and `fake_store/` are ignored by git.

### 6. Make a change and send it for review

```bash
git checkout main
git pull
git checkout -b atif/follow-up-questions
# ...edit, then run the tests from step 3...
git add <the files you changed>
git commit -m "Remember the previous question for follow-ups"
git push -u origin atif/follow-up-questions
```

Open the pull request on GitHub and ask Shane to review it. Don't merge your own pull request.

## HPC setup (Shane, on the team 06 remote desktop)

Use the Mate Terminal on the remote desktop. Team storage lives in `/data/epic20/APGCE/apgce_team_06`. The home folder is small, so the code and the Python environment both go in team storage.

### 1. First time only: name, code and environment

```bash
git config --global user.name "Team 06 HPC"
git config --global user.email "spidymatthew@gmail.com"
cd /data/epic20/APGCE/apgce_team_06
git clone https://github.com/spicydood/exploration-copilot-team6.git
python3 -m venv /data/epic20/APGCE/apgce_team_06/copilot-env
source /data/epic20/APGCE/apgce_team_06/copilot-env/bin/activate
cd exploration-copilot-team6
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 2. Every new terminal

```bash
cd /data/epic20/APGCE/apgce_team_06/exploration-copilot-team6
source /data/epic20/APGCE/apgce_team_06/copilot-env/bin/activate
export COPILOT_STORE_DIR=/data/epic20/APGCE/apgce_team_06/copilot_store
git pull
```

The store folder sits outside the repo, so nothing built from the real data can be committed by accident.

### 3. Check the real data and get a starting window

```bash
python scripts/check_real_data.py
```

It lists the volumes, where each well lands, the well results and a provisional reservoir window. Fix any `FAIL` lines before going on.

### 4. Build the store and run the app

Use the window that `check_real_data.py` suggests, or Ruthan's window from DUG Insight.

```bash
python -m engine.precompute --t0 <start_ms> --t1 <end_ms>
python -m engine.render_instrument
uvicorn backend.app:app --host 127.0.0.1 --port 8800
```

Open http://localhost:8800 in the remote desktop's Firefox. Use `http`, not `https`. The header should read "real data" and "Gemma 4 connected".

### 5. Push from the HPC (only if you changed code there)

GitHub needs a token to accept a push from the HPC. Make a short-lived one that can only touch this repo:

1. On your own laptop, open GitHub, then Settings, then Developer settings, then Personal access tokens, then Fine-grained tokens, then Generate new token.
2. Set the expiration to 7 days and the repository access to `exploration-copilot-team6` only. Under Permissions, set Contents to "Read and write".
3. Copy the token. Keep it out of chat, notes and the repo.

Then, on the HPC:

```bash
git config --global credential.helper "cache --timeout=28800"
git status                        # check: only code files, no data
git checkout -b hpc/<what-changed>
git add <the files you changed>
git commit -m "<what changed>"
git push -u origin hpc/<what-changed>
```

When git asks, the username is your GitHub username and the password is the token. The cache keeps it in memory for 8 hours and never writes it to disk. Delete the token on GitHub after the event.
