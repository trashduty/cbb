# Game Result Grading Workflow

This document explains how the game result grading system works and how to use it.

## Overview

The `game_tracker.py` script tracks qualifying games from `CBB_Output.csv`, retrieves actual game results from KenPom FanMatch data, and grades the performance of spread and total bets.

## How It Works

### 1. Game Selection
Games are selected from `CBB_Output.csv` based on these criteria:

**Spread Games:**
- Edge For Covering Spread >= 0.03 (3%)
- spread_consensus_flag = 1

**Total Games:**
- (Over Total Edge >= 0.03 AND over_consensus_flag = 1) OR
- (Under Total Edge >= 0.03 AND under_consensus_flag = 1)

### 2. Result Retrieval
The script loads game results from FanMatch HTML files in the `kenpom-data/` directory:
- Files must follow naming convention: `fanmatch-YYYY-MM-DD.html`
- The `fanmatch-initial.html` file is skipped (it's a duplicate)
- Dates are extracted from filenames for proper matching

### 3. Team Name Matching
The system uses **fuzzy matching** to handle team name variations:
- Case-insensitive matching
- Whitespace normalization
- "St." vs "Saint" normalization
- Handles mascot names (e.g., "Duke" matches "Duke Blue Devils")
- Prevents false matches (e.g., "Florida" does NOT match "Florida Atlantic")

### 4. Grading Logic

**Spread Bets:**
- WIN (1): Team covers the spread
- LOSS (0): Team doesn't cover the spread
- PUSH (2): Actual margin exactly equals the spread

Examples:
- Favorite -5, wins by 6 → WIN
- Favorite -5, wins by 5 → PUSH
- Favorite -5, wins by 4 → LOSS
- Underdog +5, loses by 4 → WIN

**Total Bets:**
- WIN (1): Bet is correct (Over when actual > line, Under when actual < line)
- LOSS (0): Bet is incorrect
- PUSH (2): Actual total exactly equals the line

Examples:
- Over 150, actual 155 → WIN
- Over 150, actual 150 → PUSH
- Under 150, actual 145 → WIN

## Running the Grading Process

### Prerequisites
```bash
pip install pandas pytz beautifulsoup4 openpyxl
```

### Step 1: Scrape FanMatch Data
First, you need to scrape FanMatch data for the dates of games you want to grade:

```bash
cd src/scrapers
node kenpom-scraper.js
```

This requires:
- KenPom account credentials in `.env` file:
  ```
  EMAIL=your_email@example.com
  PASSWORD=your_password
  ```
- Node.js and npm dependencies:
  ```bash
  npm install
  ```

The scraper will save HTML files to `kenpom-data/fanmatch-YYYY-MM-DD.html`.

### Step 2: Run the Grading Script
```bash
python3 game_tracker.py
```

This will:
1. Load qualifying games from `CBB_Output.csv`
2. Load FanMatch results from `kenpom-data/` directory
3. Match games using fuzzy team name matching
4. Grade spread and total bets
5. Save results to `master_game_tracking.xlsx` with two sheets:
   - "Spreads" sheet: Spread bet results
   - "Totals" sheet: Total bet results
6. Update tracking summary in `tracking_summary.csv`

### Step 3: Review Results
Open `master_game_tracking.xlsx` to see:
- `actual_score_team`: Actual score for the team
- `actual_score_opponent`: Actual score for opponent
- `actual_total`: Combined score
- `actual_margin`: Score difference
- `spread_result`: 0=Loss, 1=Win, 2=Push
- `over_result` / `under_result`: 0=Loss, 1=Win, 2=Push

## Debugging

The script includes comprehensive logging to help diagnose issues:

- **INFO level**: General progress and summary information
- **DEBUG level**: Detailed matching attempts and game data
- **WARNING level**: Issues like unparseable dates or missing data
- **ERROR level**: Critical errors

### Common Issues

**Issue: "Matched 0 out of X games with results"**
- **Cause**: No FanMatch data for the game dates
- **Solution**: Run the scraper for the specific dates where games were played

**Issue: Team names not matching**
- **Cause**: Team name variation not handled by fuzzy matching
- **Debug**: Look at the DEBUG log output to see exact strings being compared
- **Solution**: May need to enhance `normalize_team_name()` function

**Issue: Wrong date assigned to games**
- **Cause**: FanMatch HTML file doesn't have date in filename
- **Solution**: Rename file to `fanmatch-YYYY-MM-DD.html` format

## Testing

Run the test suite to verify grading logic:
```bash
python3 test_grading_logic.py
```

This tests:
- Spread grading calculations
- Total (over/under) grading calculations
- Fuzzy team name matching

All tests should pass for the system to work correctly.

## File Format

Results are saved in Excel format (`master_game_tracking.xlsx`) with two sheets:
- **Spreads**: One row per team tracked
- **Totals**: One row per game tracked

This format is used (instead of CSV) because CSV cannot support multiple sheets.

## Data Flow

```
CBB_Output.csv
    ↓ (filter by edge thresholds and consensus flags)
Qualifying Games
    ↓ (scrape KenPom FanMatch)
kenpom-data/fanmatch-YYYY-MM-DD.html
    ↓ (parse and match using fuzzy logic)
Game Results Matched
    ↓ (grade spreads and totals)
master_game_tracking.xlsx
    ├─ Spreads sheet
    └─ Totals sheet
```

## Important Notes

1. **FanMatch shows predictions before games start**: FanMatch displays predicted scores for upcoming games. These become actual results after games complete. Make sure to scrape FanMatch AFTER games have finished.

2. **Date matching is critical**: Games must match by date for grading to work. The script uses the date from the FanMatch HTML filename.

3. **Deduplication**: The script prevents duplicate entries by using a composite key of game date + team name (for spreads) or game date + game string (for totals).

4. **Historical data preserved**: Existing data in `master_game_tracking.xlsx` is never deleted. New games are only added if they don't already exist.
