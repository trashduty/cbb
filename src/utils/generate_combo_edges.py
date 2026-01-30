# /// script
# dependencies = [
#   "pandas",
#   "numpy"
# ]
# ///
"""
Generate Combo_Output.csv using specific model combos with lookup-table probabilities.

Uses specific model combos as inputs to the same lookup tables as CBB_Output:
- Spread: KP+BT mean → lookup table → cover_prob → edge
- Moneyline: BT+EM mean (raw, no devigged blend) → edge
- Over/Under: KP+BT+HA mean → lookup table → cover_prob → edge

Reads CBB_Output.csv (already filtered) and writes Combo_Output.csv.
All columns from CBB_Output.csv are preserved and filled.
"""

import pandas as pd
import numpy as np
import os
import sys

# Define file paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
input_file = os.path.join(project_root, 'CBB_Output.csv')
output_file = os.path.join(project_root, 'Combo_Output.csv')
spreads_lookup_path = os.path.join(project_root, 'spreads_lookup_combined.csv')
totals_lookup_path = os.path.join(project_root, 'totals_lookup_combined.csv')

SPREAD_IMPLIED_DEFAULT = 0.5238095238095238  # -110 odds

print(f"Reading from: {input_file}")

if not os.path.exists(input_file):
    print(f"ERROR: {input_file} not found!")
    sys.exit(1)

df = pd.read_csv(input_file)
print(f"Loaded {len(df)} rows from CBB_Output.csv")


def american_odds_to_implied_probability(odds):
    """Convert American odds to implied probability."""
    if not odds or pd.isna(odds):
        return np.nan
    try:
        odds = float(odds)
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    except (ValueError, TypeError):
        return np.nan


def calculate_spread_implied_prob_safe(spread_price):
    """Safely calculate spread implied probability with defaults."""
    if pd.isna(spread_price) or spread_price is None:
        return SPREAD_IMPLIED_DEFAULT
    try:
        spread_price = float(spread_price)
    except (ValueError, TypeError):
        return SPREAD_IMPLIED_DEFAULT
    if abs(spread_price) > 200:
        return SPREAD_IMPLIED_DEFAULT
    if 0 < abs(spread_price) < 100:
        return SPREAD_IMPLIED_DEFAULT
    prob = american_odds_to_implied_probability(spread_price)
    return prob if prob is not None else SPREAD_IMPLIED_DEFAULT


# ============================================================
# 1. SPREAD: model_spread = mean(KP, BT), then lookup table
# ============================================================
spread_cols = ['spread_kenpom', 'spread_barttorvik']
df['model_spread'] = df[spread_cols].mean(axis=1, skipna=False)

# Predicted Outcome: 60% market + 40% model, rounded to 0.5
df['Predicted Outcome'] = ((0.6 * df['market_spread'] + 0.4 * df['model_spread']) * 2).round() / 2

# Spread lookup
try:
    spreads_lookup_df = pd.read_csv(spreads_lookup_path)
    print(f"Loaded spreads lookup table")

    df['market_spread_rounded'] = (df['market_spread'] * 2).round() / 2

    # Calculate spread implied prob from Spread Price if available
    if 'Spread Price' in df.columns:
        df['spread_implied_prob'] = df['Spread Price'].apply(calculate_spread_implied_prob_safe)
    else:
        df['spread_implied_prob'] = SPREAD_IMPLIED_DEFAULT

    # Merge with lookup
    df = df.merge(
        spreads_lookup_df,
        left_on=['total_category', 'market_spread_rounded', 'Predicted Outcome'],
        right_on=['total_category', 'market_spread', 'model_spread'],
        how='left',
        suffixes=('', '_lookup')
    )

    df['Spread Cover Probability'] = df['cover_prob']
    df['Edge For Covering Spread'] = df['Spread Cover Probability'] - df['spread_implied_prob']

    # Clean up lookup columns
    df.drop(columns=['market_spread_rounded', 'market_spread_lookup', 'model_spread_lookup',
                     'cover_prob', 'spread_implied_prob'],
            inplace=True, errors='ignore')

    print(f"  Spread cover prob filled: {df['Spread Cover Probability'].notna().sum()}/{len(df)}")
