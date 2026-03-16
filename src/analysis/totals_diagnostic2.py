# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "numpy"]
# ///

import pandas as pd
import numpy as np
from pathlib import Path

base_path = Path(__file__).parent.parent.parent

graded = pd.read_csv(base_path / 'graded_results.csv')
graded = graded[graded['team'] == graded['home_team']].copy()

print("=== MODEL-BY-MODEL TOTALS ACCURACY ===\n")

models = ['kenpom', 'barttorvik', 'evanmiya', 'hasla']

for model in models:
    col = f'projected_total_{model}'
    df = graded[graded[col].notna() & graded['opening_total'].notna() & graded['over_hit'].notna()].copy()

    if len(df) == 0:
        print(f"{model}: No data")
        continue

    df['model_says_over'] = df[col] > df['opening_total']
    df['edge'] = abs(df[col] - df['opening_total'])

    print(f"{model.upper()} ({len(df)} games):")

    # Overall
    over_bets = df[df['model_says_over'] == True]
    under_bets = df[df['model_says_over'] == False]
    over_wins = (over_bets['over_hit'] == True).sum()
    under_wins = (under_bets['under_hit'] == True).sum()
    total = len(df)
    wins = over_wins + under_wins
    print(f"  Overall: {wins}/{total} ({wins/total*100:.1f}%)")

    # By edge threshold
    for edge_thresh in [2, 3, 4, 5]:
        filtered = df[df['edge'] >= edge_thresh]
        if len(filtered) < 20:
            continue
        over_bets = filtered[filtered['model_says_over'] == True]
        under_bets = filtered[filtered['model_says_over'] == False]
        over_wins = (over_bets['over_hit'] == True).sum()
        under_wins = (under_bets['under_hit'] == True).sum()
        total = len(filtered)
        wins = over_wins + under_wins
        roi = ((wins * (100/110)) - (total - wins)) / total * 100
        print(f"  Edge >= {edge_thresh}: {wins}/{total} ({wins/total*100:.1f}%), ROI: {roi:+.1f}%")
    print()

# Check if model UNDER-predicting vs OVER-predicting matters
print("\n=== DIRECTION BREAKDOWN ===\n")
print("Checking if models are biased high or low...\n")

for model in models:
    col = f'projected_total_{model}'
    df = graded[graded[col].notna() & graded['opening_total'].notna() & graded['over_hit'].notna()].copy()

    if len(df) == 0:
        continue

    df['model_higher'] = df[col] > df['opening_total']
    df['actual_total'] = df['home_score'] + df['away_score']

    # When model predicts HIGHER than market
    higher = df[df['model_higher'] == True]
    # When model predicts LOWER than market
    lower = df[df['model_higher'] == False]

    print(f"{model.upper()}:")
    print(f"  Model predicts HIGHER than market: {len(higher)} games")
    if len(higher) > 0:
        over_hit_rate = higher['over_hit'].mean()
        print(f"    Over actually hit: {over_hit_rate:.1%} (need 52.4% to profit)")

    print(f"  Model predicts LOWER than market: {len(lower)} games")
    if len(lower) > 0:
        under_hit_rate = lower['under_hit'].mean()
        print(f"    Under actually hit: {under_hit_rate:.1%} (need 52.4% to profit)")
    print()

# Check average model error
print("\n=== MODEL BIAS CHECK ===\n")
for model in models:
    col = f'projected_total_{model}'
    df = graded[graded[col].notna() & graded['opening_total'].notna()].copy()
    df['actual_total'] = df['home_score'] + df['away_score']

    model_error = (df[col] - df['actual_total']).mean()
    market_error = (df['opening_total'] - df['actual_total']).mean()

    print(f"{model.upper()}:")
    print(f"  Model avg error: {model_error:+.1f} pts (positive = predicts too high)")
    print(f"  Market avg error: {market_error:+.1f} pts")
    print()
