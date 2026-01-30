# Spread Model Combination Analysis

## Results Ranked by RMSE (lower = better)

| Rank | Combination | Games | RMSE | MAE | Accuracy |
|------|-------------|-------|------|-----|----------|
| 1 | KP | 871 | 25.70 | 19.20 | 50.29% |
| 2 | KP+EM | 871 | 25.94 | 19.28 | 49.60% |
| 3 | KP+EM+HA | 848 | 26.15 | 19.48 | 51.42% |
| 4 | KP+HA | 848 | 26.22 | 19.63 | 50.00% |
| 5 | EM | 906 | 26.48 | 19.56 | 48.34% |
| 6 | EM+HA | 876 | 26.77 | 19.95 | 50.68% |
| 7 | MARKET ⭐ | 906 | 27.09 | 20.04 | 48.23% |
| 8 | HA | 876 | 27.24 | 20.49 | 49.89% |
| 9 | KP+BT | 556 | 27.99 | 20.86 | 48.20% |
| 10 | KP+BT+EM | 556 | 28.08 | 20.85 | 47.66% |
| 11 | KP+BT+HA | 540 | 28.26 | 21.06 | 50.00% |
| 12 | KP+BT+EM+HA | 540 | 28.26 | 20.99 | 50.56% |
| 13 | BT+EM | 591 | 28.53 | 21.17 | 48.39% |
| 14 | BT | 591 | 28.57 | 21.31 | 49.92% |
| 15 | BT+EM+HA | 568 | 28.81 | 21.44 | 51.41% |
| 16 | BT+HA | 568 | 28.92 | 21.63 | 51.76% |

⭐ = Market benchmark (opening line)

## Market Benchmark

- **RMSE**: 27.09 points
- **MAE**: 20.04 points
- **Games**: 906

## Best Model Combination: **KP**

- **RMSE**: 25.70 points
- **MAE**: 19.20 points
- **Accuracy**: 50.29%
- **Games**: 871

**Beats market by 1.39 RMSE points**

## Legend

- **KP** = KenPom
- **BT** = Barttorvik
- **EM** = EvanMiya
- **HA** = Hasla
- **MARKET** = Opening spread line

## Methodology

- For each model combination, the spread is calculated as the **average** of included model spreads.
- **RMSE** measures how close predictions are to actual game margins (lower = better).
- **Accuracy** measures % of games where model correctly predicted which side covers the opening spread.
- Only games with opening spread data are included.
