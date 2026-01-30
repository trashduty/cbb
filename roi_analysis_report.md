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
- **Win payout**: +1.0 units (risk 1.1 to win 1.0)
- **Loss**: -1.1 units

## Complete Results

Results stratified by bet type, consensus, and edge threshold:

| Bet Type | Consensus | Edge Threshold | # Bets | Wins | Losses | Win Rate | Total Profit | Total Wagered | ROI |
|----------|-----------|----------------|--------|------|--------|----------|--------------|---------------|-----|
| Over | Yes | 0% | 26 | 14.0 | 12.0 | 53.85% | 0.80 | 28.60 | 2.80% |
| Over | Yes | 1% | 6 | 3.0 | 3.0 | 50.00% | -0.30 | 6.60 | -4.55% |
| Over | Yes | 2% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |
| Over | Yes | 3% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |
| Over | No | 0% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |
| Over | No | 1% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |
| Under | Yes | 0% | 44 | 25.0 | 19.0 | 56.82% | 4.10 | 48.40 | 8.47% |
| Under | Yes | 1% | 12 | 7.0 | 5.0 | 58.33% | 1.50 | 13.20 | 11.36% |
| Under | Yes | 2% | 3 | 3.0 | 0.0 | 100.00% | 3.00 | 3.30 | 90.91% |
| Under | Yes | 3% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |
| Under | No | 0% | 8 | 5.0 | 3.0 | 62.50% | 1.70 | 8.80 | 19.32% |
| Under | No | 1% | 3 | 2.0 | 1.0 | 66.67% | 0.90 | 3.30 | 27.27% |
| Under | No | 2% | 2 | 1.0 | 1.0 | 50.00% | -0.10 | 2.20 | -4.55% |
| Under | No | 3% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |
| Under | No | 4% | 1 | 1.0 | 0.0 | 100.00% | 1.00 | 1.10 | 90.91% |

## Key Insights

### Best Performing Strategy

- **Bet Type**: Over
- **Consensus**: Yes
- **Edge Threshold**: 2%
- **ROI**: 90.91%
- **Win Rate**: 100.00%
- **Number of Bets**: 1

### Worst Performing Strategy

- **Bet Type**: Over
- **Consensus**: Yes
- **Edge Threshold**: 1%
- **ROI**: -4.55%
- **Win Rate**: 50.00%
- **Number of Bets**: 6

### Edge Threshold Impact

- **0% edge**: Avg ROI = 30.37%, Total bets = 79
- **1% edge**: Avg ROI = 31.25%, Total bets = 22
- **2% edge**: Avg ROI = 59.09%, Total bets = 6
- **3% edge**: Avg ROI = 90.91%, Total bets = 3
- **4% edge**: Avg ROI = 90.91%, Total bets = 1

### Consensus Impact

- **Consensus bets**: Avg ROI = 47.72%, Total bets = 94
- **Non-consensus bets**: Avg ROI = 57.95%, Total bets = 17

### Over vs Under Performance

- **Over bets**: Avg ROI = 60.31%, Total bets = 36
- **Under bets**: Avg ROI = 47.28%, Total bets = 75

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
