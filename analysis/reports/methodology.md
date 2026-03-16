# Edge Calculation Methodology

This document explains how edges are calculated for spreads, totals, and moneylines.

---

## Spreads & Totals

Both spreads and totals use the same approach because both sides of the bet pay at standard -110 juice.

### Edge Formula

1. Compute raw model prediction (average of selected models)
2. Round to nearest 0.5 for lookup
3. Look up implied probability from historical lookup tables:
   - `spreads_lookup_combined.csv` for spreads
   - `totals_lookup_combined.csv` for totals
4. Regress toward 50%: `p_final = 0.4 × p_lookup + 0.6 × 0.50`
5. Edge = `p_final - 0.5238` (52.38% is break-even at -110)

### Why Bet Both Directions?

For spreads and totals, both sides pay at -110. If the model says "bet against the spread" (negative edge), the cost is the same -110 as betting "for the spread." So we can use absolute edge and bet in either direction:

- Positive edge → bet on the outcome
- Negative edge → bet against the outcome

---

## Moneylines

Moneylines are different because each side has different odds (-150/+130, -200/+170, etc.).

### Edge Formula

1. Compute **median** win probability across selected models (matches pipeline)
2. Regress toward market: `final_prob = 0.5 × median(models) + 0.5 × market_implied`
3. Edge = `final_prob - market_implied`

### Why Positive Edge Only?

You can't infer one team's moneyline odds by negating the other team's. Each side has independent odds set by the market. So:

- **Positive edge** → bet on that team using their actual posted odds
- **Negative edge** → we do NOT bet the other side (we don't have their actual odds in our data structure)

### ROI Calculation

Uses actual posted `opening_moneyline` odds:

- Win: `profit = ML/100` (plus-money) or `100/|ML|` (minus-money)
- Loss: `profit = -$1`
- ROI = `sum(profits) / num_bets × 100`

---

## What Was Wrong With The Old Analysis

The previous analysis had several issues:

### 1. No Regression

The old script used raw model probabilities with no regression. This produced edges ~2x larger than what the pipeline actually computes.

**Old:** `edge = model_prob - market_implied`

**New:** `edge = (0.5 × model_prob + 0.5 × market_implied) - market_implied`

The new formula simplifies to `edge = 0.5 × (model_prob - market_implied)`, which is exactly half the old edge magnitude.

### 2. Betting Both Directions With abs(edge)

The old script used `abs(edge) >= threshold`, betting both directions:
- Positive edge → bet on team
- Negative edge → bet against team (using `-opening_moneyline`)

This is invalid for moneylines because `-opening_moneyline` is not the opponent's actual odds. The opponent has their own independently-set odds.

### 3. Synthetic Odds

When betting against a team, the old script used `-row['opening_moneyline']` as the payout odds. This is made-up and doesn't reflect real market prices.

---

## Pipeline Reference

The production pipeline computes edges in `src/scrapers/oddsAPI.py`:

- **Spread edge**: Uses lookup tables with `0.6 × market + 0.4 × forecast` blend, then regresses the resulting probability
- **Moneyline edge**: Uses devigged market probability (removes vig from both sides), computes `model_prob - devigged_prob`

The per-combo analysis uses `market_implied` (raw odds without devig) as a proxy since `devigged_prob` isn't stored in `graded_results.csv`. The difference is small (~2-2.5% per side).
