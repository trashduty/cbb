# Totals (Over/Under) Model Combination Analysis

## Results Ranked by RMSE (lower = better)

| Rank | Combination | Games | RMSE | MAE | Accuracy |
|------|-------------|-------|------|-----|----------|
| 1 | BT+EM | 584 | 16.67 | 13.44 | 53.60% |
| 2 | KP+BT+EM | 550 | 16.69 | 13.48 | 54.91% |
| 3 | BT+EM+HA | 563 | 16.74 | 13.48 | 53.82% |
| 4 | KP+BT | 550 | 16.80 | 13.54 | 50.36% |
| 5 | KP+BT+EM+HA | 535 | 16.81 | 13.55 | 54.95% |
| 6 | MARKET ⭐ | 912 | 16.86 | 13.41 | 49.01% |
| 7 | BT+HA | 563 | 16.88 | 13.56 | 50.27% |
| 8 | KP+BT+HA | 535 | 16.89 | 13.59 | 52.52% |
| 9 | BT | 584 | 16.92 | 13.58 | 49.14% |
| 10 | EM | 912 | 17.08 | 13.66 | 54.39% |
| 11 | KP+EM | 878 | 17.16 | 13.74 | 52.05% |
| 12 | EM+HA | 884 | 17.26 | 13.76 | 51.70% |
| 13 | KP | 878 | 17.29 | 13.87 | 52.05% |
| 14 | KP+EM+HA | 856 | 17.32 | 13.82 | 52.57% |
| 15 | KP+HA | 856 | 17.45 | 13.92 | 51.52% |
| 16 | HA | 884 | 17.59 | 13.99 | 50.11% |

⭐ = Market benchmark (opening total)

## Market Benchmark

- **RMSE**: 16.86 points
- **MAE**: 13.41 points
- **Games**: 912

## Best Model Combination: **BT+EM**

- **RMSE**: 16.67 points
- **MAE**: 13.44 points
- **Accuracy**: 53.60%
- **Games**: 584

**Beats market by 0.19 RMSE points**

## Legend

- **KP** = KenPom
- **BT** = Barttorvik
- **EM** = EvanMiya
- **HA** = Hasla
- **MARKET** = Opening total line

## Methodology

- For each model combination, the total is calculated as the **average** of included model projections.
- **RMSE** measures how close predictions are to actual game totals (lower = better).
- **Accuracy** measures % of games where model correctly predicted over/under vs opening total.
- Only games with opening total data are included.
