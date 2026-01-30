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

# Spread std dev for combo models only
df['Spread Std. Dev.'] = df[spread_cols].std(axis=1, skipna=True).round(1)

# --- Moneyline: mean(BT, EM), raw (no devigged blend) ---
ml_cols = ['win_prob_barttorvik', 'win_prob_evanmiya']
df['Moneyline Win Probability'] = df[ml_cols].mean(axis=1, skipna=False)
ml_implied = df['Current Moneyline'].apply(american_odds_to_implied_probability)
df['Moneyline Edge'] = df['Moneyline Win Probability'] - ml_implied

# Moneyline std dev for combo models only
df['Moneyline Std. Dev.'] = df[ml_cols].std(axis=1, skipna=True).round(3)

# --- Totals: mean(KP, BT, HA) ---
total_cols = ['projected_total_kenpom', 'projected_total_barttorvik', 'projected_total_hasla']
df['model_total'] = df[total_cols].mean(axis=1, skipna=False)
df['Over Total Edge'] = (df['model_total'] - df['market_total']) / 100
df['Under Total Edge'] = (df['market_total'] - df['model_total']) / 100

# Totals std dev for combo models only
df['Totals Std. Dev.'] = df[total_cols].std(axis=1, skipna=True).round(1)

# --- Clear lookup-table-specific columns ---
for col in ['Predicted Outcome', 'Spread Cover Probability',
            'Over Cover Probability', 'Under Cover Probability', 'average_total']:
    if col in df.columns:
        df[col] = np.nan


# --- Consensus flags for combo models ---
def calc_spread_consensus(row):
    """KP+BT agree on direction vs market spread."""
    try:
        market = row.get('Consensus Spread')
        kp = row.get('spread_kenpom')
        bt = row.get('spread_barttorvik')
        if pd.isna(market) or pd.isna(kp) or pd.isna(bt):
            return 0
        abs_m = abs(market)
        abs_kp = abs(kp)
        abs_bt = abs(bt)
        if (abs_kp > abs_m and abs_bt > abs_m) or (abs_kp < abs_m and abs_bt < abs_m):
            return 1
        return 0
    except Exception:
        return 0


def calc_ml_consensus(row):
    """BT+EM agree on direction vs implied probability."""
    try:
        ml = row.get('Current Moneyline')
        bt = row.get('win_prob_barttorvik')
        em = row.get('win_prob_evanmiya')
        if pd.isna(ml) or pd.isna(bt) or pd.isna(em):
            return 0
        implied = american_odds_to_implied_probability(ml)
        if pd.isna(implied):
            return 0
        if (bt > implied and em > implied) or (bt < implied and em < implied):
            return 1
        return 0
    except Exception:
        return 0


def calc_over_consensus(row):
    """KP+BT+HA all above market total."""
    try:
        mt = row.get('market_total')
        kp = row.get('projected_total_kenpom')
        bt = row.get('projected_total_barttorvik')
        ha = row.get('projected_total_hasla')
        if pd.isna(mt) or pd.isna(kp) or pd.isna(bt) or pd.isna(ha):
            return 0
        if kp > mt and bt > mt and ha > mt:
            return 1
        return 0
    except Exception:
        return 0


def calc_under_consensus(row):
    """KP+BT+HA all below market total."""
    try:
        mt = row.get('market_total')
        kp = row.get('projected_total_kenpom')
        bt = row.get('projected_total_barttorvik')
        ha = row.get('projected_total_hasla')
        if pd.isna(mt) or pd.isna(kp) or pd.isna(bt) or pd.isna(ha):
            return 0
        if kp < mt and bt < mt and ha < mt:
            return 1
        return 0
    except Exception:
        return 0


df['spread_consensus_flag'] = df.apply(calc_spread_consensus, axis=1)
df['moneyline_consensus_flag'] = df.apply(calc_ml_consensus, axis=1)
df['over_consensus_flag'] = df.apply(calc_over_consensus, axis=1)
df['under_consensus_flag'] = df.apply(calc_under_consensus, axis=1)


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
    'Opening Spread', 'Edge For Covering Spread', 'Opening Spread Edge', 'Spread Std. Dev.', 'spread_barttorvik',
    'spread_kenpom', 'spread_evanmiya', 'spread_hasla',
    # Moneyline columns
    'Moneyline Win Probability', 'Opening Moneyline', 'Current Moneyline', 'Devigged Probability', 'Moneyline Edge', 'Opening Moneyline Edge', 'Moneyline Std. Dev.',
    'win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya',
    # Totals framework columns
    'spread_category', 'market_total', 'model_total', 'average_total', 'Opening Total', 'theoddsapi_total', 'Totals Std. Dev.',
    'projected_total_barttorvik', 'projected_total_kenpom', 'projected_total_evanmiya', 'projected_total_hasla',
    'Over Cover Probability', 'Under Cover Probability',
    'Over Total Edge', 'Under Total Edge', 'Opening Over Edge', 'Opening Under Edge',
    # Consensus flags
    'spread_consensus_flag', 'moneyline_consensus_flag', 'over_consensus_flag', 'under_consensus_flag'
]

available_columns = [col for col in column_order if col in df.columns]
df = df[available_columns]

df.to_csv(output_file, index=False)
print(f"\nWrote {len(df)} rows to {output_file}")
print("Done.")
