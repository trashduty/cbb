# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "numpy"]
# ///

"""
Totals Analysis - REGRESSED POINTS (regress forecast toward market before lookup)

regressed_total = 0.5 * combo_total + 0.5 * market_total
Edge = lookup_prob(regressed_total) - 52.38%
"""

import pandas as pd
import numpy as np
from itertools import combinations
from pathlib import Path

IMPLIED_PROB_110 = 110 / 210  # ~0.5238

TOTAL_MODELS = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
TOTAL_COLS = {m: f'projected_total_{m}' for m in TOTAL_MODELS}
MODEL_ABBREV = {'kenpom': 'KP', 'barttorvik': 'BT', 'evanmiya': 'EM', 'hasla': 'HA'}


def get_spread_category(market_spread):
    if pd.isna(market_spread):
        return None
    abs_spread = abs(market_spread)
    if abs_spread <= 2.5:
        return 1
    elif abs_spread <= 10:
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
    totals_lookup = pd.read_csv(base_path / 'totals_lookup_combined.csv')

    # Home team only
    graded = graded[graded['team'] == graded['home_team']].copy()

    print(f"Total games: {len(graded)}")

    def lookup_totals_prob(spread_category, market_total, model_total):
        if spread_category is None or pd.isna(market_total) or pd.isna(model_total):
            return None, None

        model_total_rounded = round(model_total * 2) / 2
        market_total_rounded = round(market_total * 2) / 2

        match = totals_lookup[
            (totals_lookup['spread_category'] == spread_category) &
            (totals_lookup['market_total'] == market_total_rounded) &
            (totals_lookup['model_total'] == model_total_rounded)
        ]

        if len(match) > 0:
            return match.iloc[0]['over_prob'], match.iloc[0]['under_prob']
        return None, None

    combos = get_all_combinations(TOTAL_MODELS)
    thresholds = [0, 1, 2, 3, 4, 5, 6]

    results = {'over': {}, 'under': {}}

    for bet_type in ['over', 'under']:
        outcome_col = 'over_hit' if bet_type == 'over' else 'under_hit'

        for threshold in thresholds:
            results[bet_type][threshold] = {}

            for combo in combos:
                combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

                df = graded.copy()
                df = df[df['opening_total'].notna() & df['opening_spread'].notna() & df[outcome_col].notna()]

                cols = [TOTAL_COLS[m] for m in combo]
                df = df.dropna(subset=cols)

                if len(df) == 0:
                    results[bet_type][threshold][combo_name] = (0, 0, 0, 0)
                    continue

                # Mean of model totals
                df['combo_total'] = df[cols].mean(axis=1)

                # REGRESS THE FORECAST toward market BEFORE lookup
                df['regressed_total'] = 0.5 * df['combo_total'] + 0.5 * df['opening_total']
                df['regressed_total_rounded'] = (df['regressed_total'] * 2).round() / 2

                df['spread_category'] = df['opening_spread'].apply(get_spread_category)

                # Lookup probability using REGRESSED total
                def get_prob(row):
                    over_p, under_p = lookup_totals_prob(
                        row['spread_category'],
                        row['opening_total'],
                        row['regressed_total_rounded']  # Use regressed total for lookup
                    )
                    return over_p if bet_type == 'over' else under_p

                df['lookup_prob'] = df.apply(get_prob, axis=1)
                df = df[df['lookup_prob'].notna()]

                if len(df) == 0:
                    results[bet_type][threshold][combo_name] = (0, 0, 0, 0)
                    continue

                # NO regression on probability - use lookup_prob directly
                df['edge'] = df['lookup_prob'] - IMPLIED_PROB_110

                # Filter by threshold (both directions)
                filtered = df[df['edge'].abs() >= threshold/100].copy()

                if len(filtered) == 0:
                    results[bet_type][threshold][combo_name] = (0, 0, 0, 0)
                    continue

                # Bet direction based on edge sign
                filtered['bet_won'] = filtered.apply(
                    lambda row: row[outcome_col] if row['edge'] > 0 else (1 - row[outcome_col]),
                    axis=1
                )

                wins = int(filtered['bet_won'].sum())
                losses = len(filtered) - wins
                roi = calculate_roi(wins, losses)

                results[bet_type][threshold][combo_name] = (len(filtered), wins, losses, roi)

    # Generate report
    lines = []
    lines.append("# Totals Analysis - REGRESSED POINTS")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("Regress the forecast toward the market before lookup:")
    lines.append("")
    lines.append("1. **regressed_total = 0.5 × combo_total + 0.5 × market_total**")
    lines.append("2. Look up probability using regressed_total")
    lines.append("3. Edge = lookup_prob - 52.38% (no probability regression)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Results
    for bet_type in ['over', 'under']:
        lines.append(f"## {bet_type.upper()} Results")
        lines.append("")
        lines.append("| Combination | Threshold | Games | W-L | Accuracy | ROI |")
        lines.append("|-------------|-----------|-------|-----|----------|-----|")

        for combo in combos:
            combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
            for threshold in thresholds:
                r = results[bet_type][threshold][combo_name]
                if r[0] == 0:
                    continue
                roi_str = f"+{r[3]:.1f}%" if r[3] >= 0 else f"{r[3]:.1f}%"
                acc = r[1] / r[0] * 100
                lines.append(f"| {combo_name} | {threshold}% | {r[0]} | {r[1]}-{r[2]} | {acc:.1f}% | {roi_str} |")

        lines.append("")

    # Write report
    output_path = base_path / 'analysis' / 'reports' / 'totals_regressed_analysis_points.md'
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"\nWrote {output_path}")


if __name__ == '__main__':
    main()
