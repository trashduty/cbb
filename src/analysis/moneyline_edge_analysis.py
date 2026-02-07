# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///

"""
Moneyline Edge Analysis

Reproducible script that analyzes moneyline betting performance with proper methodology:
- Median win probability across models (matches pipeline)
- Regression toward market: final_prob = 0.5 × median(models) + 0.5 × market_implied
- Edge = final_prob - market_implied
- Positive edge only (we don't bet the other side)
- ROI uses actual posted opening moneyline odds
"""

import pandas as pd
import numpy as np
from itertools import combinations
from pathlib import Path

# Model name abbreviations
MODEL_ABBREV = {
    'kenpom': 'KP',
    'barttorvik': 'BT',
    'evanmiya': 'EM',
}

# Win probability ranges
WIN_PROB_RANGES = [
    ('Heavy Dogs (0-25%)', 0.0, 0.25),
    ('Moderate Dogs (25-40%)', 0.25, 0.40),
    ('Slight Dogs (40-50%)', 0.40, 0.50),
    ('Slight Favs (50-60%)', 0.50, 0.60),
    ('Moderate Favs (60-75%)', 0.60, 0.75),
    ('Heavy Favs (75-100%)', 0.75, 1.0),
]


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


def calc_ml_return(row):
    """Calculate return for a moneyline bet."""
    if row['bet_won'] == 1:
        ml = row['opening_moneyline']
        if ml > 0:
            return ml / 100
        else:
            return 100 / abs(ml)
    else:
        return -1


def get_all_combinations(models):
    """Generate all non-empty combinations of models."""
    combos = []
    for r in range(1, len(models) + 1):
        for combo in combinations(models, r):
            combos.append(list(combo))
    return combos


def analyze_production_benchmark(graded, thresholds):
    """Analyze using pipeline's pre-computed edge (opening_moneyline_edge).

    This matches the pipeline's exact computation including devigged probability.
    """
    results = []

    df = graded.copy()
    df = df[
        df['opening_moneyline'].notna() &
        df['moneyline_won'].notna() &
        df['opening_moneyline_edge'].notna() &
        df['moneyline_win_probability'].notna()
    ]

    for threshold in thresholds:
        # Positive edge only
        filtered = df[df['opening_moneyline_edge'] >= threshold].copy()

        if len(filtered) == 0:
            results.append({
                'threshold': f'{threshold*100:.0f}%',
                'games': 0,
                'wins': 0,
                'losses': 0,
                'accuracy': 0.0,
                'roi': 0.0,
                'avg_edge': 0.0
            })
            continue

        filtered['bet_won'] = filtered['moneyline_won']
        filtered['bet_return'] = filtered.apply(calc_ml_return, axis=1)

        wins = int(filtered['bet_won'].sum())
        losses = len(filtered) - wins
        accuracy = wins / len(filtered) * 100
        roi = filtered['bet_return'].sum() / len(filtered) * 100
        avg_edge = filtered['opening_moneyline_edge'].mean() * 100

        results.append({
            'threshold': f'{threshold*100:.0f}%',
            'games': len(filtered),
            'wins': wins,
            'losses': losses,
            'accuracy': accuracy,
            'roi': roi,
            'avg_edge': avg_edge
        })

    return pd.DataFrame(results)


def analyze_production_by_win_prob(graded, thresholds):
    """Analyze production benchmark broken down by win probability range."""
    results = []

    df = graded.copy()
    df = df[
        df['opening_moneyline'].notna() &
        df['moneyline_won'].notna() &
        df['opening_moneyline_edge'].notna() &
        df['moneyline_win_probability'].notna()
    ]

    for threshold in thresholds:
        for range_name, low, high in WIN_PROB_RANGES:
            # Positive edge only
            filtered = df[
                (df['opening_moneyline_edge'] >= threshold) &
                (df['moneyline_win_probability'] >= low) &
                (df['moneyline_win_probability'] < high)
            ].copy()

            if len(filtered) == 0:
                results.append({
                    'threshold': f'{threshold*100:.0f}%',
                    'range': range_name,
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0,
                    'avg_edge': 0.0,
                    'avg_win_prob': 0.0
                })
                continue

            filtered['bet_won'] = filtered['moneyline_won']
            filtered['bet_return'] = filtered.apply(calc_ml_return, axis=1)

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            accuracy = wins / len(filtered) * 100
            roi = filtered['bet_return'].sum() / len(filtered) * 100
            avg_edge = filtered['opening_moneyline_edge'].mean() * 100
            avg_win_prob = filtered['moneyline_win_probability'].mean() * 100

            results.append({
                'threshold': f'{threshold*100:.0f}%',
                'range': range_name,
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi,
                'avg_edge': avg_edge,
                'avg_win_prob': avg_win_prob
            })

    return pd.DataFrame(results)


