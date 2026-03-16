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
print('Spreads:')
print(f'  opening_spread not null: {df_home["opening_spread"].notna().sum()}')
print(f'  spread_covered not null: {df_home["spread_covered"].notna().sum()}')
print(f'  Both not null: {(df_home["opening_spread"].notna() & df_home["spread_covered"].notna()).sum()}')
print()
print('Moneylines:')
print(f'  opening_moneyline not null: {df_home["opening_moneyline"].notna().sum()}')
print(f'  moneyline_won not null: {df_home["moneyline_won"].notna().sum()}')
print(f'  Both not null: {(df_home["opening_moneyline"].notna() & df_home["moneyline_won"].notna()).sum()}')
print()
print('=== METHODOLOGY DIFFERENCES ===')
print('Spreads: abs(edge) >= threshold (bet BOTH directions)')
print('Moneylines: edge >= threshold (positive edge only, one direction)')
print()
print('So if both had 1000 games with valid data:')
print('  - Spreads: bet all 1000 (both directions count)')
print('  - Moneylines: bet ~500 (only positive edge)')