except FileNotFoundError:
    print("WARNING: spreads_lookup_combined.csv not found")
    df['Spread Cover Probability'] = np.nan
    df['Edge For Covering Spread'] = np.nan



# ============================================================
# 2. MONEYLINE: mean(BT, EM), raw (no devigged blend)
# ============================================================
ml_cols = ['win_prob_barttorvik', 'win_prob_evanmiya']
df['Moneyline Win Probability'] = df[ml_cols].mean(axis=1, skipna=False)
ml_implied = df['Current Moneyline'].apply(american_odds_to_implied_probability)
df['Moneyline Edge'] = df['Moneyline Win Probability'] - ml_implied



# ============================================================
# 3. TOTALS: model_total = mean(KP, BT, HA), then lookup table
# ============================================================
total_cols = ['projected_total_kenpom', 'projected_total_barttorvik', 'projected_total_hasla']
df['model_total'] = df[total_cols].mean(axis=1, skipna=False)

# average_total: 60% market + 40% model, rounded to 0.5
df['average_total'] = ((0.6 * df['market_total'].fillna(0) +
                         0.4 * df['model_total'].fillna(df['market_total'])) * 2).round() / 2

# Totals lookup
try:
    totals_lookup_df = pd.read_csv(totals_lookup_path)
    print(f"Loaded totals lookup table")

    df = df.drop_duplicates(subset=['Game', 'Team'], keep='first')
    df['market_total_rounded'] = (df['market_total'] * 2).round() / 2

    df = df.merge(
        totals_lookup_df,
        left_on=['spread_category', 'market_total_rounded', 'average_total'],
        right_on=['spread_category', 'market_total', 'model_total'],
        how='left',
        suffixes=('', '_lookup')
    )

    df['Over Cover Probability'] = df['over_prob']
    df['Under Cover Probability'] = df['under_prob']

    # Over/Under edges: cover_prob - implied_prob
    # Use Over/Under Price if available, otherwise default to -110 (52.38%)
    if 'Over Price' in df.columns:
        df['over_implied_prob'] = df['Over Price'].apply(american_odds_to_implied_probability)
    else:
        df['over_implied_prob'] = SPREAD_IMPLIED_DEFAULT
    if 'Under Price' in df.columns:
        df['under_implied_prob'] = df['Under Price'].apply(american_odds_to_implied_probability)
    else:
        df['under_implied_prob'] = SPREAD_IMPLIED_DEFAULT
    df['Over Total Edge'] = df['Over Cover Probability'] - df['over_implied_prob']
    df['Under Total Edge'] = df['Under Cover Probability'] - df['under_implied_prob']

    # Clean up lookup columns
    df.drop(columns=['market_total_rounded', 'market_total_lookup', 'model_total_lookup',
                     'over_prob', 'under_prob', 'over_implied_prob', 'under_implied_prob'],
            inplace=True, errors='ignore')

    print(f"  Over cover prob filled: {df['Over Cover Probability'].notna().sum()}/{len(df)}")
except FileNotFoundError:
    print("WARNING: totals_lookup_combined.csv not found")
    df['Over Cover Probability'] = np.nan
    df['Under Cover Probability'] = np.nan
    df['Over Total Edge'] = np.nan
    df['Under Total Edge'] = np.nan



# --- Drop consensus flag and std dev columns ---
drop_cols = ['spread_consensus_flag', 'moneyline_consensus_flag',
             'over_consensus_flag', 'under_consensus_flag',
             'Spread Std. Dev.', 'Moneyline Std. Dev.', 'Totals Std. Dev.']
for col in drop_cols:
    if col in df.columns:
        df.drop(columns=[col], inplace=True)


