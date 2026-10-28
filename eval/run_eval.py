"""Run the test bank against the copilot and write a sheet for Ruthan to score.

    MOCK=1 python eval/run_eval.py --questions eval/questions_mock.csv
    python eval/run_eval.py --questions eval/questions.csv --tag gemma-v2

Scoring rubric (fill the four score columns, 10 points total):
  grounded 0-3 · correct 0-3 · alternatives 0-2 · clear 0-2
"""
import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from backend.agent import Agent  # noqa: E402
from backend.store import Store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default="eval/questions.csv")
    ap.add_argument("--tag", default=config.LLM_MODE)
    a = ap.parse_args()
    agent = Agent(Store(config.STORE_DIR))
    rows = list(csv.DictReader(open(a.questions)))
    out = Path("eval/results") / f"{time.strftime('%Y%m%d-%H%M')}-{a.tag}.csv"
    out.parent.mkdir(exist_ok=True)
    fields = ["id", "tier", "question", "selected_lead", "answer", "tools", "cited", "unverified_numbers",
              "mode", "seconds", "reference_answer", "grounded_0_3", "correct_0_3", "alternatives_0_2",
              "clear_0_2", "total_10", "notes"]
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            res = agent.answer(r["question"], r.get("selected_lead") or None)
            w.writerow({**{k: r.get(k, "") for k in ("id", "tier", "question", "selected_lead", "reference_answer")},
                        "answer": res["text"], "tools": " ".join(res["tools"]),
                        "cited": len(res.get("cited", [])), "unverified_numbers": " ".join(res.get("unverified_numbers", [])),
                        "mode": res.get("mode"), "seconds": res.get("seconds")})
            print(f"{r['id']:>3} {r['tier']:<14} cited={len(res.get('cited', [])):<3} "
                  f"unverified={len(res.get('unverified_numbers', []))} {res.get('seconds')}s")
    print(f"\nwrote {out} - open it in Excel/Sheets and score each answer.")


if __name__ == "__main__":
    main()
