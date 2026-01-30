# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///

"""
Edge-Based Model Combination Analysis - SIMPLE VERSION (No Regression)

Analyzes model combination accuracy at different edge thresholds (0%, 1%, 2%, 3%, 4%)
for spreads, moneylines, and totals.

This version uses SIMPLE edge calculation (no lookup table regression):
- Spreads: edge = (market_spread - combo_spread) / some scaling, bet if model says cover
- Totals: edge = (combo_total - market_total) / some scaling for over
- Moneylines: edge = combo_prob - market_prob (same as regressed version)

Comparison baseline: 50% cover probability assumed.
"""

import pandas as pd
import numpy as np
from itertools import combinations
from pathlib import Path

# Constants
IMPLIED_PROB_110 = 110 / 210  # ~0.5238 for -110 lines

# Model name abbreviations
MODEL_ABBREV = {
    'kenpom': 'KP',
    'barttorvik': 'BT',
    'evanmiya': 'EM',
    'hasla': 'HA'
}


def load_data():
    """Load graded results."""
    base_path = Path(__file__).parent.parent.parent

    graded = pd.read_csv(base_path / "graded_results.csv")

    # Filter to one row per game (home team only) to avoid double-counting
    graded = graded[graded['team'] == graded['home_team']].copy()

    return graded


def implied_prob_from_moneyline(ml):
    """Convert American moneyline to implied probability."""
    if pd.isna(ml):
        return None
    if ml > 0:
        return 100 / (ml + 100)
    else:
        return abs(ml) / (abs(ml) + 100)


def calculate_roi(wins, losses):
    """Calculate ROI at standard -110 juice."""
    total = wins + losses
    if total == 0:
        return 0.0
    return ((wins * (100/110)) - losses) / total * 100


def get_all_combinations(models):
    """Generate all non-empty combinations of models."""
    combos = []
    for r in range(1, len(models) + 1):
        for combo in combinations(models, r):
            combos.append(list(combo))
    return combos


def analyze_spreads_simple(graded):
    """
    Analyze spread betting - SIMPLE VERSION.

    Edge = how much better model spread is vs market spread.
    If combo_spread < market_spread, model thinks team covers.
    Edge (in points) = market_spread - combo_spread
    Convert to percentage: edge_pct = edge_points / 10 (rough scaling)
    """
    spread_models = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
    spread_cols = {m: f'spread_{m}' for m in spread_models}

    combos = get_all_combinations(spread_models)
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04]

    results = []

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

        df = graded.copy()
        df = df[df['opening_spread'].notna() & df['spread_covered'].notna()]

        for model in combo:
            col = spread_cols[model]
            df = df[df[col].notna()]

        if len(df) == 0:
            continue

        # Calculate combo spread (average of selected models)
        df['combo_spread'] = df[[spread_cols[m] for m in combo]].mean(axis=1)

        # Simple edge: how many points better is our model?
        # If market_spread = -5 and combo_spread = -7, model thinks team wins by 7
        # That's 2 points of edge for the favorite covering
        # Edge in points = market_spread - combo_spread (for covering)
        df['edge_points'] = df['opening_spread'] - df['combo_spread']

        # Convert to rough percentage (1 point ≈ 1% edge, rough estimate)
        df['edge'] = df['edge_points'] / 100  # So 2 points = 0.02 = 2%

        for threshold in thresholds:
            # Filter by edge threshold (absolute value)
            filtered = df[df['edge'].abs() >= threshold].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'threshold': f'{threshold*100:.0f}%',
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0
                })
                continue

            # Positive edge = bet on covering, negative edge = bet against
            filtered['bet_won'] = filtered.apply(
                lambda row: row['spread_covered'] if row['edge'] > 0 else (1 - row['spread_covered']),
                axis=1
            )

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            accuracy = wins / len(filtered) * 100 if len(filtered) > 0 else 0
            roi = calculate_roi(wins, losses)

            results.append({
                'combination': combo_name,
                'threshold': f'{threshold*100:.0f}%',
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi
            })

    return pd.DataFrame(results)


