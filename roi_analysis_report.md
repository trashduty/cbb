# ROI Analysis: KP+BT+HA Totals Betting Model Ensemble

## Executive Summary

This analysis evaluates betting performance using the **median prediction** from three models:
- **KenPom (KP)**
- **Bart Torvik (BT)**
- **Haslametrics (HA)**

### Data Overview

- Total games analyzed: **682**
- Over bets: **259**
- Under bets: **423**
- Consensus bets (all 3 models agree): **339**
- Non-consensus bets: **343**

### Betting Assumptions

- **Odds**: -110 (American odds)
- **Breakeven win rate**: 52.38%
- **Win payout**: +0.909 units (risk 1.1 to win 1.0)
- **Loss**: -1.1 units

## Complete Results

Results stratified by bet type, consensus, and edge threshold:

| Bet Type | Consensus | Edge Threshold | # Bets | Wins | Losses | Win Rate | Total Profit | Total Wagered | ROI |
|----------|-----------|----------------|--------|------|--------|----------|--------------|---------------|-----|
| Over | Yes | 0% | 128 | 66.0 | 62.0 | 51.56% | -8.21 | 140.80 | -5.83% |
| Over | Yes | 1% | 77 | 37.0 | 40.0 | 48.05% | -10.37 | 84.70 | -12.24% |
| Over | Yes | 2% | 34 | 18.0 | 16.0 | 52.94% | -1.24 | 37.40 | -3.31% |
| Over | Yes | 3% | 7 | 5.0 | 2.0 | 71.43% | 2.34 | 7.70 | 30.45% |
| Over | No | 0% | 131 | 65.0 | 66.0 | 49.62% | -13.52 | 144.10 | -9.38% |
| Over | No | 1% | 117 | 58.0 | 59.0 | 49.57% | -12.18 | 128.70 | -9.46% |
| Over | No | 2% | 82 | 42.0 | 40.0 | 51.22% | -5.82 | 90.20 | -6.45% |
| Over | No | 3% | 18 | 11.0 | 7.0 | 61.11% | 2.30 | 19.80 | 11.61% |
| Over | No | 4% | 2 | 1.0 | 1.0 | 50.00% | -0.19 | 2.20 | -8.68% |
| Under | Yes | 0% | 211 | 110.0 | 101.0 | 52.13% | -11.11 | 232.10 | -4.79% |
| Under | Yes | 1% | 110 | 60.0 | 50.0 | 54.55% | -0.46 | 121.00 | -0.38% |
| Under | Yes | 2% | 38 | 23.0 | 15.0 | 60.53% | 4.41 | 41.80 | 10.54% |
| Under | Yes | 3% | 8 | 3.0 | 5.0 | 37.50% | -2.77 | 8.80 | -31.51% |
| Under | Yes | 4% | 1 | 1.0 | 0.0 | 100.00% | 0.91 | 1.10 | 82.64% |
| Under | No | 0% | 212 | 101.0 | 111.0 | 47.64% | -30.29 | 233.20 | -12.99% |
| Under | No | 1% | 179 | 80.0 | 99.0 | 44.69% | -36.18 | 196.90 | -18.37% |
| Under | No | 2% | 109 | 44.0 | 65.0 | 40.37% | -31.50 | 119.90 | -26.28% |
| Under | No | 3% | 29 | 14.0 | 15.0 | 48.28% | -3.77 | 31.90 | -11.83% |
| Under | No | 4% | 7 | 3.0 | 4.0 | 42.86% | -1.67 | 7.70 | -21.73% |

## Key Insights

### Best Performing Strategy

- **Bet Type**: Under
- **Consensus**: Yes
- **Edge Threshold**: 4%
- **ROI**: 82.64%
- **Win Rate**: 100.00%
- **Number of Bets**: 1

### Worst Performing Strategy

- **Bet Type**: Under
- **Consensus**: Yes
- **Edge Threshold**: 3%
- **ROI**: -31.51%
- **Win Rate**: 37.50%
- **Number of Bets**: 8

### Edge Threshold Impact

- **0% edge**: Avg ROI = -8.25%, Total bets = 682
- **1% edge**: Avg ROI = -10.11%, Total bets = 483
- **2% edge**: Avg ROI = -6.37%, Total bets = 263
- **3% edge**: Avg ROI = -0.32%, Total bets = 62
- **4% edge**: Avg ROI = 17.41%, Total bets = 10

### Consensus Impact

- **Consensus bets**: Avg ROI = 7.29%, Total bets = 614
- **Non-consensus bets**: Avg ROI = -11.36%, Total bets = 886

### Over vs Under Performance

- **Over bets**: Avg ROI = -1.48%, Total bets = 596
- **Under bets**: Avg ROI = -3.47%, Total bets = 904

## Methodology

1. **Median Calculation**: For each game, calculate the median of KP, BT, and HA projections
2. **Bet Direction**: 
   - Over bet: median > opening_total
   - Under bet: median < opening_total
3. **Consensus Flag**:
   - Yes: All three models agree on direction
   - No: Models disagree on direction
4. **Edge Thresholds**: Filter bets by minimum edge (0%, 1%, 2%, 3%, 4%)
5. **ROI Calculation**: (Total Profit / Total Wagered) × 100

## Data Quality Notes

- Only includes completed games
- Excludes games with missing model predictions or opening totals
- Uses `over_hit` and `under_hit` columns to grade bets
- Edges from `opening_over_edge` and `opening_under_edge` columns
