# /// script
# dependencies = [
#   "pandas",
#   "numpy"
# ]
# ///
"""
Generate Combo_Output.csv with simple (non-regressed) edge calculations.

Uses specific model combos instead of lookup tables:
- Spread: KP+BT mean, edge = (market_spread - combo_spread) / 100
- Moneyline: BT+EM mean (raw, no devigged blend), edge = combo_prob - ml_implied_prob
- Over: KP+BT+HA mean, edge = (combo_total - market_total) / 100
- Under: KP+BT+HA mean, edge = (market_total - combo_total) / 100

Reads CBB_Output.csv (already filtered) and writes Combo_Output.csv.
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


# --- Spread: mean(KP, BT) ---
spread_cols = ['spread_kenpom', 'spread_barttorvik']
df['model_spread'] = df[spread_cols].mean(axis=1, skipna=False)
df['Edge For Covering Spread'] = (df['Consensus Spread'] - df['model_spread']) / 100


# --- Moneyline: mean(BT, EM), raw (no devigged blend) ---
ml_cols = ['win_prob_barttorvik', 'win_prob_evanmiya']
df['Moneyline Win Probability'] = df[ml_cols].mean(axis=1, skipna=False)
ml_implied = df['Current Moneyline'].apply(american_odds_to_implied_probability)
df['Moneyline Edge'] = df['Moneyline Win Probability'] - ml_implied


# --- Totals: mean(KP, BT, HA) ---
total_cols = ['projected_total_kenpom', 'projected_total_barttorvik', 'projected_total_hasla']
df['model_total'] = df[total_cols].mean(axis=1, skipna=False)
df['Over Total Edge'] = (df['model_total'] - df['market_total']) / 100
df['Under Total Edge'] = (df['market_total'] - df['model_total']) / 100


# --- Fill derived columns (equivalent to lookup-table outputs) ---
# Predicted Outcome: same blended formula as CBB_Output
df['Predicted Outcome'] = ((0.6 * df['market_spread'] + 0.4 * df['model_spread']) * 2).round() / 2

# Spread Cover Probability: back-calculate from edge + implied prob
# Default spread implied prob is 52.38% (-110 odds)
SPREAD_IMPLIED_DEFAULT = 0.5238095238095238
df['Spread Cover Probability'] = df['Edge For Covering Spread'] + SPREAD_IMPLIED_DEFAULT

# average_total: same blended formula as CBB_Output
df['average_total'] = ((0.6 * df['market_total'] + 0.4 * df['model_total']) * 2).round() / 2

# Over/Under Cover Probability: back-calculate from edge + implied prob
over_implied = df['Over Price'].apply(american_odds_to_implied_probability) if 'Over Price' in df.columns else SPREAD_IMPLIED_DEFAULT
under_implied = df['Under Price'].apply(american_odds_to_implied_probability) if 'Under Price' in df.columns else SPREAD_IMPLIED_DEFAULT
df['Over Cover Probability'] = df['Over Total Edge'] + over_implied
df['Under Cover Probability'] = df['Under Total Edge'] + under_implied


# --- Drop consensus flag and std dev columns ---
drop_cols = ['spread_consensus_flag', 'moneyline_consensus_flag',
             'over_consensus_flag', 'under_consensus_flag',
             'Spread Std. Dev.', 'Moneyline Std. Dev.', 'Totals Std. Dev.']
for col in drop_cols:
    if col in df.columns:
        df.drop(columns=[col], inplace=True)


# --- Preserve opening edges from previous Combo_Output.csv ---
def preserve_opening_edges(new_df):
    """
    Preserve opening odds/edges from previous Combo_Output.csv.
    Same pattern as preserve_opening_odds in oddsAPI.py.
    """
    if not os.path.exists(output_file):
        print("No existing Combo_Output.csv found, all current edges become opening edges")
        # Set opening edges to current edges for first run
        new_df['Opening Spread Edge'] = new_df['Edge For Covering Spread']
        new_df['Opening Moneyline Edge'] = new_df['Moneyline Edge']
        new_df['Opening Over Edge'] = new_df['Over Total Edge']
        new_df['Opening Under Edge'] = new_df['Under Total Edge']
        return new_df

    try:
        existing_df = pd.read_csv(output_file)
        print(f"Loaded {len(existing_df)} rows from existing Combo_Output.csv")

        # Build lookup from existing data
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
                # Preserve existing opening values
                for col in ['Opening Spread', 'Opening Moneyline', 'Opening Total',
                            'Opening Odds Time', 'Opening Spread Edge',
                            'Opening Moneyline Edge', 'Opening Over Edge',
                            'Opening Under Edge']:
                    if pd.notna(existing_vals.get(col)):
                        new_df.at[idx, col] = existing_vals[col]
                preserved_count += 1
            else:
                # New game: set opening edges to current combo edges
                new_df.at[idx, 'Opening Spread Edge'] = row.get('Edge For Covering Spread')
                new_df.at[idx, 'Opening Moneyline Edge'] = row.get('Moneyline Edge')
                new_df.at[idx, 'Opening Over Edge'] = row.get('Over Total Edge')
                new_df.at[idx, 'Opening Under Edge'] = row.get('Under Total Edge')
                new_count += 1

        print(f"Preserved opening edges for {preserved_count} existing games")
        print(f"Set opening edges for {new_count} new games")
    except Exception as e:
        print(f"Warning: Could not preserve opening edges: {e}")
        # Fall back to current edges as opening
        new_df['Opening Spread Edge'] = new_df['Edge For Covering Spread']
        new_df['Opening Moneyline Edge'] = new_df['Moneyline Edge']
        new_df['Opening Over Edge'] = new_df['Over Total Edge']
        new_df['Opening Under Edge'] = new_df['Under Total Edge']

    return new_df


df = preserve_opening_edges(df)

# --- Output with same column order as CBB_Output.csv ---
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
