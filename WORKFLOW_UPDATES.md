# GitHub Actions Workflow Updates

## Summary of Changes

This document summarizes the updates made to the GitHub Actions workflow (`.github/workflows/scrape-workflow.yml`) and related files.

## Changes Made

### 1. **Updated `requirements.txt`** ✅

**Added missing Python dependencies:**
- `numpy>=1.24.0` - Used by barttorvik.py, hasla.py, oddsAPI.py
- `rich>=13.0.0` - Used by all Python scrapers for terminal formatting
- `webdriver-manager>=4.0.0` - Used by hasla.py for Chrome driver management
- `python-dotenv>=1.0.0` - Used by oddsAPI.py for environment variables
- `pytz>=2023.3` - Used by oddsAPI.py for timezone conversions
- `openpyxl>=3.1.0` - Used by oddsAPI.py for Excel operations

**Why:** These packages were declared in the Python scripts' inline metadata but not in requirements.txt, causing potential installation failures in CI.

### 2. **Created `src/utils/filter_started_games.py`** ✅

**Purpose:** Automatically remove games that have already started from `CBB_Output.csv`

**Functionality:**
- Parses game times from "Nov 03 07:00PM ET" format
- Compares against current Eastern Time
- Keeps games that:
  - Haven't started yet
  - Started within the last 15 minutes (grace period)
  - Have no game time (missing odds data)
- Removes games that started more than 15 minutes ago

**Why:** The Shiny app only needs upcoming games. Keeping finished games wastes space and can confuse users.

**Time Zone Handling:**
- All game times in `CBB_Output.csv` are standardized to Eastern Time (ET)
- The oddsAPI.py script converts UTC timestamps from the API to ET
- Filter script uses `pytz.timezone('US/Eastern')` to get current ET time
- Comparison is timezone-aware, so it works correctly regardless of server location

### 3. **Updated `.github/workflows/scrape-workflow.yml`** ✅

#### Changes:
1. **Simplified Python installation:**
   - Removed UV-specific installation
   - Using standard `pip install -r requirements.txt`
   - Added pip caching for faster builds
   - More reliable and widely supported

2. **Added game filtering step:**
   - New step: "Filter out started games"
   - Runs after scraper pipeline completes
   - Runs before committing changes
   - Uses: `python src/utils/filter_started_games.py`

3. **Removed force push:**
   - Changed `git push -f` to `git push`
   - Force push can cause issues with repository history
   - Regular push is safer and sufficient for this use case

4. **Added explanatory comment:**
   - Clarified why 5-minute schedule is necessary
   - Documents intent for future maintainers

#### Schedule Rationale:
**Kept at every 5 minutes (`*/5 * * * *`) because:**
- Sports betting markets move rapidly
- Line changes can happen due to:
  - Injury news
  - Starting lineup announcements
  - Sharp bettor activity
  - Weather/venue changes
- Shiny app users expect near-real-time data
- 5 minutes balances freshness with API rate limits

## Workflow Execution Flow

```
1. Checkout code
2. Set up Node.js 18 + install dependencies
3. Install Playwright browsers (for KenPom/EvanMiya scrapers)
4. Set up Python 3.10 + install dependencies from requirements.txt
5. Configure credentials from GitHub Secrets
   ├─ EMAIL (KenPom login)
   ├─ PASSWORD (KenPom password)
   └─ ODDS_API_KEY (The Odds API key)
6. Run full scraper pipeline (node src/index.js)
   ├─ EvanMiya scraper
   ├─ KenPom scraper
   ├─ Data transformers
   ├─ Dataset joiner
   └─ OddsAPI processor → CBB_Output.csv
7. Filter out started games (python src/utils/filter_started_games.py)
   └─ Removes games that started >15 minutes ago
8. Commit and push CBB_Output.csv (if changed)
```

## Testing

### Local Testing Commands

```bash
# Test full pipeline
node src/index.js

# Test filter script
uv run src/utils/filter_started_games.py
# OR (if dependencies installed globally)
python src/utils/filter_started_games.py
```

### Expected Behavior

**On a typical run at 3:35 PM ET:**
- Pipeline scrapes fresh odds data
- Games scheduled for:
  - ✅ 4:00 PM ET → KEPT (upcoming)
  - ✅ 3:30 PM ET → KEPT (started 5 min ago, within buffer)
  - ❌ 3:00 PM ET → REMOVED (started 35 min ago)
  - ❌ 2:00 PM ET → REMOVED (started 95 min ago)

**Buffer period (15 minutes):**
- Prevents games from disappearing immediately at tip-off
- Allows users to see "just started" games
- Balances data freshness with user experience

## Files Modified

1. ✅ `requirements.txt` - Added 6 missing dependencies
2. ✅ `.github/workflows/scrape-workflow.yml` - Updated workflow
3. ✅ `src/utils/filter_started_games.py` - NEW: Filter script
4. ✅ `claude.md` - NEW: Repository documentation

## Files NOT Modified

- `src/index.js` - No changes needed
- `src/scrapers/*.js` - No changes needed
- `src/scrapers/*.py` - No changes needed
- `package.json` - No changes needed
- `data/crosswalk.csv` - No changes needed

## Deployment Checklist

Before enabling the workflow:

- [x] Update `requirements.txt` with all dependencies
- [x] Create `filter_started_games.py` script
- [x] Update workflow file
- [ ] Set GitHub Secrets:
  - [ ] `EMAIL` - KenPom login email
  - [ ] `PASSWORD` - KenPom login password
  - [ ] `ODDS_API_KEY` - The Odds API key
- [ ] Test workflow with manual trigger (`workflow_dispatch`)
- [ ] Monitor first few automated runs
- [ ] Verify CBB_Output.csv is updating correctly
- [ ] Check that started games are being filtered

## Monitoring

### Success Indicators:
- Workflow completes in < 5 minutes
- CBB_Output.csv updated every 5 minutes (when data changes)
- No started games in output file
- Shiny app displays fresh data

### Common Issues:
1. **Workflow fails on Python dependencies**
   - Solution: Verify all packages in requirements.txt
   - Check: `pip install -r requirements.txt` runs locally

2. **Filter script removes all games**
   - Likely: No upcoming games in schedule
   - Check: Time zone handling is correct
   - Verify: Game times are in ET format

3. **Git push fails**
   - Check: Workflow has `contents: write` permission
   - Verify: No branch protection rules blocking GitHub Actions

4. **Scrapers timeout**
   - KenPom/EvanMiya may have login issues
   - Check: GitHub Secrets are set correctly
   - Verify: Websites haven't changed their HTML structure

## Future Enhancements

Possible improvements for later:
1. Add Slack/Discord notifications on workflow failure
2. Store historical odds data in separate branch
3. Add data quality checks before committing
4. Implement rate limiting awareness for Odds API
5. Add metrics dashboard for workflow performance

## Rollback Plan

If the workflow causes issues:

```bash
# Disable workflow temporarily
# In GitHub repo → Actions → Disable workflow

# Revert to previous version
git revert <commit-hash>

# Or manually update workflow file
# Comment out the "schedule" trigger to stop automated runs
```

## Contact

For issues with the workflow, check:
1. GitHub Actions logs (detailed error messages)
2. Individual scraper logs (in workflow output)
3. CBB_Output.csv (data quality)

---

**Last Updated:** November 2, 2025
**Version:** 2.0
**Status:** Ready for deployment