def analyze_combo(graded, combo, thresholds):
    """Analyze a single model combination."""
    ml_models = ['kenpom', 'barttorvik', 'evanmiya']
    prob_cols = {m: f'win_prob_{m}' for m in ml_models}

    results = []
    combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

    df = graded.copy()
    df = df[df['opening_moneyline'].notna() & df['moneyline_won'].notna()]

    # Check if all models in combo have data
    for model in combo:
        col = prob_cols[model]
        df = df[df[col].notna()]

    if len(df) == 0:
        return pd.DataFrame(results)

    # Calculate combo win probability using MEDIAN
    df['combo_prob'] = df[[prob_cols[m] for m in combo]].median(axis=1)

    # Calculate market implied probability
    df['market_prob'] = df['opening_moneyline'].apply(implied_prob_from_moneyline)

    # Regress toward market: 50% model, 50% market
    df['combo_prob_regressed'] = 0.5 * df['combo_prob'] + 0.5 * df['market_prob']

    # Calculate edge from regressed probability
    df['edge'] = df['combo_prob_regressed'] - df['market_prob']

    df = df[df['edge'].notna()]

    for threshold in thresholds:
        # Positive edge only
        filtered = df[df['edge'] >= threshold].copy()

        if len(filtered) == 0:
            results.append({
                'combination': combo_name,
                'threshold': f'{threshold*100:.0f}%',
                'games': 0,
                'wins': 0,
                'losses': 0,
                'accuracy': 0.0,
                'roi': 0.0,
                'avg_edge': 0.0
            })
            continue

        filtered['bet_won'] = filtered['moneyline_won']
        filtered['bet_return'] = filtered.apply(calc_ml_return, axis=1)

        wins = int(filtered['bet_won'].sum())
        losses = len(filtered) - wins
        accuracy = wins / len(filtered) * 100
        roi = filtered['bet_return'].sum() / len(filtered) * 100
        avg_edge = filtered['edge'].mean() * 100

        results.append({
            'combination': combo_name,
            'threshold': f'{threshold*100:.0f}%',
            'games': len(filtered),
            'wins': wins,
            'losses': losses,
            'accuracy': accuracy,
            'roi': roi,
            'avg_edge': avg_edge
        })

    return pd.DataFrame(results)


def analyze_combo_by_win_prob(graded, combo, thresholds):
    """Analyze a single model combination broken down by win probability range."""
    ml_models = ['kenpom', 'barttorvik', 'evanmiya']
    prob_cols = {m: f'win_prob_{m}' for m in ml_models}

    results = []
    combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])

    df = graded.copy()
    df = df[df['opening_moneyline'].notna() & df['moneyline_won'].notna()]

    for model in combo:
        col = prob_cols[model]
        df = df[df[col].notna()]

    if len(df) == 0:
        return pd.DataFrame(results)

    # Calculate combo win probability using MEDIAN
    df['combo_prob'] = df[[prob_cols[m] for m in combo]].median(axis=1)

    # Calculate market implied probability
    df['market_prob'] = df['opening_moneyline'].apply(implied_prob_from_moneyline)

    # Regress toward market: 50% model, 50% market
    df['combo_prob_regressed'] = 0.5 * df['combo_prob'] + 0.5 * df['market_prob']

    # Calculate edge from regressed probability
    df['edge'] = df['combo_prob_regressed'] - df['market_prob']

    df = df[df['edge'].notna()]

    for threshold in thresholds:
        for range_name, low, high in WIN_PROB_RANGES:
            # Use market_prob for win prob range classification
            filtered = df[
                (df['edge'] >= threshold) &
                (df['market_prob'] >= low) &
                (df['market_prob'] < high)
            ].copy()

            if len(filtered) == 0:
                results.append({
                    'combination': combo_name,
                    'threshold': f'{threshold*100:.0f}%',
                    'range': range_name,
                    'games': 0,
                    'wins': 0,
                    'losses': 0,
                    'accuracy': 0.0,
                    'roi': 0.0,
                    'avg_edge': 0.0
                })
                continue

            filtered['bet_won'] = filtered['moneyline_won']
            filtered['bet_return'] = filtered.apply(calc_ml_return, axis=1)

            wins = int(filtered['bet_won'].sum())
            losses = len(filtered) - wins
            accuracy = wins / len(filtered) * 100
            roi = filtered['bet_return'].sum() / len(filtered) * 100
            avg_edge = filtered['edge'].mean() * 100

            results.append({
                'combination': combo_name,
                'threshold': f'{threshold*100:.0f}%',
                'range': range_name,
                'games': len(filtered),
                'wins': wins,
                'losses': losses,
                'accuracy': accuracy,
                'roi': roi,
                'avg_edge': avg_edge
            })

    return pd.DataFrame(results)


def format_roi(val):
    """Format ROI value with sign."""
    if val >= 0:
        return f'+{val:.1f}%'
    return f'{val:.1f}%'


