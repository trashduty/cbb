# Multi-Date FanMatch Scraping Guide

## Overview

The multi-date FanMatch scraping system automatically retrieves game results from KenPom for multiple dates based on tracked games. This eliminates the need to manually scrape each date and ensures all tracked games can be graded.

## How It Works

### 1. Date Extraction

The system automatically extracts unique game dates from tracked games:

```python
# Input: "Nov 11 07:00PM ET" 
# Output: "2025-11-11"
```

### 2. Multi-Date Scraping

For each unique date found in tracked games, the system:
- Constructs a date-specific URL: `https://kenpom.com/fanmatch.php?d=2025-11-11`
- Logs in to KenPom using credentials from `.env` file
- Downloads the FanMatch HTML for that date
- Saves to `kenpom-data/fanmatch-YYYY-MM-DD.html`

### 3. Game Matching and Grading

After scraping, the system:
- Parses all FanMatch HTML files
- Matches tracked games to FanMatch results using fuzzy team name matching
- Grades spread and total bets
- Updates the Excel file with results

## Usage

### Option 1: Automatic Scraping (Recommended)

The `game_tracker.py` script now automatically scrapes missing dates:

```bash
# Set up credentials
echo "EMAIL=your_email@kenpom.com" > .env
echo "PASSWORD=your_password" >> .env

# Run tracker - it will automatically scrape needed dates
python3 game_tracker.py
```

**What happens:**
1. Script identifies games needing results (e.g., Nov 11, Nov 12)
2. Checks if FanMatch HTML exists for those dates
3. If missing, scrapes those specific dates automatically
4. Grades all games and updates Excel file

### Option 2: Manual Scraping

You can scrape specific dates manually:

```bash
# Scrape specific dates
python3 scrape_fanmatch.py --dates 2025-11-11 2025-11-12

# Scrape with visible browser (for debugging)
python3 scrape_fanmatch.py --dates 2025-11-11 --no-headless

# Custom output directory
python3 scrape_fanmatch.py --dates 2025-11-11 --output-dir ./my-data
```

### Option 3: Using the Scraping Module

You can use the scraping module in your own scripts:

```python
from scrape_fanmatch import scrape_fanmatch_for_tracked_games
import pandas as pd

# Load tracked games
spread_df = pd.read_excel('master_game_tracking.xlsx', sheet_name='Spreads')
total_df = pd.read_excel('master_game_tracking.xlsx', sheet_name='Totals')

# Scrape FanMatch for all unique dates
success_count = scrape_fanmatch_for_tracked_games(
    spread_df,
    total_df,
    'kenpom-data',
    headless=True
)

print(f"Successfully scraped {success_count} dates")
```

## Configuration

### Environment Variables

Create a `.env` file in the repository root:

```bash
EMAIL=your_email@kenpom.com
PASSWORD=your_password
```

**Security Note:** Never commit the `.env` file to git. It's already in `.gitignore`.

### Scraper Settings

You can customize scraper behavior in `scrape_fanmatch.py`:

```python
DEFAULT_WAIT_TIME = 10  # seconds to wait for page elements
PAGE_LOAD_DELAY = 2     # seconds to wait after navigation
```

## Features

### Intelligent Date Parsing

Handles various date formats:
- "Nov 11 07:00PM ET" → "2025-11-11"
- "Dec 25 12:00PM ET" → "2025-12-25"
- "Jan 1 06:00PM ET" → "2025-01-01"

### Fuzzy Team Name Matching

Matches team names even when they differ:
- ✅ "Oklahoma St Cowboys" matches "Oklahoma St"
- ✅ "North Florida Ospreys" matches "North Florida"
- ✅ "Saint Joseph's Hawks" matches "Saint Joseph's"
- ❌ "Florida" does NOT match "Florida Atlantic" (correctly prevents false positives)

The system removes common mascot names before matching to improve accuracy.

### Graceful Fallback

If scraping fails (no credentials, network issue, etc.):
- System continues with existing FanMatch HTML files
- Logs warnings about missing dates
- Still grades games for which data exists

### Comprehensive Logging

The system logs all operations:
- Date extraction
- Scraping progress
- Login status
- Game matching attempts
- Grading results

Example output:
```
[INFO] Extracted 2 unique game dates: ['2025-11-11', '2025-11-12']
[INFO] Logging in to KenPom...
[INFO] Successfully logged in to KenPom
[INFO] Scraping FanMatch for date 2025-11-11...
[INFO] Saved FanMatch HTML to kenpom-data/fanmatch-2025-11-11.html
[INFO] MATCH FOUND! Team 'North Florida Ospreys' matched with FanMatch game
[INFO] SUMMARY: Matched 15 out of 15 spread games with results
```

## File Structure

### Input Files

- `CBB_Output.csv` - Games to track (from odds/model pipeline)
- `master_game_tracking.xlsx` - Existing tracked games
- `.env` - KenPom credentials

### Output Files

