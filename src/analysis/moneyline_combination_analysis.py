# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///
"""
Analyze which combination of models produces the best moneyline (win probability) predictions.

Tests all 7 non-empty combinations of: KenPom, Barttorvik, EvanMiya (Hasla doesn't provide win prob)
Includes MARKET (opening moneyline implied probability) as a benchmark.
"""

import pandas as pd
import numpy as np
from itertools import combinations as iter_combinations
from pathlib import Path

# Model columns - only 3 models provide win probability
MODELS = ['kenpom', 'barttorvik', 'evanmiya']
WIN_PROB_COLS = {m: f'win_prob_{m}' for m in MODELS}
MODEL_NAMES = {'kenpom': 'KP', 'barttorvik': 'BT', 'evanmiya': 'EM'}


def moneyline_to_implied_prob(ml):
    """Convert American moneyline odds to implied probability."""
    if pd.isna(ml):
        return np.nan
    if ml > 0:
        return 100 / (ml + 100)
    else:
        return abs(ml) / (abs(ml) + 100)


def get_all_combinations():
    """Generate all non-empty subsets of models."""
    all_combos = []
    for r in range(1, len(MODELS) + 1):
        for combo in iter_combinations(MODELS, r):
            all_combos.append(combo)
    return all_combos


def analyze_combination(df, models, is_market=False):
    """
    Analyze a specific combination of models for moneyline.

    Returns dict with accuracy, Brier score, log loss, and game count.
    """
    if is_market:
        # Use opening moneyline implied probability as the prediction
        mask = df['market_prob'].notna()
        subset = df[mask].copy()
        if len(subset) == 0:
            return None
        subset['combo_prob'] = subset['market_prob']
        name = 'MARKET'
    else:
        # Get win prob columns for this combination
        prob_cols = [WIN_PROB_COLS[m] for m in models]

        # Filter to games where all models in combo have data AND opening_moneyline exists
        mask = df[prob_cols].notna().all(axis=1) & df['market_prob'].notna()
        subset = df[mask].copy()

        if len(subset) == 0:
            return None

        # Calculate combined probability (average of included models)
        subset['combo_prob'] = subset[prob_cols].mean(axis=1)
        name = '+'.join([MODEL_NAMES[m] for m in models])

    # Actual outcome: 1 if team won, 0 if lost
    subset['actual_win'] = (subset['actual_margin'] > 0).astype(int)

    # Exclude ties (very rare in basketball but just in case)
    graded = subset[subset['actual_margin'] != 0].copy()

    if len(graded) == 0:
        return None

    # Calculate metrics

    # Accuracy: did the predicted favorite (prob > 0.5) actually win?
    graded['predicted_win'] = (graded['combo_prob'] > 0.5).astype(int)
    correct = (graded['predicted_win'] == graded['actual_win']).sum()
    accuracy = correct / len(graded) * 100

    # Brier Score: mean((predicted_prob - actual_outcome)^2) - lower is better
    brier = ((graded['combo_prob'] - graded['actual_win']) ** 2).mean()

    # Log Loss: -mean(actual*log(pred) + (1-actual)*log(1-pred)) - lower is better
    # Clip probabilities to avoid log(0)
    eps = 1e-10
    probs_clipped = graded['combo_prob'].clip(eps, 1 - eps)
    log_loss = -np.mean(
        graded['actual_win'] * np.log(probs_clipped) +
        (1 - graded['actual_win']) * np.log(1 - probs_clipped)
    )

    return {
        'models': models if not is_market else ('market',),
        'name': name,
        'games': len(graded),
        'accuracy': accuracy,
        'brier': brier,
        'log_loss': log_loss,
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

    # Convert opening moneyline to implied probability
    df['market_prob'] = df['opening_moneyline'].apply(moneyline_to_implied_prob)

    # Filter to one row per game (home team rows only) to avoid double counting
    # Also filter to games with opening_moneyline
    df_home = df[(df['team'] == df['home_team']) & df['market_prob'].notna()]

    print(f"Total games with opening moneyline: {len(df_home)}")
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

    # Sort by Brier score (ascending - lower is better)
    results.sort(key=lambda x: x['brier'])

    # Print results
    print("=" * 85)
    print("MONEYLINE COMBINATION ANALYSIS RESULTS (with Market Benchmark)")
    print("Ranked by Brier Score (lower = better probability calibration)")
    print("=" * 85)
    print()
    print(f"{'Rank':<5} {'Combination':<15} {'Games':<8} {'Brier':<10} {'Log Loss':<10} {'Accuracy':<10}")
    print("-" * 85)

    for i, row in enumerate(results, 1):
        marker = " <-- MARKET" if row['is_market'] else ""
        print(f"{i:<5} {row['name']:<15} {row['games']:<8} {row['brier']:<10.4f} {row['log_loss']:<10.4f} {row['accuracy']:.2f}%{marker}")

    # Find best model (excluding market)
    model_results = [r for r in results if not r['is_market']]
    best_model = model_results[0] if model_results else None

    print()
    print("=" * 85)
    if market_result:
        print(f"MARKET BENCHMARK (Opening Moneyline Implied Prob):")
        print(f"  Brier Score: {market_result['brier']:.4f}")
        print(f"  Log Loss: {market_result['log_loss']:.4f}")
        print(f"  Accuracy: {market_result['accuracy']:.2f}%")
        print(f"  Games: {market_result['games']}")
    if best_model:
        print()
        print(f"BEST MODEL COMBINATION: {best_model['name']}")
        print(f"  Brier Score: {best_model['brier']:.4f}")
        print(f"  Log Loss: {best_model['log_loss']:.4f}")
        print(f"  Accuracy: {best_model['accuracy']:.2f}%")
        print(f"  Games: {best_model['games']}")
        if market_result:
            diff = best_model['brier'] - market_result['brier']
            if diff < 0:
                print(f"  --> BEATS market by {abs(diff):.4f} Brier points")
            else:
                print(f"  --> WORSE than market by {diff:.4f} Brier points")
    print("=" * 85)

    # Write markdown output
    reports_dir = Path(__file__).parent.parent.parent / "analysis" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(reports_dir / 'moneyline_combination_analysis.md', 'w') as f:
        f.write("# Moneyline Model Combination Analysis\n\n")
        f.write("## Results Ranked by Brier Score (lower = better)\n\n")
        f.write("| Rank | Combination | Games | Brier | Log Loss | Accuracy |\n")
        f.write("|------|-------------|-------|-------|----------|----------|\n")

        for i, row in enumerate(results, 1):
            marker = " ⭐" if row['is_market'] else ""
            f.write(f"| {i} | {row['name']}{marker} | {row['games']} | {row['brier']:.4f} | {row['log_loss']:.4f} | {row['accuracy']:.2f}% |\n")

        f.write("\n⭐ = Market benchmark (opening moneyline implied probability)\n")

        if market_result:
            f.write(f"\n## Market Benchmark\n\n")
            f.write(f"- **Brier Score**: {market_result['brier']:.4f}\n")
            f.write(f"- **Log Loss**: {market_result['log_loss']:.4f}\n")
            f.write(f"- **Accuracy**: {market_result['accuracy']:.2f}%\n")
            f.write(f"- **Games**: {market_result['games']}\n")

        if best_model:
            f.write(f"\n## Best Model Combination: **{best_model['name']}**\n\n")
            f.write(f"- **Brier Score**: {best_model['brier']:.4f}\n")
            f.write(f"- **Log Loss**: {best_model['log_loss']:.4f}\n")
            f.write(f"- **Accuracy**: {best_model['accuracy']:.2f}%\n")
            f.write(f"- **Games**: {best_model['games']}\n")
            if market_result:
                diff = best_model['brier'] - market_result['brier']
                if diff < 0:
                    f.write(f"\n**Beats market by {abs(diff):.4f} Brier points**\n")
                else:
                    f.write(f"\n**Worse than market by {diff:.4f} Brier points**\n")

        f.write("\n## Legend\n\n")
        f.write("- **KP** = KenPom\n")
        f.write("- **BT** = Barttorvik\n")
        f.write("- **EM** = EvanMiya\n")
        f.write("- **MARKET** = Opening moneyline implied probability\n")
        f.write("\n## Metrics Explained\n\n")
        f.write("- **Brier Score**: Mean squared error between predicted probability and actual outcome (0 or 1). Lower is better. Perfect = 0, random = 0.25.\n")
        f.write("- **Log Loss**: Logarithmic loss penalizing confident wrong predictions heavily. Lower is better.\n")
        f.write("- **Accuracy**: % of games where the predicted favorite (prob > 50%) actually won.\n")
        f.write("\n## Methodology\n\n")
        f.write("- For each model combination, win probability is calculated as the **average** of included model probabilities.\n")
        f.write("- Market probability is derived from opening moneyline odds using standard implied probability formula.\n")
        f.write("- Only games with opening moneyline data are included.\n")
        f.write("- Note: Hasla does not provide win probabilities, so only KP, BT, EM are tested.\n")

    print(f"\nResults written to {reports_dir / 'moneyline_combination_analysis.md'}")


if __name__ == '__main__':
    main()
