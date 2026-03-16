# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///

import pandas as pd
from pathlib import Path

df = pd.read_csv(Path(__file__).parent.parent.parent / 'graded_results.csv')
df = df[df['team'] == df['home_team']]

print(f"Total games (home team only): {len(df)}")
print()

# Check individual model data availability
models = {
    'KP': 'projected_total_kenpom',
    'BT': 'projected_total_barttorvik',
    'EM': 'projected_total_evanmiya',
    'HA': 'projected_total_hasla'
}

print("=== INDIVIDUAL MODEL DATA ===")
for name, col in models.items():
    count = df[col].notna().sum()
    pct = count / len(df) * 100
    print(f"{name}: {count} games ({pct:.1f}%)")

print()
print("=== COMBINATION DATA (games with ALL models in combo) ===")

from itertools import combinations

all_models = list(models.keys())
for r in range(1, len(all_models) + 1):
    for combo in combinations(all_models, r):
        cols = [models[m] for m in combo]
        count = df[cols].notna().all(axis=1).sum()
        pct = count / len(df) * 100
        combo_name = '+'.join(combo)
        print(f"{combo_name}: {count} games ({pct:.1f}%)")

print()
print("=== WHAT THE ANALYSIS USES ===")
print("For each combo, we filter to games where:")
print("1. opening_total is not null")
print("2. opening_spread is not null")
print("3. over_hit is not null")
print("4. ALL models in the combo have data")
print()

# Check the actual filter used in analysis
base_filter = df['opening_total'].notna() & df['opening_spread'].notna() & df['over_hit'].notna()
print(f"Games with opening_total + opening_spread + over_hit: {base_filter.sum()}")
print()

print("=== ACTUAL GAMES USED PER COMBO ===")
for r in range(1, len(all_models) + 1):
    for combo in combinations(all_models, r):
        cols = [models[m] for m in combo]
        full_filter = base_filter & df[cols].notna().all(axis=1)
        count = full_filter.sum()
        combo_name = '+'.join(combo)
        print(f"{combo_name}: {count} games")
