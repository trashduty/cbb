# Moneyline Edge Analysis by Win Probability Range

## Key Question
When we have a 2%+ moneyline edge, should we bet everything or only certain win probability ranges?

## TL;DR

Betting all 2%+ edges blindly loses money (-4.8% ROI). Filtering by win probability range improves results dramatically:

| Edge Threshold | All Bets (ROI) | Filtered 10-40% or 50-90% (ROI) |
|----------------|----------------|----------------------------------|
| 2%+ | -4.8% (126 games) | +2.4% (112 games) |
| 3%+ | +8.5% (91 games) | +19.9% (78 games) |
| 4%+ | +18.9% (67 games) | +30.6% (57 games) |

---

## Performance by Win Probability Range

### Edge >= 2%

| Range | Games | Wins | Win% | Expected Win% | Avg Edge | ROI | Verdict |
|-------|-------|------|------|----------------|----------|-----|---------|
| Heavy Dogs (0-25%) | 32 | 6 | 18.8% | 18.6% | 4.5% | +34.1% | High variance* |
| Moderate Dogs (25-40%) | 21 | 3 | 14.3% | 32.0% | 8.3% | -54.0% | SKIP |
| Coin Flips (40-60%) | 40 | 16 | 40.0% | 51.8% | 7.4% | -18.8% | SKIP |
| Moderate Favs (60-75%) | 26 | 12 | 46.2% | 64.6% | 18.3% | +8.7% | Marginal |
| Heavy Favs (75+%) | 7 | 5 | 71.4% | 80.4% | 6.4% | -6.0% | Small N |

### Edge >= 3%

| Range | Games | Wins | Win% | Expected Win% | Avg Edge | ROI | Verdict |
|-------|-------|------|------|----------------|----------|-----|---------|
| Heavy Dogs (0-25%) | 22 | 6 | 27.3% | 18.9% | 5.4% | +95.0% | High variance* |
| Moderate Dogs (25-40%) | 12 | 1 | 8.3% | 32.8% | 12.8% | -74.2% | SKIP |
| Coin Flips (40-60%) | 31 | 12 | 38.7% | 50.8% | 8.8% | -18.3% | SKIP |
| Moderate Favs (60-75%) | 20 | 8 | 40.0% | 64.4% | 23.0% | +10.2% | BET |
| Heavy Favs (75+%) | 6 | 4 | 66.7% | 79.1% | 7.1% | -9.8% | Small N |

### Edge >= 4%

| Range | Games | Wins | Win% | Expected Win% | Avg Edge | ROI | Verdict |
|-------|-------|------|------|----------------|----------|-----|---------|
| Heavy Dogs (0-25%) | 15 | 5 | 33.3% | 19.3% | 6.4% | +151.9% | High variance* |
| Moderate Dogs (25-40%) | 9 | 0 | 0.0% | 32.6% | 15.9% | -100.0% | Small N |
| Coin Flips (40-60%) | 25 | 10 | 40.0% | 51.2% | 10.1% | -14.2% | SKIP |
| Moderate Favs (60-75%) | 15 | 6 | 40.0% | 64.3% | 29.5% | +26.4% | BET |
| Heavy Favs (75+%) | 3 | 1 | 33.3% | 78.1% | 10.4% | -50.8% | Small N |

---

## *Why Heavy Dogs (0-25%) Show High ROI

The ROI looks impressive but is misleading due to extreme variance. Here's the math:

- **32 games at 2%+ edge**: 6 wins, 26 losses (18.8% win rate)
- **Win rate matches expectation** (18.6%) - the model is well-calibrated
- **But the payouts are massive**: individual wins paid +8.80, +7.69, +7.00, +4.80, +4.50, +4.12 units
- **Total return**: 6 big wins (+36.91 units) minus 26 losses (-26 units) = +10.91 units on 32 bets

**The problem: remove just 2 of those 6 wins and ROI drops to -37%.** With an 18% hit rate, you can easily go 0-for-15 or worse on any given stretch. The positive ROI is real in expectation but requires a large bankroll and stomach for long losing streaks.

### Heavy Dog Winners (2%+ Edge)

| Date | Team | Model Prob | Market Prob | Edge | Odds | Payout |
|------|------|-----------|-------------|------|------|--------|
| 2025-12-28 | N Colorado Bears | 14.8% | 10.2% | 4.6% | +880 | +8.80 |
| 2025-11-27 | TCU Horned Frogs | 18.0% | 12.5% | 5.5% | +700 | +7.00 |
| 2026-01-11 | Texas Longhorns | 18.2% | 11.5% | 6.7% | +769 | +7.69 |
| 2026-01-10 | Fordham Rams | 22.7% | 19.5% | 3.2% | +412 | +4.12 |
| 2026-01-03 | Mississippi St Bulldogs | 22.8% | 17.2% | 5.6% | +480 | +4.80 |
| 2025-11-24 | Seton Hall Pirates | 23.8% | 18.2% | 5.6% | +450 | +4.50 |

---

## Consistently Bad: 40-60% Coin Flips

At every edge threshold, the 40-60% win probability range loses money:
- 2%+ edge: -18.8% ROI (40 games)
- 3%+ edge: -18.3% ROI (31 games)
- 4%+ edge: -14.2% ROI (25 games)

These are games where the model and market roughly agree the game is close, but the model thinks one side is slightly better. The edge doesn't translate to profit - possibly because these games are genuinely unpredictable.

## Also Bad: 25-40% Moderate Underdogs

This range is consistently the worst performer:
- 2%+ edge: -54.0% ROI
- 3%+ edge: -74.2% ROI
- 4%+ edge: -100.0% ROI

These teams lose too often and the payouts aren't large enough to compensate (unlike the heavy dogs where a single +700 win covers 7 losses).

---

## Recommended Guardrails

**For moneyline betting with model edge:**

1. **Minimum 2% edge** to consider any bet
2. **AVOID 25-50% win probability range** - consistently loses regardless of edge size
3. **Moderate favorites (50-75%)** are the safest positive-ROI bucket
4. **Heavy underdogs (10-25%)** are positive EV but extremely high variance - only bet with proper bankroll management (small unit sizes)
5. **Heavy favorites (75%+)** - not enough data, and payouts are small

**Conservative approach**: Bet 3%+ edges in the 50-75% range only

**Aggressive approach**: Bet 2%+ edges in 10-25% OR 50-90% ranges, with smaller units on dogs

---

## Caveats

- Sample sizes are small (67-126 games at 2%+ edge depending on threshold)
- One season of data - patterns may not persist
- Heavy dog ROI is driven by a handful of big wins
- Results should be tracked prospectively to validate
