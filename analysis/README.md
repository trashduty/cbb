# CBB Analysis Reports

This directory contains analysis scripts, generated reports, and detailed betting data for College Basketball (CBB) betting models.

## Directory Structure

```
analysis/
├── scripts/          # Python analysis scripts
├── reports/          # Generated markdown reports
└── data/            # Detailed CSV data exports
```

## Available Reports

All analysis reports are available as markdown files in the `analysis/reports/` directory:

### Moneyline Analysis Reports

1. **EM+BT Moneyline Analysis** (`em_bt_moneyline_analysis.md`)
   - Model combination: Median of Evanmiya and Barttorvik win probabilities
   - Edge analysis by threshold (0%, 1%, 2%, 3%, 4%)
   - Performance by market probability bands (0-10% through 91-100%)
   - ROI calculations with American odds format
   - Best overall ROI: +35.9% at 4%+ edge

2. **KP+BT Moneyline Analysis** (`moneyline_analysis.md`)
   - Model combination: Average of KenPom and Barttorvik win probabilities
   - Edge analysis with betting recommendations
   - Performance by win probability ranges

### Model Combination Analysis

3. **Edge Analysis** (`edge_analysis_regressed.md`)
   - Comprehensive edge combination analysis
   - Multiple model combinations tested

4. **Model Analysis Summary** (`model_analysis_summary.md`)
   - Summary of various model performance metrics

5. **Consensus Impact Analysis** (`consensus_impact_analysis.md`)
   - Analysis of consensus betting indicators

6. **Spread Combination Analysis** (`spread_combination_analysis.md`)
   - Best model combinations for spread betting

7. **Totals Combination Analysis** (`totals_combination_analysis.md`)
   - Best model combinations for over/under betting

## How to Access Reports

### Option 1: View Locally in Repository

Navigate to the reports directory and open any markdown file:

```bash
cd analysis/reports/
ls -la                                    # List all available reports
cat em_bt_moneyline_analysis.md         # View in terminal
```

Or open in a markdown viewer or text editor:
```bash
# Using your preferred editor
vim em_bt_moneyline_analysis.md
nano em_bt_moneyline_analysis.md
code em_bt_moneyline_analysis.md        # VS Code
```

### Option 2: View on GitHub

Once pushed to GitHub, reports can be viewed directly in the GitHub web interface:

1. Navigate to your repository: `https://github.com/trashduty/cbb`
2. Click on `analysis/` folder
3. Click on `reports/` folder
4. Click on any `.md` file (e.g., `em_bt_moneyline_analysis.md`)
5. GitHub will render the markdown with tables and formatting

### Option 3: Convert to PDF

You can convert any markdown report to PDF using tools like:

```bash
# Using pandoc
pandoc em_bt_moneyline_analysis.md -o em_bt_moneyline_analysis.pdf

# Using markdown-pdf (npm package)
markdown-pdf em_bt_moneyline_analysis.md
```

## Running Analysis Scripts

All analysis scripts are located in `analysis/scripts/` and can be run to regenerate reports with updated data:

### EM+BT Moneyline Analysis

```bash
cd /path/to/cbb
python analysis/scripts/em_bt_moneyline_analysis.py
```

**Output:**
- Report: `analysis/reports/em_bt_moneyline_analysis.md`
- Detailed data: `analysis/data/em_bt_moneyline_results.csv`

**Requirements:**
- Python 3.10+
- pandas
- numpy

**What it does:**
1. Loads `graded_results.csv`
2. Calculates median of Evanmiya and Barttorvik win probabilities
3. Computes edge against market odds
4. Calculates ROI using proper American odds format
5. Groups by edge thresholds and probability bands
6. Generates comprehensive markdown report
7. Exports detailed bet-by-bet CSV

## Data Exports

Detailed betting data is available in `analysis/data/`:

- **em_bt_moneyline_results.csv** (894 games)
  - Columns: date, team, moneyline_win_probability, win_prob_barttorvik, win_prob_evanmiya, pred_win_prob, edge, opening_moneyline, moneyline_won, risk, profit, prob_band

## Key Metrics Explained

### Edge
The difference between model predicted probability and market implied probability:
```
edge = predicted_win_probability - market_win_probability
```

### ROI (Return on Investment)
For American odds:
- **Favorites (negative odds)**: Risk = |moneyline|, Win = $100
- **Underdogs (positive odds)**: Risk = $100, Win = moneyline
- **ROI** = (Total Profit / Total Risk) × 100%

### Probability Bands
Market win probabilities grouped into 10% buckets:
- 0-10%: Heavy underdogs
- 11-20%: Strong underdogs
- 21-30%: Moderate underdogs
- 31-40%: Slight underdogs
- 41-50%: Toss-up underdogs
- 51-60%: Slight favorites
- 61-70%: Moderate favorites
- 71-80%: Strong favorites
- 81-90%: Heavy favorites
- 91-100%: Dominant favorites

## Quick Access Examples

### View EM+BT Moneyline Analysis
```bash
# In terminal
cat analysis/reports/em_bt_moneyline_analysis.md | less

# Or use a markdown viewer
glow analysis/reports/em_bt_moneyline_analysis.md
```

### Extract Specific Data
```bash
# Get TL;DR summary
head -20 analysis/reports/em_bt_moneyline_analysis.md

# Get key insights section
grep -A 20 "## Key Insights" analysis/reports/em_bt_moneyline_analysis.md

# View recommended betting strategy
grep -A 30 "## Recommended Betting Strategy" analysis/reports/em_bt_moneyline_analysis.md
```

### Query Detailed CSV Data
```bash
# View first 10 bets
head -10 analysis/data/em_bt_moneyline_results.csv

# Count bets by probability band
cut -d',' -f12 analysis/data/em_bt_moneyline_results.csv | sort | uniq -c

# Filter to profitable bets only
awk -F',' '$11 > 0' analysis/data/em_bt_moneyline_results.csv
```

## Contributing

To add a new analysis:

1. Create analysis script in `analysis/scripts/`
2. Have it generate markdown report in `analysis/reports/`
3. Optionally export detailed CSV to `analysis/data/`
4. Update this README with description and usage

## Support

For questions or issues:
1. Check the generated reports for insights and recommendations
2. Review the methodology sections in each report
3. Examine the detailed CSV data for bet-level analysis
