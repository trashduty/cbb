"""Run the existing Barttorvik scraper locally and push its validated CSV."""
import csv
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = "data/bt_mapped.csv"

def run(*args, capture=False):
    return subprocess.run(args, cwd=ROOT, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None)

def main():
    # Pull before scraping so the new CSV is not overwritten by the pull.
    if run("git", "branch", "--show-current", capture=True).stdout.strip() != "main":
        raise RuntimeError("Switch this checkout to main first.")
    if run("git", "status", "--porcelain", "--untracked-files=no", capture=True).stdout.strip():
        raise RuntimeError("Commit or stash tracked changes before running this launcher.")
    run("git", "pull", "--ff-only", "origin", "main")
    run("uv", "run", "src/scrapers/barttorvik.py", *sys.argv[1:])
    with (ROOT / TARGET).open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise RuntimeError("Empty CSV; nothing will be pushed.")
    for number, row in enumerate(rows, 2):
        for column in ("Home Team", "Away Team", "Team", "Game Date"):
            if not row.get(column, "").strip():
                raise RuntimeError(f"Missing {column} on row {number}; nothing pushed.")
        for column in ("spread_barttorvik", "win_prob_barttorvik", "projected_total_barttorvik"):
            if not math.isfinite(float(row.get(column, ""))):
                raise RuntimeError(f"Invalid {column} on row {number}; nothing pushed.")
        if not 0 <= float(row["win_prob_barttorvik"]) <= 1:
            raise RuntimeError(f"Invalid probability on row {number}; nothing pushed.")
    if not run("git", "diff", "--", TARGET, capture=True).stdout.strip():
        print("Data is unchanged; no commit needed.")
        return
    run("git", "add", "--", TARGET)
    run("git", "commit", "--only", "-m", "Update Barttorvik data from local scraper", "--", TARGET)
    run("git", "push", "origin", "main")
    print("Uploaded data/bt_mapped.csv. Run Basketball Data Scraper to refresh website outputs.")

if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        sys.exit(1)
