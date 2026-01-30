# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///
"""
Analyze which combination of models produces the best spread predictions.

Tests all 15 non-empty combinations of: KenPom, Barttorvik, EvanMiya, Hasla
Includes MARKET (opening line) as a benchmark.
"""

import pandas as pd
import numpy as np
from itertools import combinations as iter_combinations
from pathlib import Path

# Model columns
MODELS = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']
SPREAD_COLS = {m: f'spread_{m}' for m in MODELS}
MODEL_NAMES = {'kenpom': 'KP', 'barttorvik': 'BT', 'evanmiya': 'EM', 'hasla': 'HA'}


def get_all_combinations():
    """Generate all non-empty subsets of models."""
    all_combos = []
    for r in range(1, len(MODELS) + 1):
        for combo in iter_combinations(MODELS, r):
            all_combos.append(combo)
    return all_combos


def analyze_combination(df, models, is_market=False):
    """
    Analyze a specific combination of models.

    Returns dict with accuracy, RMSE, MAE, and game count.
    """
    if is_market:
        # Use opening spread as the prediction
        mask = df['opening_spread'].notna()
        subset = df[mask].copy()
        if len(subset) == 0:
            return None
        subset['combo_spread'] = subset['opening_spread']
        name = 'MARKET'
    else:
        # Get spread columns for this combination
        spread_cols = [SPREAD_COLS[m] for m in models]

        # Filter to games where all models in combo have data AND opening_spread exists
        mask = df[spread_cols].notna().all(axis=1) & df['opening_spread'].notna()
        subset = df[mask].copy()

        if len(subset) == 0:
            return None

        # Calculate combined spread (average of included models)
        subset['combo_spread'] = subset[spread_cols].mean(axis=1)
        name = '+'.join([MODEL_NAMES[m] for m in models])

    # Grade accuracy against opening spread (not closing)
    # predicted_cover: model thinks team covers if combo_spread < opening_spread
    subset['predicted_cover'] = subset['combo_spread'] < subset['opening_spread']

    # actual_cover: team covered if actual_margin + opening_spread > 0
    subset['actual_cover'] = (subset['actual_margin'] + subset['opening_spread']) > 0

    # Handle pushes (exact spread hit) - exclude them
    pushes = (subset['actual_margin'] + subset['opening_spread']) == 0
    graded = subset[~pushes]

    if len(graded) == 0:
        return None

    # Calculate metrics
    correct = (graded['predicted_cover'] == graded['actual_cover']).sum()
    accuracy = correct / len(graded) * 100

    # RMSE and MAE of spread prediction vs actual margin
    errors = graded['combo_spread'] - graded['actual_margin']
    rmse = np.sqrt((errors ** 2).mean())
    mae = errors.abs().mean()

    return {
        'models': models if not is_market else ('market',),
        'name': name,
        'games': len(graded),
        'accuracy': accuracy,
        'rmse': rmse,
        'mae': mae,
        'is_market': is_market
    }


