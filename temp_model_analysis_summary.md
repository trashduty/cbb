# Model Combination Analysis Summary

**Date**: January 2025
**Games Analyzed**: ~900 (2025 season through December 30)

---

## How We Incorporated the Market Benchmark

Per feedback, we added the **opening line as a benchmark** to answer: *"Do our models actually beat the market?"*

- **Spreads**: Compare model RMSE vs `opening_spread` RMSE
- **Totals**: Compare model RMSE vs `opening_total` RMSE
- **Moneyline**: Compare model Brier score vs `opening_moneyline` implied probability

This tells us if models add value over simply using the market line.

---

## Results Overview

### 1. Spreads — Best: **KenPom alone**

| Rank | Combination | RMSE | MAE | vs Market |
|------|-------------|------|-----|-----------|
| 1 | KP | 25.70 | 19.20 | **-1.39** ✅ |
| 2 | KP+EM | 25.94 | 19.28 | -1.15 ✅ |
| 3 | KP+EM+HA | 26.15 | 19.48 | -0.94 ✅ |
| 7 | **MARKET** | 27.09 | 20.04 | baseline |
| 16 | BT+HA | 28.92 | 21.63 | +1.83 ❌ |

**Insight**: KenPom alone is the most accurate spread predictor. Adding other models hurts performance. Barttorvik combinations are worst.

---

### 2. Totals — Best: **Barttorvik + EvanMiya**

| Rank | Combination | RMSE | MAE | vs Market |
|------|-------------|------|-----|-----------|
| 1 | BT+EM | 16.67 | 13.44 | **-0.19** ✅ |
| 2 | KP+BT+EM | 16.69 | 13.48 | -0.17 ✅ |
| 3 | BT+EM+HA | 16.74 | 13.48 | -0.12 ✅ |
| 6 | **MARKET** | 16.86 | 13.41 | baseline |
| 16 | HA | 17.59 | 13.99 | +0.73 ❌ |

**Insight**: BT+EM slightly beats the market. Hasla alone is worst. KenPom alone is mediocre for totals.

---

### 3. Moneyline — Best: **MARKET** (models don't beat it)

| Rank | Combination | Brier | Log Loss | Accuracy | vs Market |
|------|-------------|-------|----------|----------|-----------|
| 1 | **MARKET** | 0.1765 | 0.5207 | 71.95% | baseline |
| 2 | KP+BT+EM | 0.1822 | 0.5356 | 72.15% | +0.0057 ❌ |
| 3 | KP+EM | 0.1823 | 0.5353 | 72.70% | +0.0058 ❌ |
| 8 | BT | 0.1848 | 0.5442 | 73.72% | +0.0083 ❌ |

**Insight**: Market has better probability calibration than all models. Models pick winners slightly better (accuracy) but assign worse probabilities.

---

## Recommended Model Usage

| Bet Type | Best Combination | Beats Market? |
|----------|------------------|---------------|
| **Spread** | KenPom alone | ✅ Yes, by 1.39 RMSE |
| **Total** | BT + EM | ✅ Yes, by 0.19 RMSE |
| **Moneyline** | Market (or KP+EM for picks) | ❌ Market is better |

---

## Methodology

- **RMSE** (Root Mean Squared Error): How close predictions are to actual outcomes. Lower = better.
- **MAE** (Mean Absolute Error): Average prediction error in points. Lower = better.
- **Brier Score**: Probability calibration metric. Lower = better. Perfect = 0, random = 0.25.
- **Accuracy**: % of correct picks (spread cover, over/under, winner).

For each combination, predictions are the **simple average** of included models.

---

## Data Notes

- Only games with opening lines are included (ensures apples-to-apples comparison)
- Pushes are excluded from accuracy calculations
- Barttorvik has fewer games (~550-590) due to missing data
- Hasla does not provide win probabilities (excluded from moneyline analysis)

---

## Legend

- **KP** = KenPom
- **BT** = Barttorvik
- **EM** = EvanMiya
- **HA** = Hasla
- **MARKET** = Opening line (spread, total, or moneyline implied prob)