def analyze_moneylines_simple(graded):
    """
    Analyze moneyline betting - same as regressed version.
    Edge = combo_prob - market_implied_prob
    """
    ml_models = ['kenpom', 'barttorvik', 'evanmiya']
    prob_cols = {m: f'win_prob_{m}' for m in ml_models}

    combos = get_all_combinations(ml_models)
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04]

    results = []

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

        df = graded.copy()
        df = df[df['opening_moneyline'].notna() & df['moneyline_won'].notna()]

        for model in combo:
            col = prob_cols[model]
            df = df[df[col].notna()]

        if len(df) == 0:
            continue

        df['combo_prob'] = df[[prob_cols[m] for m in combo]].mean(axis=1)
        df['market_prob'] = df['opening_moneyline'].apply(implied_prob_from_moneyline)
        df['edge'] = df['combo_prob'] - df['market_prob']

        df = df[df['edge'].notna()]

        for threshold in thresholds:
            filtered = df[df['edge'].abs() >= threshold].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'threshold': f'{threshold*100:.0f}%',
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0
                })
                continue

            filtered['bet_won'] = filtered.apply(
                lambda row: row['moneyline_won'] if row['edge'] > 0 else (1 - row['moneyline_won']),
                axis=1
            )

            def calc_ml_roi(row):
                if row['bet_won'] == 1:
                    ml = row['opening_moneyline'] if row['edge'] > 0 else -row['opening_moneyline']
                    if ml > 0:
                        return ml / 100
                    else:
                        return 100 / abs(ml)
                else:
                    return -1

            filtered['bet_return'] = filtered.apply(calc_ml_roi, axis=1)

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            accuracy = wins / len(filtered) * 100 if len(filtered) > 0 else 0
            roi = filtered['bet_return'].sum() / len(filtered) * 100 if len(filtered) > 0 else 0

            results.append({
                'combination': combo_name,
                'threshold': f'{threshold*100:.0f}%',
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi
            })

    return pd.DataFrame(results)


def analyze_totals_simple(graded, bet_type='over'):
    """
    Analyze over/under betting - SIMPLE VERSION.

    Edge = how much higher/lower model total is vs market.
    For over: edge = (combo_total - market_total) / 100
    For under: edge = (market_total - combo_total) / 100
    """
    total_models = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
    total_cols = {m: f'projected_total_{m}' for m in total_models}

    combos = get_all_combinations(total_models)
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04]

    results = []
    outcome_col = 'over_hit' if bet_type == 'over' else 'under_hit'

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

        df = graded.copy()
        df = df[df['opening_total'].notna() & df[outcome_col].notna()]

        for model in combo:
            col = total_cols[model]
            df = df[df[col].notna()]

        if len(df) == 0:
            continue

        df['combo_total'] = df[[total_cols[m] for m in combo]].mean(axis=1)

        # Simple edge: difference between model and market
        if bet_type == 'over':
            # If model total > market total, we have over edge
            df['edge_points'] = df['combo_total'] - df['opening_total']
        else:
            # If model total < market total, we have under edge
            df['edge_points'] = df['opening_total'] - df['combo_total']

        df['edge'] = df['edge_points'] / 100  # 1 point = 1%

        for threshold in thresholds:
            # Only include games where edge is positive (model predicts in the direction we want to bet)
            # For over: positive edge means model predicts higher than market
            # For under: positive edge means model predicts lower than market
            filtered = df[df['edge'] >= threshold].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'threshold': f'{threshold*100:.0f}%',
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0
                })
                continue

            # With only positive edges, we always bet in the direction indicated
            filtered['bet_won'] = filtered[outcome_col]

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            accuracy = wins / len(filtered) * 100 if len(filtered) > 0 else 0
            roi = calculate_roi(wins, losses)

            results.append({
                'combination': combo_name,
                'threshold': f'{threshold*100:.0f}%',
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi
            })

    return pd.DataFrame(results)


def format_results_table(df, title):
    """Format results as markdown table."""
    lines = [f"\n## {title}\n"]
    lines.append("| Combination | Threshold | Games | W-L | Accuracy | ROI |")
    lines.append("|-------------|-----------|-------|-----|----------|-----|")

    for _, row in df.iterrows():
        wl = f"{row['wins']}-{row['losses']}"
        acc = f"{row['accuracy']:.1f}%"
        roi_val = row['roi']
        roi = f"+{roi_val:.1f}%" if roi_val >= 0 else f"{roi_val:.1f}%"
        lines.append(f"| {row['combination']} | {row['threshold']} | {row['games']} | {wl} | {acc} | {roi} |")

    return '\n'.join(lines)