def main():
    # Load data
    df = pd.read_csv('graded_results.csv')

    # Calculate actual margin based on whether this row is for home or away team
    def get_actual_margin(row):
        team = row['team']
        home_team = row['home_team']
        home_margin = row['home_score'] - row['away_score']
        if team == home_team:
            return home_margin
        else:
            return -home_margin

    df['actual_margin'] = df.apply(get_actual_margin, axis=1)

    # Filter to one row per game (home team rows only) to avoid double counting
    # Also filter to games with opening_spread
    df_home = df[(df['team'] == df['home_team']) & df['opening_spread'].notna()]

    print(f"Total games with opening spread: {len(df_home)}")
    print()

    # Get all combinations
    all_combos = get_all_combinations()

    # Analyze each combination
    results = []

    # First, add market benchmark
    market_result = analyze_combination(df_home, None, is_market=True)
    if market_result:
        results.append(market_result)

    # Then analyze model combinations
    for combo in all_combos:
        result = analyze_combination(df_home, combo)
        if result:
            results.append(result)

    # Sort by RMSE (ascending - lower is better)
    results.sort(key=lambda x: x['rmse'])

    # Print results
    print("=" * 80)
    print("SPREAD COMBINATION ANALYSIS RESULTS (with Market Benchmark)")
    print("Ranked by RMSE (lower = better prediction of actual margin)")
    print("=" * 80)
    print()
    print(f"{'Rank':<5} {'Combination':<20} {'Games':<8} {'RMSE':<10} {'MAE':<10} {'Accuracy':<10}")
    print("-" * 80)

    for i, row in enumerate(results, 1):
        marker = " <-- MARKET" if row['is_market'] else ""
        print(f"{i:<5} {row['name']:<20} {row['games']:<8} {row['rmse']:<10.2f} {row['mae']:<10.2f} {row['accuracy']:.2f}%{marker}")

    # Find best model (excluding market)
    model_results = [r for r in results if not r['is_market']]
    best_model = model_results[0] if model_results else None

    print()
    print("=" * 80)
    if market_result:
        print(f"MARKET BENCHMARK (Opening Line):")
        print(f"  RMSE: {market_result['rmse']:.2f}")
        print(f"  MAE: {market_result['mae']:.2f}")
        print(f"  Games: {market_result['games']}")
    if best_model:
        print()
        print(f"BEST MODEL COMBINATION: {best_model['name']}")
        print(f"  RMSE: {best_model['rmse']:.2f}")
        print(f"  MAE: {best_model['mae']:.2f}")
        print(f"  Games: {best_model['games']}")
        if market_result:
            diff = best_model['rmse'] - market_result['rmse']
            if diff < 0:
                print(f"  --> BEATS market by {abs(diff):.2f} RMSE points")
            else:
                print(f"  --> WORSE than market by {diff:.2f} RMSE points")
    print("=" * 80)

    # Write markdown output
    reports_dir = Path(__file__).parent.parent.parent / "analysis" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(reports_dir / 'spread_combination_analysis.md', 'w') as f:
        f.write("# Spread Model Combination Analysis\n\n")
        f.write("## Results Ranked by RMSE (lower = better)\n\n")
        f.write("| Rank | Combination | Games | RMSE | MAE | Accuracy |\n")
        f.write("|------|-------------|-------|------|-----|----------|\n")

        for i, row in enumerate(results, 1):
            marker = " ⭐" if row['is_market'] else ""
            f.write(f"| {i} | {row['name']}{marker} | {row['games']} | {row['rmse']:.2f} | {row['mae']:.2f} | {row['accuracy']:.2f}% |\n")

        f.write("\n⭐ = Market benchmark (opening line)\n")

        if market_result:
            f.write(f"\n## Market Benchmark\n\n")
            f.write(f"- **RMSE**: {market_result['rmse']:.2f} points\n")
            f.write(f"- **MAE**: {market_result['mae']:.2f} points\n")
            f.write(f"- **Games**: {market_result['games']}\n")

        if best_model:
            f.write(f"\n## Best Model Combination: **{best_model['name']}**\n\n")
            f.write(f"- **RMSE**: {best_model['rmse']:.2f} points\n")
            f.write(f"- **MAE**: {best_model['mae']:.2f} points\n")
            f.write(f"- **Accuracy**: {best_model['accuracy']:.2f}%\n")
            f.write(f"- **Games**: {best_model['games']}\n")
            if market_result:
                diff = best_model['rmse'] - market_result['rmse']
                if diff < 0:
                    f.write(f"\n**Beats market by {abs(diff):.2f} RMSE points**\n")
                else:
                    f.write(f"\n**Worse than market by {diff:.2f} RMSE points**\n")

        f.write("\n## Legend\n\n")
        f.write("- **KP** = KenPom\n")
        f.write("- **BT** = Barttorvik\n")
        f.write("- **EM** = EvanMiya\n")
        f.write("- **HA** = Hasla\n")
        f.write("- **MARKET** = Opening spread line\n")
        f.write("\n## Methodology\n\n")
        f.write("- For each model combination, the spread is calculated as the **average** of included model spreads.\n")
        f.write("- **RMSE** measures how close predictions are to actual game margins (lower = better).\n")
        f.write("- **Accuracy** measures % of games where model correctly predicted which side covers the opening spread.\n")
        f.write("- Only games with opening spread data are included.\n")

    print(f"\nResults written to {reports_dir / 'spread_combination_analysis.md'}")


if __name__ == '__main__':
    main()