def main():
    print("Loading data...")
    graded = load_data()
    print(f"Loaded {len(graded)} games (home team rows only)")

    thresholds = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]
    ml_models = ['kenpom', 'barttorvik', 'evanmiya']
    combos = get_all_combinations(ml_models)

    # --- Per-Combo Analysis ---
    print("\nAnalyzing model combinations...")
    all_combo_results = []
    all_combo_by_range = []

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
        print(f"  {combo_name}...")
        all_combo_results.append(analyze_combo(graded, combo, thresholds))
        all_combo_by_range.append(analyze_combo_by_win_prob(graded, combo, thresholds))

    combo_results = pd.concat(all_combo_results, ignore_index=True)
    combo_by_range = pd.concat(all_combo_by_range, ignore_index=True)

    # --- Generate Report ---
    print("\nGenerating report...")

    report = []
    report.append("# Moneyline Edge Analysis (REGRESSED)")
    report.append("")
    report.append("## Methodology")
    report.append("")
    report.append("- Edge = (0.5 × median(model_probs) + 0.5 × market_implied) - market_implied (regressed toward market)")
    report.append("- Positive edge only")
    report.append("- ROI uses actual posted opening moneyline odds")
    report.append("")
    report.append("**Note:** Barttorvik only has 55% data coverage, limiting BT combo sample sizes.")
    report.append("")
    report.append("")
    report.append("---")
    report.append("")
    report.append("## All Results")
    report.append("")
    report.append("| Combo | Threshold | Games | W-L | Accuracy | ROI | Avg Edge |")
    report.append("|-------|-----------|-------|-----|----------|-----|----------|")

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
        for threshold in thresholds:
            t_label = f'{threshold*100:.0f}%'
            t_df = combo_results[(combo_results['combination'] == combo_name) & (combo_results['threshold'] == t_label)]
            if len(t_df) == 0:
                continue
            row = t_df.iloc[0]
            if row['games'] == 0:
                continue
            report.append(f"| {combo_name} | {t_label} | {row['games']} | {row['wins']}-{row['losses']} | {row['accuracy']:.1f}% | {format_roi(row['roi'])} | {row['avg_edge']:.1f}% |")

    report.append("")
    report.append("---")
    report.append("")
    report.append("## Best Performers by Threshold")
    report.append("")

    for threshold in thresholds:
        t_label = f'{threshold*100:.0f}%'
        t_df = combo_results[combo_results['threshold'] == t_label]
        t_df = t_df[t_df['games'] >= 10]
        if len(t_df) == 0:
            continue
        best = t_df.loc[t_df['roi'].idxmax()]
        report.append(f"- **{t_label} edge**: {best['combination']} - {best['games']} games, {format_roi(best['roi'])} ROI")

    report.append("")
    report.append("---")
    report.append("")

    # Per-combo breakdown by win prob range
    report.append("## Model Combinations: Performance by Win Probability Range")
    report.append("")
    report.append("*Win probability ranges based on market implied probability (from opening moneyline).*")
    report.append("")

    for combo in combos:
        combo_name = '+'.join([MODEL_ABBREV[m] for m in combo])
        report.append(f"### {combo_name}")
        report.append("")

        for threshold in ['2%', '3%', '4%']:
            t_df = combo_by_range[(combo_by_range['combination'] == combo_name) & (combo_by_range['threshold'] == threshold)]

            if len(t_df) == 0 or t_df['games'].sum() == 0:
                continue

            report.append(f"#### Edge >= {threshold}")
            report.append("")
            report.append("| Range | Games | W-L | Win% | Avg Edge | ROI |")
            report.append("|-------|-------|-----|------|----------|-----|")

            for _, row in t_df.iterrows():
                if row['games'] > 0:
                    report.append(f"| {row['range']} | {row['games']} | {row['wins']}-{row['losses']} | {row['accuracy']:.1f}% | {row['avg_edge']:.1f}% | {format_roi(row['roi'])} |")

            report.append("")

    report.append("---")
    report.append("")
    report.append("## Notes")
    report.append("")
    report.append("- Edge is calculated using raw market implied probability (from moneyline odds)")
    report.append("- Sample sizes decrease significantly at higher edge thresholds - interpret with caution")
    report.append("")

    # Write report
    base_path = Path(__file__).parent.parent.parent
    output_path = base_path / "analysis" / "reports" / "moneyline_regressed_analysis.md"
    with open(output_path, 'w') as f:
        f.write('\n'.join(report))

    print(f"Report written to {output_path}")

    # Console summary
    print("\n" + "="*60)
    print("SUMMARY: Best at 2% edge")
    print("="*60)
    t_df = combo_results[combo_results['threshold'] == '2%']
    t_df = t_df[t_df['games'] >= 10]
    if len(t_df) > 0:
        best = t_df.loc[t_df['roi'].idxmax()]
        print(f"ML: {best['combination']} - {best['games']} games, {best['wins']}-{best['losses']}, {format_roi(best['roi'])} ROI")


if __name__ == "__main__":
    main()
