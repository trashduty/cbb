# Local Barttorvik runner (Windows)

This uses the repository's existing Selenium scraper with a visible Chrome window.
It does not use stealth flags, proxies, or copy your KenPom Chrome profile.
Access errors stop the run; they are not bypassed.

## One-time setup

1. Use your existing checkout at C:/Users/dudley/cbb. Open a terminal there and run `git pull --ff-only origin main`.
2. Install Python, Google Chrome and Git if they are not already installed.
3. Install UV with `py -m pip install uv`, then reopen the terminal.
4. Confirm that Git can push to this checkout. Reuse your existing Git sign-in; no token belongs in these files.

## Run

Double-click `tools/barttorvik-local/run-scraper.bat`.
The default window is November 1–7, 2026 inclusive. To change it, edit the
`--start-date` and `--days` arguments in that BAT file.
For a rolling window from today, remove `--start-date 2026-11-01`.

The runner pulls main, opens Chrome, downloads and maps predictions, validates
the CSV, and commits/pushes only `data/bt_mapped.csv`. Tracked changes in the
checkout must be committed or stashed first. Git conflicts are left for review.
If push fails, the local commit remains; resolve the Git error before rerunning.

After upload, manually run **Basketball Data Scraper** in GitHub Actions to
regenerate CBB_Output.csv, Combo_Output.csv and their docs copies.

If the local browser gets 403/verification errors, stop and obtain supported
access from the site owner. This package does not guarantee that local access
will work. Rows without complete numeric predictions are not uploaded.
