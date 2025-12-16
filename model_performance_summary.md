# Individual Model Performance Summary

Report generated: 2025-12-16 05:30:38

## Spread Predictions

| Model | Accuracy | MAE | RMSE | Games |
|-------|----------|-----|------|-------|
| Hasla | 50.28% | 21.20 | 27.69 | 726 |
| Barttorvik | 50.00% | 20.80 | 27.45 | 788 |
| Evan Miya | 49.88% | 21.25 | 27.83 | 808 |
| Kenpom | 48.98% | 21.11 | 27.46 | 788 |

## Moneyline (Win Probability) Predictions

| Model | Accuracy | Brier Score | Log Loss | Games |
|-------|----------|-------------|----------|-------|
| Kenpom | 75.51% | 0.1667 | 0.4993 | 788 |
| Evan Miya | 75.00% | 0.1710 | 0.5154 | 808 |
| Barttorvik | 72.66% | 0.1749 | 0.5192 | 790 |

## Total Points Predictions

| Model | MAE | RMSE | Games |
|-------|-----|------|-------|
| Evan Miya | 12.83 | 16.09 | 808 |
| Kenpom | 13.22 | 16.35 | 788 |
| Barttorvik | 13.23 | 16.51 | 790 |
| Hasla | 13.39 | 16.59 | 726 |

## Key Insights

- **Best Spread Predictor:** Hasla (50.28% accuracy)
- **Best Moneyline Predictor:** Kenpom (75.51% accuracy)
- **Best Total Predictor:** Evan Miya (MAE: 12.83 points)

## Notes

- **Spread Accuracy:** Percentage of games where the model correctly predicted whether the team would cover the spread.
- **MAE (Mean Absolute Error):** Average absolute difference between predicted and actual values.
- **RMSE (Root Mean Square Error):** Square root of average squared differences. Penalizes larger errors more heavily.
- **Brier Score:** Measure of probabilistic prediction accuracy. Lower is better. Range: [0, 1]
- **Log Loss:** Logarithmic loss for probabilistic predictions. Lower is better.
- **Hasla** does not provide win probability predictions, so it's excluded from moneyline analysis.
