# Consensus Flag Impact on Model Performance

Does requiring the models IN the combo to all agree improve ROI?

Edge and consensus both measured against market consensus lines.

- **Spreads**: KP+BT combo → consensus = KP and BT both agree on direction
- **Totals**: KP+BT+HA combo → consensus = KP, BT, and HA all agree on direction

---

## Spreads: KP+BT

Consensus = KP and BT both agree on direction vs closing spread.

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | KP+BT agree | 477 | 238 | 49.9% | -4.7% |
| 0% | KP+BT disagree | 259 | 133 | 51.4% | -2.0% |
| 0% | **ALL** | 736 | 371 | 50.4% | -3.8% |
| | | | | | |
| 1% | KP+BT agree | 395 | 198 | 50.1% | -4.3% |
| 1% | KP+BT disagree | 73 | 34 | 46.6% | -11.1% |
| 1% | **ALL** | 468 | 232 | 49.6% | -5.4% |
| | | | | | |
| 2% | KP+BT agree | 256 | 128 | 50.0% | -4.5% |
| 2% | KP+BT disagree | 6 | 4 | 66.7% | +27.3% |
| 2% | **ALL** | 262 | 132 | 50.4% | -3.8% |
| | | | | | |
| 3% | KP+BT agree | 136 | 58 | 42.6% | -18.6% |
| 3% | KP+BT disagree | 0 | - | - | - |
| 3% | **ALL** | 136 | 58 | 42.6% | -18.6% |
| | | | | | |
| 4% | KP+BT agree | 81 | 39 | 48.1% | -8.1% |
| 4% | KP+BT disagree | 0 | - | - | - |
| 4% | **ALL** | 81 | 39 | 48.1% | -8.1% |

---

## Totals Over: KP+BT+HA

Consensus = KP, BT, and HA all project total above market_total.

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | KP+BT+HA agree over | 224 | 115 | 51.3% | -2.0% |
| 0% | Disagree | 82 | 34 | 41.5% | -20.8% |
| 0% | **ALL** | 306 | 149 | 48.7% | -7.0% |
| | | | | | |
| 1% | KP+BT+HA agree over | 221 | 113 | 51.1% | -2.4% |
| 1% | Disagree | 26 | 12 | 46.2% | -11.9% |
| 1% | **ALL** | 247 | 125 | 50.6% | -3.4% |
| | | | | | |
| 2% | KP+BT+HA agree over | 208 | 107 | 51.4% | -1.8% |
| 2% | Disagree | 13 | 6 | 46.2% | -11.9% |
| 2% | **ALL** | 221 | 113 | 51.1% | -2.4% |
| | | | | | |
| 3% | KP+BT+HA agree over | 179 | 90 | 50.3% | -4.0% |
| 3% | Disagree | 8 | 4 | 50.0% | -4.5% |
| 3% | **ALL** | 187 | 94 | 50.3% | -4.0% |
| | | | | | |
| 4% | KP+BT+HA agree over | 155 | 77 | 49.7% | -5.2% |
| 4% | Disagree | 2 | 1 | 50.0% | -4.5% |
| 4% | **ALL** | 157 | 78 | 49.7% | -5.2% |

---

## Totals Under: KP+BT+HA

Consensus = KP, BT, and HA all project total below market_total.

| Threshold | Consensus | Games | Wins | Win% | ROI |
|-----------|-----------|-------|------|------|-----|
| 0% | KP+BT+HA agree under | 292 | 136 | 46.6% | -11.1% |
| 0% | Disagree | 127 | 71 | 55.9% | +6.7% |
| 0% | **ALL** | 419 | 207 | 49.4% | -5.7% |
| | | | | | |
| 1% | KP+BT+HA agree under | 290 | 134 | 46.2% | -11.8% |
| 1% | Disagree | 56 | 31 | 55.4% | +5.7% |
| 1% | **ALL** | 346 | 165 | 47.7% | -9.0% |
| | | | | | |
| 2% | KP+BT+HA agree under | 265 | 127 | 47.9% | -8.5% |
| 2% | Disagree | 26 | 17 | 65.4% | +24.8% |
| 2% | **ALL** | 291 | 144 | 49.5% | -5.5% |
| | | | | | |
| 3% | KP+BT+HA agree under | 231 | 110 | 47.6% | -9.1% |
| 3% | Disagree | 8 | 4 | 50.0% | -4.5% |
| 3% | **ALL** | 239 | 114 | 47.7% | -8.9% |
| | | | | | |
| 4% | KP+BT+HA agree under | 191 | 90 | 47.1% | -10.0% |
| 4% | Disagree | 1 | 1 | 100.0% | +90.9% |
| 4% | **ALL** | 192 | 91 | 47.4% | -9.5% |

---

## Key Takeaways

### Edge >= 2%+

- **Spread**: Agree -4.5% (256g) vs Disagree +27.3% (6g) → **Disagree**
- **Over**: Agree -1.8% (208g) vs Disagree -11.9% (13g) → **Agree**
- **Under**: Agree -8.5% (265g) vs Disagree +24.8% (26g) → **Disagree**

### Edge >= 3%+

- **Over**: Agree -4.0% (179g) vs Disagree -4.5% (8g) → **Agree**
- **Under**: Agree -9.1% (231g) vs Disagree -4.5% (8g) → **Disagree**

### Edge >= 4%+

- **Over**: Agree -5.2% (155g) vs Disagree -4.5% (2g) → **Disagree**
- **Under**: Agree -10.0% (191g) vs Disagree +90.9% (1g) → **Disagree**
