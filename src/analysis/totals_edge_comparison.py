# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "numpy"]
# ///

"""
Totals Analysis: Regressed vs Unregressed Comparison

Compares regressed and unregressed edge calculations for over/under bets.
Uses MEAN (average) of model totals.
"""

import pandas as pd
import numpy as np
from itertools import combinations
from pathlib import Path

IMPLIED_PROB_110 = 110 / 210  # ~0.5238

# Model columns
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

    # Load data
    graded = pd.read_csv(base_path / 'graded_results.csv')
    totals_lookup = pd.read_csv(base_path / 'totals_lookup_combined.csv')

    # Filter to home team only (one row per game)
    graded = graded[graded['team'] == graded['home_team']].copy()

    print(f"Total games (home team only): {len(graded)}")

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

    # Run analysis
    combos = get_all_combinations(TOTAL_MODELS)
    thresholds = [0, 1, 2, 3, 4, 5, 6]

    results = {}

    for bet_type in ['over', 'under']:
        outcome_col = 'over_hit' if bet_type == 'over' else 'under_hit'

        for threshold in thresholds:
            key = (bet_type, threshold)
            results[key] = {}

            for combo in combos:
                combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

                df = graded.copy()

                # Filter to valid data
                df = df[df['opening_total'].notna() & df['opening_spread'].notna() & df[outcome_col].notna()]

                # Check all models in combo have data
                cols = [TOTAL_COLS[m] for m in combo]
                df = df.dropna(subset=cols)

                if len(df) == 0:
                    results[key][combo_name] = {'reg': (0, 0, 0, 0), 'unreg': (0, 0, 0, 0)}
                    continue

                # Calculate combo total using MEAN (average)
                df['combo_total'] = df[cols].mean(axis=1)
                df['combo_total_rounded'] = (df['combo_total'] * 2).round() / 2

                # Get spread category
                df['spread_category'] = df['opening_spread'].apply(get_spread_category)

                # Look up probabilities
                def get_prob(row):
                    over_p, under_p = lookup_totals_prob(
                        row['spread_category'],
                        row['opening_total'],
                        row['combo_total_rounded']
                    )
                    return over_p if bet_type == 'over' else under_p

                df['lookup_prob'] = df.apply(get_prob, axis=1)
                df = df[df['lookup_prob'].notna()]

                if len(df) == 0:
                    results[key][combo_name] = {'reg': (0, 0, 0, 0), 'unreg': (0, 0, 0, 0)}
                    continue

                # Regressed: 0.5 × lookup + 0.5 × 0.50
                df['p_regressed'] = 0.5 * df['lookup_prob'] + 0.5 * 0.50
                df['edge_regressed'] = df['p_regressed'] - IMPLIED_PROB_110

                # Unregressed: direct lookup prob
                df['edge_unregressed'] = df['lookup_prob'] - IMPLIED_PROB_110

                # Filter and calculate for regressed
                reg_filtered = df[df['edge_regressed'].abs() >= threshold/100].copy()
                if len(reg_filtered) > 0:
                    reg_filtered['bet_won'] = reg_filtered.apply(
                        lambda row: row[outcome_col] if row['edge_regressed'] > 0 else (1 - row[outcome_col]),
                        axis=1
                    )
                    reg_wins = int(reg_filtered['bet_won'].sum())
                    reg_losses = len(reg_filtered) - reg_wins
                    reg_roi = calculate_roi(reg_wins, reg_losses)
                    reg_result = (len(reg_filtered), reg_wins, reg_losses, reg_roi)
                else:
                    reg_result = (0, 0, 0, 0)

                # Filter and calculate for unregressed
                unreg_filtered = df[df['edge_unregressed'].abs() >= threshold/100].copy()
                if len(unreg_filtered) > 0:
                    unreg_filtered['bet_won'] = unreg_filtered.apply(
                        lambda row: row[outcome_col] if row['edge_unregressed'] > 0 else (1 - row[outcome_col]),
                        axis=1
                    )
                    unreg_wins = int(unreg_filtered['bet_won'].sum())
                    unreg_losses = len(unreg_filtered) - unreg_wins
                    unreg_roi = calculate_roi(unreg_wins, unreg_losses)
                    unreg_result = (len(unreg_filtered), unreg_wins, unreg_losses, unreg_roi)
                else:
                    unreg_result = (0, 0, 0, 0)

                results[key][combo_name] = {'reg': reg_result, 'unreg': unreg_result}

    # Generate markdown
    lines = []
    lines.append("# Totals Analysis: Regressed vs Unregressed Comparison")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("- **Model combination**: Mean (average) of selected model totals")
    lines.append("- **Regressed**: p_final = 0.5 × lookup_prob + 0.5 × 0.50, edge = p_final - 52.38%")
    lines.append("- **Unregressed**: edge = lookup_prob - 52.38%")
    lines.append("- **Bet direction**: Both (positive edge = bet over/under, negative = bet opposite)")
    lines.append("- **ROI**: Standard -110 juice")
    lines.append("- **Filter**: Home team only (one bet per game)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Output for over and under
    for bet_type in ['over', 'under']:
        lines.append(f"# {bet_type.upper()} Bets")
        lines.append("")

        for threshold in thresholds:
            key = (bet_type, threshold)
            lines.append(f"## Edge >= {threshold}%")
            lines.append("")
            lines.append("| Combo | Regressed Games | Regressed ROI | Unreg Games | Unreg ROI |")
            lines.append("|-------|-----------------|---------------|-------------|-----------|")

            for combo in combos:
                combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
                reg = results[key][combo_name]['reg']
                unreg = results[key][combo_name]['unreg']

                reg_str = f"{reg[0]} ({reg[1]}-{reg[2]})"
                unreg_str = f"{unreg[0]} ({unreg[1]}-{unreg[2]})"
                reg_roi = f"+{reg[3]:.1f}%" if reg[3] >= 0 else f"{reg[3]:.1f}%"
                unreg_roi = f"+{unreg[3]:.1f}%" if unreg[3] >= 0 else f"{unreg[3]:.1f}%"

                lines.append(f"| {combo_name} | {reg_str} | {reg_roi} | {unreg_str} | {unreg_roi} |")

            lines.append("")

    # Write to file
    output_path = base_path / 'analysis' / 'reports' / 'totals_regressed_vs_unregressed.md'
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))

    print(f"Wrote {output_path}")
    print("")

    # Print summary
    print("=" * 80)
    print("SUMMARY: Best performers at 2% edge (min 50 games)")
    print("=" * 80)
    for bet_type in ['over', 'under']:
        key = (bet_type, 2)
        best_reg = None
        best_unreg = None
        for combo in combos:
            combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
            reg = results[key][combo_name]['reg']
            unreg = results[key][combo_name]['unreg']

            if reg[0] >= 50 and (best_reg is None or reg[3] > best_reg[1]):
                best_reg = (combo_name, reg[3], reg[0])
            if unreg[0] >= 50 and (best_unreg is None or unreg[3] > best_unreg[1]):
                best_unreg = (combo_name, unreg[3], unreg[0])

        print(f"\n{bet_type.upper()}:")
        if best_reg:
            print(f"  Regressed best: {best_reg[0]} - {best_reg[2]} games, {best_reg[1]:+.1f}% ROI")
        if best_unreg:
            print(f"  Unregressed best: {best_unreg[0]} - {best_unreg[2]} games, {best_unreg[1]:+.1f}% ROI")


if __name__ == '__main__':
    main()
