# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///

import pandas as pd
from pathlib import Path

df = pd.read_csv(Path(__file__).parent.parent.parent / 'graded_results.csv')
df_home = df[df['team'] == df['home_team']]

print('=== DATA AVAILABILITY (home team rows only) ===')
print(f'Total home team rows: {len(df_home)}')
print()
print('Totals:')
print(f'  opening_total not null: {df_home["opening_total"].notna().sum()}')
print(f'  over_hit not null: {df_home["over_hit"].notna().sum()}')
print(f'  Both not null: {(df_home["opening_total"].notna() & df_home["over_hit"].notna()).sum()}')
print()
print('Moneylines:')
print(f'  opening_moneyline not null: {df_home["opening_moneyline"].notna().sum()}')
print(f'  moneyline_won not null: {df_home["moneyline_won"].notna().sum()}')
print(f'  Both not null: {(df_home["opening_moneyline"].notna() & df_home["moneyline_won"].notna()).sum()}')
print()
print('=== METHODOLOGY DIFFERENCES ===')
print('Totals: abs(edge) >= threshold (bet BOTH directions - over or under)')
print('Moneylines: edge >= threshold (positive edge only)')
print()
print('=== CURRENT TOTALS METHOD (edge_analysis_regressed.md) ===')
print('1. combo_total = mean of model totals')
print('2. Look up probability from totals_lookup_combined.csv')
print('3. Regress: p_final = 0.4 * lookup_prob + 0.6 * 0.50')
print('4. Edge = p_final - 52.38%')
print('5. Bet if |edge| >= threshold')
