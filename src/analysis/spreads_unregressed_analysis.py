# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "numpy"]
# ///

"""
Spreads Analysis - UNREGRESSED (using lookup tables)

Edge = cover_prob - 52.38% (no regression toward 50%)
"""

import pandas as pd
import numpy as np
from itertools import combinations
from pathlib import Path

IMPLIED_PROB_110 = 110 / 210  # ~0.5238

SPREAD_MODELS = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
SPREAD_COLS = {m: f'spread_{m}' for m in SPREAD_MODELS}
MODEL_ABBREV = {'kenpom': 'KP', 'barttorvik': 'BT', 'evanmiya': 'EM', 'hasla': 'HA'}


def get_total_category(opening_total):
    if pd.isna(opening_total):
        return None
    if opening_total <= 137.5:
        return 1
    elif opening_total <= 145.5:
        return 2
    else:
        return 3


def get_all_combinations(models):
    combos = []
    for r in range(1, len(models) + 1):
        for combo in combinations(models, r):
            combos.append(list(combo))
    return combos


def calculate_roi(wins, losses):
    total = wins + losses
    if total == 0:
        return 0.0
    return ((wins * (100/110)) - losses) / total * 100


def main():
    base_path = Path(__file__).parent.parent.parent

    graded = pd.read_csv(base_path / 'graded_results.csv')
    spreads_lookup = pd.read_csv(base_path / 'spreads_lookup_combined.csv')

    # Home team only
    graded = graded[graded['team'] == graded['home_team']].copy()

    print(f"Total games: {len(graded)}")

    def lookup_cover_prob(total_category, market_spread, model_spread):
        if total_category is None or pd.isna(market_spread) or pd.isna(model_spread):
            return None

        model_spread_rounded = round(model_spread * 2) / 2
        market_spread_rounded = round(market_spread * 2) / 2

        match = spreads_lookup[
            (spreads_lookup['total_category'] == total_category) &
            (spreads_lookup['market_spread'] == market_spread_rounded) &
            (spreads_lookup['model_spread'] == model_spread_rounded)
        ]

        if len(match) > 0:
            return match.iloc[0]['cover_prob']
        return None

    combos = get_all_combinations(SPREAD_MODELS)
    thresholds = [0, 1, 2, 3, 4, 5, 6]

    results = {}

    for threshold in thresholds:
        results[threshold] = {}

        for combo in combos:
            combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

            df = graded.copy()
            df = df[df['opening_spread'].notna() & df['opening_total'].notna() & df['spread_covered'].notna()]

            cols = [SPREAD_COLS[m] for m in combo]
            df = df.dropna(subset=cols)

            if len(df) == 0:
                results[threshold][combo_name] = (0, 0, 0, 0)
                continue

            # Mean of model spreads
            df['combo_spread'] = df[cols].mean(axis=1)
            df['combo_spread_rounded'] = (df['combo_spread'] * 2).round() / 2
            df['total_category'] = df['opening_total'].apply(get_total_category)

            # Lookup probability
            def get_prob(row):
                return lookup_cover_prob(
                    row['total_category'],
                    row['opening_spread'],
                    row['combo_spread_rounded']
                )

            df['cover_prob'] = df.apply(get_prob, axis=1)
            df = df[df['cover_prob'].notna()]

            if len(df) == 0:
                results[threshold][combo_name] = (0, 0, 0, 0)
                continue

            # UNREGRESSED: use cover_prob directly
            df['edge'] = df['cover_prob'] - IMPLIED_PROB_110

            # Filter by threshold
            filtered = df[df['edge'].abs() >= threshold/100].copy()

            if len(filtered) == 0:
                results[threshold][combo_name] = (0, 0, 0, 0)
                continue

            # Bet direction: positive edge = bet cover, negative edge = bet against
            filtered['bet_won'] = filtered.apply(
                lambda row: row['spread_covered'] if row['edge'] > 0 else (1 - row['spread_covered']),
                axis=1
            )

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            roi = calculate_roi(wins, losses)

            results[threshold][combo_name] = (len(filtered), wins, losses, roi)

    # Generate report
    lines = []
    lines.append("# Spreads Analysis - UNREGRESSED (Lookup Tables)")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("### Step 1: Calculate Combo Spread")
    lines.append("- For each model combination, compute the **mean** of the selected model spreads")
    lines.append("- Example: KP+BT+EM combo_spread = (spread_kenpom + spread_barttorvik + spread_evanmiya) / 3")
    lines.append("- Round to nearest 0.5 for lookup")
    lines.append("")
    lines.append("### Step 2: Look Up Probability")
    lines.append("- Use `spreads_lookup_combined.csv` with inputs:")
    lines.append("  - `total_category`: 1 (total ≤137.5), 2 (137.5-145.5), 3 (>145.5)")
    lines.append("  - `market_spread`: Opening spread line (rounded to 0.5)")
    lines.append("  - `model_spread`: Combo spread from Step 1")
    lines.append("- Returns `cover_prob`")
    lines.append("")
    lines.append("### Step 3: Calculate Edge (UNREGRESSED)")
    lines.append("- **Edge = cover_prob - 52.38%**")
    lines.append("- 52.38% is break-even at -110 odds")
    lines.append("- NO regression toward 50% is applied")
    lines.append("")
    lines.append("### Step 4: Bet Direction")
    lines.append("- If edge > 0: Bet COVER (model says team covers the spread)")
    lines.append("- If edge < 0: Bet AGAINST (model says team does NOT cover)")
    lines.append("- Filter: Only bet when |edge| >= threshold")
    lines.append("")
    lines.append("### Step 5: Calculate ROI")
    lines.append("- Standard -110 juice: Win pays 100/110, loss costs 1")
    lines.append("- ROI = ((wins × 0.909) - losses) / total_bets × 100")
    lines.append("")
    lines.append("### Filters Applied")
    lines.append("- Home team rows only (one bet per game)")
    lines.append("- Games must have: opening_spread, opening_total, spread_covered")
    lines.append("- All models in the combination must have data for that game")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary table
    lines.append("## Summary: Best Performers by Threshold")
    lines.append("")

    for threshold in thresholds:
        lines.append(f"### Edge >= {threshold}%")
        lines.append("")
        lines.append("| Best Combo | Games | W-L | Accuracy | ROI |")
        lines.append("|------------|-------|-----|----------|-----|")

        best = None
        best_roi = -999
        for combo in combos:
            combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
            r = results[threshold][combo_name]
            if r[0] >= 30 and r[3] > best_roi:  # min 30 games
                best_roi = r[3]
                best = (combo_name, r)

        if best:
            combo_name, r = best
            roi_str = f"+{r[3]:.1f}%" if r[3] >= 0 else f"{r[3]:.1f}%"
            acc = r[1] / r[0] * 100 if r[0] > 0 else 0
            lines.append(f"| {combo_name} | {r[0]} | {r[1]}-{r[2]} | {acc:.1f}% | {roi_str} |")
        else:
            lines.append(f"| N/A | - | - | - | - |")

        lines.append("")

    # Detailed results
    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| Combination | Threshold | Games | W-L | Accuracy | ROI |")
    lines.append("|-------------|-----------|-------|-----|----------|-----|")

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
        for threshold in thresholds:
            r = results[threshold][combo_name]
            if r[0] == 0:
                continue
            roi_str = f"+{r[3]:.1f}%" if r[3] >= 0 else f"{r[3]:.1f}%"
            acc = r[1] / r[0] * 100
            lines.append(f"| {combo_name} | {threshold}% | {r[0]} | {r[1]}-{r[2]} | {acc:.1f}% | {roi_str} |")

    lines.append("")

    # Write report
    output_path = base_path / 'analysis' / 'reports' / 'spreads_unregressed_analysis.md'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"\nWrote {output_path}")

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY: Best at 2% edge (min 30 games)")
    print("=" * 70)
    best = None
    best_roi = -999
    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
        r = results[2][combo_name]
        if r[0] >= 30 and r[3] > best_roi:
            best_roi = r[3]
            best = (combo_name, r)
    if best:
        combo_name, r = best
        print(f"SPREAD: {combo_name} - {r[0]} games, {r[1]}-{r[2]}, {r[3]:+.1f}% ROI")


if __name__ == '__main__':
    main()