# ============================================================
# 5. PRESERVE OPENING EDGES from previous Combo_Output.csv
# ============================================================
def preserve_opening_edges(new_df):
    """
    Preserve opening odds/edges from previous Combo_Output.csv.
    Same pattern as preserve_opening_odds in oddsAPI.py.
    """
    if not os.path.exists(output_file):
        print("No existing Combo_Output.csv found, all current edges become opening edges")
        new_df['Opening Spread Edge'] = new_df['Edge For Covering Spread']
        new_df['Opening Moneyline Edge'] = new_df['Moneyline Edge']
        new_df['Opening Over Edge'] = new_df['Over Total Edge']
        new_df['Opening Under Edge'] = new_df['Under Total Edge']
        return new_df

    try:
        existing_df = pd.read_csv(output_file)
        print(f"Loaded {len(existing_df)} rows from existing Combo_Output.csv")

        existing_lookup = {}
        for _, row in existing_df.iterrows():
            key = (row.get('Game'), row.get('Team'))
            existing_lookup[key] = {
                'Opening Spread': row.get('Opening Spread'),
                'Opening Moneyline': row.get('Opening Moneyline'),
                'Opening Total': row.get('Opening Total'),
                'Opening Odds Time': row.get('Opening Odds Time'),
                'Opening Spread Edge': row.get('Opening Spread Edge'),
                'Opening Moneyline Edge': row.get('Opening Moneyline Edge'),
                'Opening Over Edge': row.get('Opening Over Edge'),
                'Opening Under Edge': row.get('Opening Under Edge'),
            }

        preserved_count = 0
        new_count = 0
        for idx, row in new_df.iterrows():
            key = (row.get('Game'), row.get('Team'))
            if key in existing_lookup:
                existing_vals = existing_lookup[key]
                for col in ['Opening Spread', 'Opening Moneyline', 'Opening Total',
                            'Opening Odds Time', 'Opening Spread Edge',
                            'Opening Moneyline Edge', 'Opening Over Edge',
                            'Opening Under Edge']:
                    if pd.notna(existing_vals.get(col)):
                        new_df.at[idx, col] = existing_vals[col]
                preserved_count += 1
            else:
                new_df.at[idx, 'Opening Spread Edge'] = row.get('Edge For Covering Spread')
                new_df.at[idx, 'Opening Moneyline Edge'] = row.get('Moneyline Edge')
                new_df.at[idx, 'Opening Over Edge'] = row.get('Over Total Edge')
                new_df.at[idx, 'Opening Under Edge'] = row.get('Under Total Edge')
                new_count += 1

        print(f"Preserved opening edges for {preserved_count} existing games")
        print(f"Set opening edges for {new_count} new games")
    except Exception as e:
        print(f"Warning: Could not preserve opening edges: {e}")
        new_df['Opening Spread Edge'] = new_df['Edge For Covering Spread']
        new_df['Opening Moneyline Edge'] = new_df['Moneyline Edge']
        new_df['Opening Over Edge'] = new_df['Over Total Edge']
        new_df['Opening Under Edge'] = new_df['Under Total Edge']

    return new_df


df = preserve_opening_edges(df)

# ============================================================
# 6. OUTPUT — same column order as CBB_Output.csv
# ============================================================
column_order = [
    'Game', 'Game Time', 'Opening Odds Time', 'Team',
    # Spread framework columns
    'total_category', 'market_spread', 'Consensus Spread', 'model_spread', 'Predicted Outcome', 'Spread Cover Probability',
    'Opening Spread', 'Edge For Covering Spread', 'Opening Spread Edge', 'spread_barttorvik',
    'spread_kenpom', 'spread_evanmiya', 'spread_hasla',
    # Moneyline columns
    'Moneyline Win Probability', 'Opening Moneyline', 'Current Moneyline', 'Devigged Probability', 'Moneyline Edge', 'Opening Moneyline Edge',
    'win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya',
    # Totals framework columns
    'spread_category', 'market_total', 'model_total', 'average_total', 'Opening Total', 'theoddsapi_total',
    'projected_total_barttorvik', 'projected_total_kenpom', 'projected_total_evanmiya', 'projected_total_hasla',
    'Over Cover Probability', 'Under Cover Probability',
    'Over Total Edge', 'Under Total Edge', 'Opening Over Edge', 'Opening Under Edge',
]

available_columns = [col for col in column_order if col in df.columns]
df = df[available_columns]

df.to_csv(output_file, index=False)
print(f"\nWrote {len(df)} rows to {output_file}")
print("Done.")
