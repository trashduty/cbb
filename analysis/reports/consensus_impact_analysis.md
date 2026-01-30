# Consensus Flag Impact on Model Performance

Does requiring ALL models to agree (consensus=1) improve ROI for our best combos?

---

## Spreads: KP+BT (Non-Regressed)

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | Yes | 406 | 196 | 48.3% | -7.8% |
| 0% | No | 313 | 160 | 51.1% | -2.4% |
| 0% | All | 719 | 356 | 49.5% | -5.5% |
| | | | | | |
| 1% | Yes | 263 | 130 | 49.4% | -5.6% |
| 1% | No | 178 | 89 | 50.0% | -4.5% |
| 1% | All | 441 | 219 | 49.7% | -5.2% |
| | | | | | |
| 2% | Yes | 148 | 70 | 47.3% | -9.7% |
| 2% | No | 91 | 48 | 52.7% | +0.7% |
| 2% | All | 239 | 118 | 49.4% | -5.7% |
| | | | | | |
| 3% | Yes | 70 | 31 | 44.3% | -15.5% |
| 3% | No | 38 | 18 | 47.4% | -9.6% |
| 3% | All | 108 | 49 | 45.4% | -13.4% |
| | | | | | |
| 4% | Yes | 33 | 14 | 42.4% | -19.0% |
| 4% | No | 15 | 11 | 73.3% | +40.0% |
| 4% | All | 48 | 25 | 52.1% | -0.6% |

---

## Totals Over: KP+BT+HA (Non-Regressed)

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | Yes | 102 | 50 | 49.0% | -6.4% |
| 0% | No | 155 | 78 | 50.3% | -3.9% |
| 0% | All | 257 | 128 | 49.8% | -4.9% |
| | | | | | |
| 1% | Yes | 60 | 28 | 46.7% | -10.9% |
| 1% | No | 101 | 50 | 49.5% | -5.5% |
| 1% | All | 161 | 78 | 48.4% | -7.5% |
| | | | | | |
| 2% | Yes | 39 | 21 | 53.8% | +2.8% |
| 2% | No | 55 | 29 | 52.7% | +0.7% |
| 2% | All | 94 | 50 | 53.2% | +1.5% |
| | | | | | |
| 3% | Yes | 19 | 11 | 57.9% | +10.5% |
| 3% | No | 32 | 19 | 59.4% | +13.4% |
| 3% | All | 51 | 30 | 58.8% | +12.3% |
| | | | | | |
| 4% | Yes | 10 | 5 | 50.0% | -4.5% |
| 4% | No | 18 | 8 | 44.4% | -15.2% |
| 4% | All | 28 | 13 | 46.4% | -11.4% |

---

## Totals Under: KP+BT+HA (Non-Regressed)

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | Yes | 182 | 90 | 49.5% | -5.6% |
| 0% | No | 260 | 129 | 49.6% | -5.3% |
| 0% | All | 442 | 219 | 49.5% | -5.4% |
| | | | | | |
| 1% | Yes | 145 | 76 | 52.4% | +0.1% |
| 1% | No | 177 | 91 | 51.4% | -1.8% |
| 1% | All | 322 | 167 | 51.9% | -1.0% |
| | | | | | |
| 2% | Yes | 94 | 50 | 53.2% | +1.5% |
| 2% | No | 107 | 51 | 47.7% | -9.0% |
| 2% | All | 201 | 101 | 50.2% | -4.1% |
| | | | | | |
| 3% | Yes | 58 | 37 | 63.8% | +21.8% |
| 3% | No | 63 | 32 | 50.8% | -3.0% |
| 3% | All | 121 | 69 | 57.0% | +8.9% |
| | | | | | |
| 4% | Yes | 29 | 19 | 65.5% | +25.1% |
| 4% | No | 27 | 12 | 44.4% | -15.2% |
| 4% | All | 56 | 31 | 55.4% | +5.7% |

---

## Summary

**Consensus = All 4 models (KP, BT, EM, HA) agree on direction vs market.**

For spreads, consensus requires all 4 model spreads on the same side of market spread.
For totals, consensus requires all 4 models above (over) or below (under) the market total.

Note: The consensus flag requires ALL 4 models to have data and agree,
while the combo edge only uses the specified models (KP+BT or KP+BT+HA).
So consensus acts as an additional filter on top of the combo edge.

## Key Takeaways

**Spreads (KP+BT):** Consensus actually HURTS. At 2%+ edge, consensus games go 47.3% / -9.7% ROI while non-consensus games go 52.7% / +0.7% ROI. At 4%+ edge, the split is dramatic: consensus 42.4% vs non-consensus 73.3%. This suggests that when all 4 models pile on the same side of a spread, the market has already priced it in.

**Overs (KP+BT+HA):** Consensus makes little difference. Both consensus and non-consensus show similar performance at most thresholds. Slight edge to consensus at 2% (+2.8% vs +0.7%) but non-consensus is better at 3% (+13.4% vs +10.5%).

**Unders (KP+BT+HA):** Consensus is a strong signal. At 2%+ edge, consensus unders go 53.2% / +1.5% ROI while non-consensus goes 47.7% / -9.0%. At 3%+ edge, the gap widens: consensus 63.8% / +21.8% ROI vs non-consensus 50.8% / -3.0%. At 4%+, consensus hits 65.5% / +25.1%.

**Bottom line:**
- **Spreads**: Do NOT require consensus (contrarian signal)
- **Overs**: Consensus doesn't matter much
- **Unders**: REQUIRE consensus for best results (3%+ edge + consensus = 63.8% win rate, +21.8% ROI)