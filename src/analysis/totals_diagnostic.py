# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "numpy"]
# ///

import pandas as pd
import numpy as np
from pathlib import Path

base_path = Path(__file__).parent.parent.parent

# Load data
graded = pd.read_csv(base_path / 'graded_results.csv')
totals_lookup = pd.read_csv(base_path / 'totals_lookup_combined.csv')

# Filter to home team only
graded = graded[graded['team'] == graded['home_team']].copy()

print("=== DIAGNOSTIC CHECK ===\n")

# 1. Check the lookup table structure
print("1. LOOKUP TABLE STRUCTURE:")
print(f"   Columns: {totals_lookup.columns.tolist()}")
print(f"   Rows: {len(totals_lookup)}")
print(f"   Sample:")
print(totals_lookup.head(10).to_string())
print()

# 2. Check over_hit/under_hit distribution
print("2. OVER/UNDER HIT RATES:")
over_games = graded[graded['over_hit'].notna()]
print(f"   Games with over_hit data: {len(over_games)}")
print(f"   Over hit rate: {over_games['over_hit'].mean():.1%}")
under_games = graded[graded['under_hit'].notna()]
print(f"   Under hit rate: {under_games['under_hit'].mean():.1%}")
print()

# 3. Check a few example lookups
print("3. SAMPLE LOOKUP CHECK:")
sample = graded[graded['opening_total'].notna() & graded['projected_total_kenpom'].notna()].head(5)
for _, row in sample.iterrows():
    market = row['opening_total']
    model = row['projected_total_kenpom']
    actual = row['home_score'] + row['away_score']
    over_hit = row['over_hit']

    # What we look up
    model_rounded = round(model * 2) / 2
    market_rounded = round(market * 2) / 2

    # What production does (0.6 market + 0.4 model)
    blended = 0.6 * market + 0.4 * model
    blended_rounded = round(blended * 2) / 2

    print(f"   Market: {market}, Model (KP): {model:.1f}, Actual: {actual}")
    print(f"   Over hit: {over_hit}, Model > Market: {model > market}")
    print(f"   We look up model_total={model_rounded}, production uses blended={blended_rounded}")
    print()

# 4. Check how many lookups succeed vs fail
print("4. LOOKUP SUCCESS RATE:")
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

test_df = graded[graded['opening_total'].notna() & graded['opening_spread'].notna() & graded['projected_total_kenpom'].notna()].copy()
test_df['spread_cat'] = test_df['opening_spread'].apply(get_spread_category)
test_df['model_rounded'] = (test_df['projected_total_kenpom'] * 2).round() / 2
test_df['market_rounded'] = (test_df['opening_total'] * 2).round() / 2

# Try lookups
success = 0
fail = 0
for _, row in test_df.iterrows():
    match = totals_lookup[
        (totals_lookup['spread_category'] == row['spread_cat']) &
        (totals_lookup['market_total'] == row['market_rounded']) &
        (totals_lookup['model_total'] == row['model_rounded'])
    ]
    if len(match) > 0:
        success += 1
    else:
        fail += 1

print(f"   Lookups succeeded: {success} ({success/(success+fail)*100:.1f}%)")
print(f"   Lookups failed: {fail} ({fail/(success+fail)*100:.1f}%)")
print()

# 5. Check if the simple approach works
print("5. SIMPLE APPROACH (no lookup table):")
print("   Just bet OVER when model > market, UNDER when model < market")
test_df['model_says_over'] = test_df['projected_total_kenpom'] > test_df['opening_total']
over_correct = ((test_df['model_says_over'] == True) & (test_df['over_hit'] == True)).sum()
under_correct = ((test_df['model_says_over'] == False) & (test_df['under_hit'] == True)).sum()
total_bets = len(test_df)
print(f"   Total games: {total_bets}")
print(f"   Correct predictions: {over_correct + under_correct} ({(over_correct + under_correct)/total_bets*100:.1f}%)")
print(f"   Break-even needed: 52.4%")

# 6. Check with edge filter
print()
print("6. SIMPLE APPROACH WITH EDGE FILTER:")
for edge_thresh in [1, 2, 3, 4, 5]:
    test_df['edge'] = abs(test_df['projected_total_kenpom'] - test_df['opening_total'])
    filtered = test_df[test_df['edge'] >= edge_thresh]
    if len(filtered) == 0:
        continue
    over_bets = filtered[filtered['model_says_over'] == True]
    under_bets = filtered[filtered['model_says_over'] == False]
    over_wins = (over_bets['over_hit'] == True).sum()
    under_wins = (under_bets['under_hit'] == True).sum()
    total = len(filtered)
    wins = over_wins + under_wins
    # ROI at -110
    roi = ((wins * (100/110)) - (total - wins)) / total * 100
    print(f"   Edge >= {edge_thresh} pts: {total} games, {wins}/{total} correct ({wins/total*100:.1f}%), ROI: {roi:+.1f}%")