- `kenpom-data/fanmatch-YYYY-MM-DD.html` - Downloaded FanMatch pages
- `master_game_tracking.xlsx` - Updated with graded results
- `tracking_summary.csv` - Summary of each run

## Troubleshooting

### No Games Matched

**Symptom:** "Matched 0 out of X games with results"

**Causes:**
1. FanMatch HTML doesn't exist for game dates
2. KenPom credentials are missing or incorrect
3. Team names don't match (rare with fuzzy matching)

**Solutions:**
```bash
# Check if HTML files exist for game dates
ls kenpom-data/fanmatch-*.html

# Verify credentials
cat .env

# Try manual scraping with visible browser
python3 scrape_fanmatch.py --dates 2025-11-11 --no-headless
```

### Scraping Fails

**Symptom:** "Failed to login to KenPom" or "Error during scraping"

**Causes:**
1. Incorrect credentials
2. KenPom site structure changed
3. Network connectivity issues
4. Chrome/ChromeDriver issues

**Solutions:**
```bash
# Verify credentials work by logging in manually
# Check KenPom subscription is active

# Update ChromeDriver
pip install --upgrade selenium webdriver-manager

# Try with visible browser to see what's happening
python3 scrape_fanmatch.py --dates 2025-11-11 --no-headless
```

### Team Name Mismatch

**Symptom:** Some games match but others don't

**Cause:** Team name variations not handled by fuzzy matching

**Solution:**
```python
# Test specific team name matching
from game_tracker import fuzzy_match_teams

team1 = "Your Team Name"
team2 = "FanMatch Team Name"
result = fuzzy_match_teams(team1, team2)
print(f"Match: {result}")
```

If names should match but don't, you may need to:
1. Add the mascot to the `mascots` list in `normalize_team_name()`
2. Adjust the fuzzy matching threshold (default 0.85)

## Testing

### Run All Tests

```bash
# Unit tests
python3 test_multi_date_scraping.py
python3 test_grading_logic.py

# Integration test
python3 test_integration.py
```

### Expected Results

All tests should pass:
```
✓ ALL TESTS PASSED (3/3)
The multi-date game result grading system is working correctly!
```

## Examples

### Example 1: Grade Games from Nov 11-12

```bash
# With auto-scraping (requires credentials)
python3 game_tracker.py

# Without scraping (uses existing HTML)
rm .env  # Remove credentials
python3 game_tracker.py
```

### Example 2: Scrape Multiple Dates

```bash
python3 scrape_fanmatch.py --dates 2025-11-11 2025-11-12 2025-11-13
```

### Example 3: Check Grading Results

```python
import pandas as pd

# Load results
df = pd.read_excel('master_game_tracking.xlsx', sheet_name='Spreads')

# Check grading
graded = df[df['spread_result'].notna()]
print(f"Graded: {len(graded)}/{len(df)} games")

# Win rate
wins = (graded['spread_result'] == 1).sum()
print(f"Win rate: {wins/len(graded):.1%}")
```

## API Reference

### scrape_fanmatch.py

#### extract_unique_game_dates(games_df)
Extract unique game dates from DataFrame.

**Parameters:**
- `games_df` (DataFrame): Games with 'Game Time' column

**Returns:**
- `set`: Unique date strings in YYYY-MM-DD format

#### scrape_multiple_fanmatch_dates(dates, output_dir, headless=True)
Scrape FanMatch for multiple dates.

**Parameters:**
- `dates` (set): Date strings in YYYY-MM-DD format
- `output_dir` (str): Directory to save HTML files
- `headless` (bool): Run browser in headless mode

**Returns:**
- `int`: Number of dates successfully scraped

#### scrape_fanmatch_for_tracked_games(spread_df, total_df, output_dir, headless=True)
Main function to scrape FanMatch for all tracked games.

**Parameters:**
- `spread_df` (DataFrame): Spread games with 'Game Time' column
- `total_df` (DataFrame): Total games with 'Game Time' column
- `output_dir` (str): Directory to save HTML files
- `headless` (bool): Run browser in headless mode

**Returns:**
- `int`: Number of dates successfully scraped

## Limitations

1. **KenPom Subscription Required:** Scraping requires an active KenPom subscription with login credentials.

2. **Rate Limiting:** The scraper adds delays between requests to be respectful to KenPom servers.

3. **Historical Data:** Can only scrape games that KenPom has data for (typically current season).

4. **Browser Requirement:** Selenium requires Chrome/Chromium browser to be installed.

## Future Enhancements

Potential improvements for future versions:

1. **Incremental Scraping:** Only scrape dates that don't have HTML files yet
2. **Retry Logic:** Automatically retry failed scrapes
3. **Parallel Scraping:** Scrape multiple dates simultaneously
4. **Alternative Authentication:** Support for API keys if KenPom adds them
5. **Result Caching:** Cache parsed results to avoid re-parsing HTML

## See Also

- [GRADING_WORKFLOW.md](GRADING_WORKFLOW.md) - Overall grading system documentation
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical implementation details
- [test_integration.py](test_integration.py) - Integration test examples
