# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///

"""
Model Combination Analysis: Spread & Total Edges

Analyzes model combination accuracy at different edge thresholds (0%, 1%, 2%, 3%, 4%)
for spreads, moneylines, and totals.

Methodology:
- Spreads/Totals: Model prediction → lookup probability → regress toward 50% → edge
- Moneylines: model_prob - market_implied_prob = edge

Probability regression: p_final = 0.4 × p_model + 0.6 × 0.50
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
    """Load graded results and lookup tables."""
    base_path = Path(__file__).parent.parent.parent

    graded = pd.read_csv(base_path / "graded_results.csv")

    # Filter to one row per game (home team only) to avoid double-counting
    # Each game has two rows in graded_results: one for each team
    graded = graded[graded['team'] == graded['home_team']].copy()

    spreads_lookup = pd.read_csv(base_path / "spreads_lookup_combined.csv")
    totals_lookup = pd.read_csv(base_path / "totals_lookup_combined.csv")

    return graded, spreads_lookup, totals_lookup


def get_total_category(market_total):
    """Determine total category for spread lookup."""
    if pd.isna(market_total):
        return None
    if market_total <= 137.5:
        return 1
    elif market_total <= 145.5:
        return 2
    else:
        return 3


def get_spread_category(market_spread):
    """Determine spread category for totals lookup."""
    if pd.isna(market_spread):
        return None
    abs_spread = abs(market_spread)
    if abs_spread <= 2.5:
        return 1
    elif abs_spread <= 10:
        return 2
    else:
        return 3


def lookup_spread_cover_prob(spreads_lookup, total_category, market_spread, model_spread):
    """Look up cover probability from spreads lookup table."""
    if total_category is None or pd.isna(market_spread) or pd.isna(model_spread):
        return None

    # Round model_spread to nearest 0.5
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


def lookup_totals_prob(totals_lookup, spread_category, market_total, model_total):
    """Look up over/under probabilities from totals lookup table."""
    if spread_category is None or pd.isna(market_total) or pd.isna(model_total):
        return None, None

    # Round to nearest 0.5
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
    # Win pays 0.909 (100/110), loss costs 1
    return ((wins * (100/110)) - losses) / total * 100


def get_all_combinations(models):
    """Generate all non-empty combinations of models."""
    combos = []
    for r in range(1, len(models) + 1):
        for combo in combinations(models, r):
            combos.append(list(combo))
    return combos


def analyze_spreads(graded, spreads_lookup):
    """Analyze spread betting by model combination and edge threshold."""
    spread_models = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
    spread_cols = {m: f'spread_{m}' for m in spread_models}

    combos = get_all_combinations(spread_models)
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04]

    results = []

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

        # Filter to games with required data
        df = graded.copy()

        # Need opening_spread, opening_total, spread_covered
        df = df[df['opening_spread'].notna() & df['opening_total'].notna() & df['spread_covered'].notna()]

        # Check if all models in combo have data
        for model in combo:
            col = spread_cols[model]
            df = df[df[col].notna()]

        if len(df) == 0:
            continue

        # Calculate combo spread (average of selected models) - RAW, no regression
        df['combo_spread'] = df[[spread_cols[m] for m in combo]].mean(axis=1)

        # NEW: Round RAW combo_spread for lookup (no 0.6/0.4 regression before lookup)
        df['combo_spread_rounded'] = (df['combo_spread'] * 2).round() / 2

        # Get total category
        df['total_category'] = df['opening_total'].apply(get_total_category)

        # Look up cover probability using RAW model spread
        df['cover_prob'] = df.apply(
            lambda row: lookup_spread_cover_prob(
                spreads_lookup,
                row['total_category'],
                row['opening_spread'],
                row['combo_spread_rounded']  # RAW, not regressed
            ),
            axis=1
        )

        # NEW: Regress probability toward 50% (40% model, 60% toward baseline)
        df['p_final'] = 0.4 * df['cover_prob'] + 0.6 * 0.50

        # Calculate edge from regressed probability
        df['edge'] = df['p_final'] - IMPLIED_PROB_110

        # Filter to rows with valid edge
        df = df[df['edge'].notna()]

        for threshold in thresholds:
            # Filter by edge threshold (absolute value)
            filtered = df[df['edge'].abs() >= threshold].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'models': combo,
                    'threshold': f'{threshold*100:.0f}%',
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0
                })
                continue

            # Determine bet direction based on edge sign
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
                'models': combo,
                'threshold': f'{threshold*100:.0f}%',
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi
            })

    return pd.DataFrame(results)


def analyze_moneylines(graded):
    """Analyze moneyline betting by model combination and edge threshold."""
    # Hasla doesn't have win probability
    ml_models = ['kenpom', 'barttorvik', 'evanmiya']
    prob_cols = {m: f'win_prob_{m}' for m in ml_models}

    combos = get_all_combinations(ml_models)
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04]

    results = []

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

        df = graded.copy()

        # Need opening_moneyline and moneyline_won
        df = df[df['opening_moneyline'].notna() & df['moneyline_won'].notna()]

        # Check if all models in combo have data
        for model in combo:
            col = prob_cols[model]
            df = df[df[col].notna()]

        if len(df) == 0:
            continue

        # Calculate combo win probability
        df['combo_prob'] = df[[prob_cols[m] for m in combo]].mean(axis=1)

        # Calculate market implied probability
        df['market_prob'] = df['opening_moneyline'].apply(implied_prob_from_moneyline)

        # Calculate edge
        df['edge'] = df['combo_prob'] - df['market_prob']

        # Filter to rows with valid edge
        df = df[df['edge'].notna()]

        for threshold in thresholds:
            # Filter by edge threshold
            filtered = df[df['edge'].abs() >= threshold].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'models': combo,
                    'threshold': f'{threshold*100:.0f}%',
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0
                })
                continue

            # Positive edge = bet on team, negative edge = bet against
            filtered['bet_won'] = filtered.apply(
                lambda row: row['moneyline_won'] if row['edge'] > 0 else (1 - row['moneyline_won']),
                axis=1
            )

            # For moneyline, ROI depends on actual odds paid
            # Simplified: use actual moneyline odds for wins
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
                'models': combo,
                'threshold': f'{threshold*100:.0f}%',
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi
            })

    return pd.DataFrame(results)


def analyze_totals(graded, totals_lookup, bet_type='over'):
    """Analyze over/under betting by model combination and edge threshold."""
    total_models = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
    total_cols = {m: f'projected_total_{m}' for m in total_models}

    combos = get_all_combinations(total_models)
    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04]

    results = []
    outcome_col = 'over_hit' if bet_type == 'over' else 'under_hit'
    prob_col = 'over_prob' if bet_type == 'over' else 'under_prob'

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

        df = graded.copy()

        # Need opening_total, opening_spread, and outcome
        df = df[df['opening_total'].notna() & df['opening_spread'].notna() & df[outcome_col].notna()]

        # Check if all models in combo have data
        for model in combo:
            col = total_cols[model]
            df = df[df[col].notna()]

        if len(df) == 0:
            continue

        # Calculate combo total (average of selected models) - RAW, no regression
        df['combo_total'] = df[[total_cols[m] for m in combo]].mean(axis=1)

        # NEW: Round RAW combo_total for lookup (no 0.6/0.4 regression before lookup)
        df['combo_total_rounded'] = (df['combo_total'] * 2).round() / 2

        # Get spread category
        df['spread_category'] = df['opening_spread'].apply(get_spread_category)

        # Look up probabilities using RAW model total
        def get_prob_raw(row):
            over_p, under_p = lookup_totals_prob(
                totals_lookup,
                row['spread_category'],
                row['opening_total'],
                row['combo_total_rounded']  # RAW, not regressed
            )
            return over_p if bet_type == 'over' else under_p

        df['lookup_prob'] = df.apply(get_prob_raw, axis=1)

        # NEW: Regress probability toward 50% (40% model, 60% toward baseline)
        df['p_final'] = 0.4 * df['lookup_prob'] + 0.6 * 0.50

        # Calculate edge from regressed probability
        df['edge'] = df['p_final'] - IMPLIED_PROB_110

        # Filter to rows with valid edge
        df = df[df['edge'].notna()]

        for threshold in thresholds:
            # Filter by edge threshold
            filtered = df[df['edge'].abs() >= threshold].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'models': combo,
                    'threshold': f'{threshold*100:.0f}%',
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0
                })
                continue

            # Positive edge = bet on over/under, negative edge = bet against
            filtered['bet_won'] = filtered.apply(
                lambda row: row[outcome_col] if row['edge'] > 0 else (1 - row[outcome_col]),
                axis=1
            )

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            accuracy = wins / len(filtered) * 100 if len(filtered) > 0 else 0
            roi = calculate_roi(wins, losses)

            results.append({
                'combination': combo_name,
                'models': combo,
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

            # Filter to combos with at least 20 games
            t_df = t_df[t_df['games'] >= 20]
            if len(t_df) == 0:
                lines.append(f"| {name} | N/A | - | - | - |")
                continue

            # Best by ROI
            best = t_df.loc[t_df['roi'].idxmax()]
            roi_val = best['roi']
            roi = f"+{roi_val:.1f}%" if roi_val >= 0 else f"{roi_val:.1f}%"
            lines.append(f"| {name} | {best['combination']} | {best['games']} | {best['accuracy']:.1f}% | {roi} |")

    return '\n'.join(lines)


def main():
    print("Loading data...")
    graded, spreads_lookup, totals_lookup = load_data()

    print(f"Loaded {len(graded)} rows from graded_results.csv")
    print(f"Spreads lookup: {len(spreads_lookup)} rows")
    print(f"Totals lookup: {len(totals_lookup)} rows")

    print("\nAnalyzing spreads...")
    spread_results = analyze_spreads(graded, spreads_lookup)

    print("Analyzing moneylines...")
    ml_results = analyze_moneylines(graded)

    print("Analyzing overs...")
    over_results = analyze_totals(graded, totals_lookup, 'over')

    print("Analyzing unders...")
    under_results = analyze_totals(graded, totals_lookup, 'under')

    # Generate report
    base_path = Path(__file__).parent.parent.parent

    report = ["# Model Combination Analysis: Spread & Total Edges\n"]
    report.append("Analysis of model combination accuracy at different edge thresholds.\n")
    report.append("## Methodology\n")
    report.append("For spreads and totals, edges are calculated using probability-space regression:\n")
    report.append("1. Compute raw model prediction (average of selected models)")
    report.append("2. Look up implied probability from historical data")
    report.append("3. Regress toward market: `p_final = 0.4 × p_model + 0.6 × 0.50`")
    report.append("4. Edge = p_final − 52.38% (break-even at -110)")
    report.append("")
    report.append("Moneylines use direct probability comparison (model vs market implied).")
    report.append("")
    report.append("**Model abbreviations**: KP=Kenpom, BT=Barttorvik, EM=EvanMiya, HA=Hasla\n")

    # Summary
    report.append(create_summary_table(spread_results, ml_results, over_results, under_results))

    # Detailed results
    report.append(format_results_table(spread_results, "Spread Results"))
    report.append(format_results_table(ml_results, "Moneyline Results"))
    report.append(format_results_table(over_results, "Over Results"))
    report.append(format_results_table(under_results, "Under Results"))

    # Write report
    output_path = base_path / "temp_edge_analysis.md"
    with open(output_path, 'w') as f:
        f.write('\n'.join(report))

    print(f"\nReport written to {output_path}")

    # Also print summary to console
    print("\n" + "="*60)
    print("SUMMARY: Best combinations at 4% edge threshold")
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
