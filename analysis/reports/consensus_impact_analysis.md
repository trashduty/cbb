# Consensus Flag Impact on Model Performance (Corrected)

Edge and consensus both measured against the SAME baseline:
- Spreads: `closing_spread` (market consensus line)
- Totals: `market_total` (market consensus total)

Consensus = all 4 models agree on direction vs market line.

---

## Spreads: KP+BT (vs Market Consensus)

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | All 4 agree | 358 | 176 | 49.2% | -6.1% |
| 0% | Disagree | 352 | 186 | 52.8% | +0.9% |
| 0% | **ALL** | 728 | 367 | 50.4% | -3.8% |
| | | | | | |
| 1% | All 4 agree | 275 | 131 | 47.6% | -9.1% |
| 1% | Disagree | 175 | 94 | 53.7% | +2.5% |
| 1% | **ALL** | 463 | 229 | 49.5% | -5.6% |
| | | | | | |
| 2% | All 4 agree | 178 | 88 | 49.4% | -5.6% |
| 2% | Disagree | 73 | 41 | 56.2% | +7.2% |
| 2% | **ALL** | 258 | 130 | 50.4% | -3.8% |
| | | | | | |
| 3% | All 4 agree | 105 | 45 | 42.9% | -18.2% |
| 3% | Disagree | 24 | 12 | 50.0% | -4.5% |
| 3% | **ALL** | 133 | 57 | 42.9% | -18.2% |
| | | | | | |
| 4% | All 4 agree | 66 | 30 | 45.5% | -13.2% |
| 4% | Disagree | 11 | 8 | 72.7% | +38.8% |
| 4% | **ALL** | 79 | 38 | 48.1% | -8.2% |

---

## Totals Over: KP+BT+HA (vs Market Consensus)

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | All 4 agree over | 209 | 109 | 52.2% | -0.4% |
| 0% | EM disagrees | 93 | 38 | 40.9% | -22.0% |
| 0% | **ALL** | 302 | 147 | 48.7% | -7.1% |
| | | | | | |
| 1% | All 4 agree over | 207 | 108 | 52.2% | -0.4% |
| 1% | EM disagrees | 36 | 15 | 41.7% | -20.5% |
| 1% | **ALL** | 243 | 123 | 50.6% | -3.4% |
| | | | | | |
| 2% | All 4 agree over | 200 | 104 | 52.0% | -0.7% |
| 2% | EM disagrees | 19 | 7 | 36.8% | -29.7% |
| 2% | **ALL** | 219 | 111 | 50.7% | -3.2% |
| | | | | | |
| 3% | All 4 agree over | 173 | 87 | 50.3% | -4.0% |
| 3% | EM disagrees | 12 | 5 | 41.7% | -20.5% |
| 3% | **ALL** | 185 | 92 | 49.7% | -5.1% |
| | | | | | |
| 4% | All 4 agree over | 152 | 75 | 49.3% | -5.8% |
| 4% | EM disagrees | 3 | 1 | 33.3% | -36.4% |
| 4% | **ALL** | 155 | 76 | 49.0% | -6.4% |

---

## Totals Under: KP+BT+HA (vs Market Consensus)

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | All 4 agree under | 256 | 118 | 46.1% | -12.0% |
| 0% | EM disagrees | 159 | 88 | 55.3% | +5.7% |
| 0% | **ALL** | 415 | 206 | 49.6% | -5.2% |
| | | | | | |
| 1% | All 4 agree under | 254 | 116 | 45.7% | -12.8% |
| 1% | EM disagrees | 89 | 48 | 53.9% | +3.0% |
| 1% | **ALL** | 343 | 164 | 47.8% | -8.7% |
| | | | | | |
| 2% | All 4 agree under | 239 | 112 | 46.9% | -10.5% |
| 2% | EM disagrees | 50 | 31 | 62.0% | +18.4% |
| 2% | **ALL** | 289 | 143 | 49.5% | -5.5% |
| | | | | | |
| 3% | All 4 agree under | 213 | 100 | 46.9% | -10.4% |
| 3% | EM disagrees | 25 | 13 | 52.0% | -0.7% |
| 3% | **ALL** | 238 | 113 | 47.5% | -9.4% |
| | | | | | |
| 4% | All 4 agree under | 181 | 84 | 46.4% | -11.4% |
| 4% | EM disagrees | 10 | 6 | 60.0% | +14.5% |
| 4% | **ALL** | 191 | 90 | 47.1% | -10.0% |

---

## Key Takeaways

- **Spread 2%+**: Consensus -5.6% (178g) vs Disagree +7.2% (73g) → **Disagree better**
- **Over 2%+**: Consensus -0.7% (200g) vs Disagree -29.7% (19g) → **Consensus better**
- **Under 2%+**: Consensus -10.5% (239g) vs Disagree +18.4% (50g) → **Disagree better**
- **Spread 3%+**: Consensus -18.2% (105g) vs Disagree -4.5% (24g) → **Disagree better**
- **Over 3%+**: Consensus -4.0% (173g) vs Disagree -20.5% (12g) → **Consensus better**
- **Under 3%+**: Consensus -10.4% (213g) vs Disagree -0.7% (25g) → **Disagree better**

## Methodology Note

Previous version had a bug: the consensus flag was calculated against `market_total`/`Consensus Spread`
but edge was calculated against `opening_total`/`opening_spread`. These differ in ~89% of games for totals
and ~66% for spreads. This version uses `market_total` and `closing_spread` consistently for both.