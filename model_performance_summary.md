# Model Performance Summary

**Report generated:** 2026-01-13 22:24:00
**Data range:** 2025-11-04 to 2026-01-14
**Total games graded:** 929

---

## Spread Predictions (ATS)

| Model | ATS Accuracy | MAE | RMSE | Games |
|-------|--------------|-----|------|-------|
| Barttorvik | 50.16% | 21.62 | 29.00 | 614 |
| Kenpom | 49.89% | 19.29 | 25.85 | 893 |
| Hasla | 49.33% | 20.59 | 27.49 | 898 |
| Evanmiya | 48.59% | 19.71 | 26.76 | 929 |

## Moneyline (Win Probability) Predictions

| Model | Accuracy | Brier Score | Log Loss | Games |
|-------|----------|-------------|----------|-------|
| Barttorvik | 75.89% | 0.1690 | 0.5004 | 618 |
| Evanmiya | 73.41% | 0.1737 | 0.5104 | 929 |
| Kenpom | 73.06% | 0.1740 | 0.5114 | 902 |

## Total Points Predictions

| Model | MAE | RMSE | Games |
|-------|-----|------|-------|
| Barttorvik | 13.52 | 16.91 | 614 |
| Evanmiya | 13.69 | 17.21 | 929 |
| Kenpom | 13.85 | 17.38 | 893 |
| Hasla | 14.01 | 17.70 | 898 |

## Over/Under Predictions

| Model | Over Accuracy | Under Accuracy | Games |
|-------|---------------|----------------|-------|
| Barttorvik | 50.85% | 49.15% | 590 |
| Kenpom | 50.63% | 49.37% | 867 |
| Hasla | 50.40% | 49.60% | 873 |
| Evanmiya | 50.28% | 49.72% | 901 |

---

## Betting Edge Performance by Tier

Performance of consensus model predictions by edge size (from `model_record.csv`):

### Spread Bets

| Edge Tier | Record | Win Rate | Profit (Units) |
|-----------|--------|----------|----------------|
| 0-1.9% | 110-105 | 51.2% | -5.01 |
| 2-3.9% | 38-44 | 46.3% | -9.46 |
| 4-5.9% | 21-15 | 58.3% | +4.09 |
| 6%+ | 10-12 | 45.5% | -2.91 |
| **Total** | **179-176** | **50.4%** | **-13.29** |

### Moneyline Bets

| Edge Tier | Record | Win Rate | Profit (Units) |
|-----------|--------|----------|----------------|
| 0-1.9% | 71-101 | 41.3% | -36.46 |
| 2-3.9% | 8-9 | 47.1% | -1.73 |
| 4-5.9% | 0-6 | 0.0% | -6.00 |
| 6%+ | 1-2 | 33.3% | -1.09 |
| **Total** | **80-118** | **40.4%** | **-45.28** |

### Over Bets

| Edge Tier | Record | Win Rate | Profit (Units) |
|-----------|--------|----------|----------------|
| 0-1.9% | 34-36 | 48.6% | -5.09 |
| 2-3.9% | 2-4 | 33.3% | -2.18 |
| 6%+ | 2-0 | 100.0% | +1.82 |
| **Total** | **38-40** | **48.7%** | **-5.45** |

### Under Bets

| Edge Tier | Record | Win Rate | Profit (Units) |
|-----------|--------|----------|----------------|
| 0-1.9% | 64-56 | 53.3% | +2.18 |
| 2-3.9% | 8-8 | 50.0% | -0.73 |
| 6%+ | 2-0 | 100.0% | +1.82 |
| **Total** | **74-64** | **53.6%** | **+3.27** |

---

## Key Insights

- **Best Spread Predictor (ATS):** Barttorvik (50.16%)
- **Best Spread Error (MAE):** Kenpom (19.29 points)
- **Best Moneyline Predictor:** Barttorvik (75.89% accuracy, 0.169 Brier)
- **Best Total Predictor:** Barttorvik (13.52 MAE)
- **Most Profitable Bet Type:** Under bets (+3.27 units, 53.6% win rate)
- **Best Edge Tier for Spreads:** 4-5.9% edge (58.3% win rate, +4.09 units)

## Notes

- **ATS Accuracy:** Percentage of games where the model correctly predicted ATS outcome relative to closing spread
- **MAE (Mean Absolute Error):** Average absolute difference between predicted and actual values
- **RMSE (Root Mean Square Error):** Penalizes larger errors more heavily
- **Brier Score:** Probabilistic prediction accuracy (lower is better, range 0-1)
- **Log Loss:** Logarithmic loss for probabilistic predictions (lower is better)
- **Hasla** does not provide win probability predictions, so it's excluded from moneyline analysis
- **Edge calculations** use the consensus median of all model predictions weighted against market lines
- **Profit units** assume standard -110 juice on spread/total bets