def create_summary_table(spread_df, ml_df, over_df, under_df):
    """Create summary showing best performers at each threshold."""
    lines = ["\n## Summary: Best Combinations by Threshold\n"]

    thresholds = ['0%', '1%', '2%', '3%', '4%']

    for threshold in thresholds:
        lines.append(f"\n### Edge >= {threshold}\n")
        lines.append("| Bet Type | Best Combo | Games | Accuracy | ROI |")
        lines.append("|----------|------------|-------|----------|-----|")

        for name, df in [('Spread', spread_df), ('Moneyline', ml_df), ('Over', over_df), ('Under', under_df)]:
            t_df = df[df['threshold'] == threshold]
            if len(t_df) == 0:
                continue

            t_df = t_df[t_df['games'] >= 20]
            if len(t_df) == 0:
                lines.append(f"| {name} | N/A | - | - | - |")
                continue

            best = t_df.loc[t_df['roi'].idxmax()]
            roi_val = best['roi']
            roi = f"+{roi_val:.1f}%" if roi_val >= 0 else f"{roi_val:.1f}%"
            lines.append(f"| {name} | {best['combination']} | {best['games']} | {best['accuracy']:.1f}% | {roi} |")

    return '\n'.join(lines)


def main():
    print("="*60)
    print("SIMPLE VERSION - No Regression/Lookup Tables")
    print("Edge = raw model difference from market (1 point = 1%)")
    print("="*60)

    print("\nLoading data...")
    graded = load_data()

    print(f"Loaded {len(graded)} unique games from graded_results.csv")

    print("\nAnalyzing spreads (simple)...")
    spread_results = analyze_spreads_simple(graded)

    print("Analyzing moneylines...")
    ml_results = analyze_moneylines_simple(graded)

    print("Analyzing overs (simple)...")
    over_results = analyze_totals_simple(graded, 'over')

    print("Analyzing unders (simple)...")
    under_results = analyze_totals_simple(graded, 'under')

    # Generate report
    base_path = Path(__file__).parent.parent.parent

    report = ["# Edge-Based Model Combination Analysis - SIMPLE (No Regression)\n"]
    report.append("Analysis WITHOUT lookup table regression. Uses raw model vs market difference.\n")
    report.append("- **Edge Calculation**: Simple difference (1 point spread diff = 1% edge)")
    report.append("- **Baseline**: 50% cover probability assumed")
    report.append("- **ROI**: Standard -110 juice for spreads/totals, actual odds for moneylines")
    report.append("- **Models**: KP=Kenpom, BT=Barttorvik, EM=EvanMiya, HA=Hasla\n")

    report.append(create_summary_table(spread_results, ml_results, over_results, under_results))
    report.append(format_results_table(spread_results, "Spread Results"))
    report.append(format_results_table(ml_results, "Moneyline Results"))
    report.append(format_results_table(over_results, "Over Results"))
    report.append(format_results_table(under_results, "Under Results"))

    output_path = base_path / "analysis" / "reports" / "edge_analysis_simple.md"
    with open(output_path, 'w') as f:
        f.write('\n'.join(report))

    print(f"\nReport written to {output_path}")

    print("\n" + "="*60)
    print("SUMMARY: Best combinations at 4% edge threshold (SIMPLE)")
    print("="*60)

    for name, df in [('Spread', spread_results), ('Moneyline', ml_results), ('Over', over_results), ('Under', under_results)]:
        t_df = df[(df['threshold'] == '4%') & (df['games'] >= 20)]
        if len(t_df) > 0:
            best = t_df.loc[t_df['roi'].idxmax()]
            roi_val = best['roi']
            roi = f"+{roi_val:.1f}%" if roi_val >= 0 else f"{roi_val:.1f}%"
            print(f"{name:10} | {best['combination']:15} | {best['games']:4} games | {best['accuracy']:.1f}% acc | {roi} ROI")


if __name__ == "__main__":
    main()
