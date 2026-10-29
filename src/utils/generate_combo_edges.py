# /// script
# dependencies = [
#   "pandas",
#   "numpy",
#   "pytz"
# ]
# ///
"""
Generate Combo_Output.csv using specific model combos with lookup-table probabilities.

Uses specific model combos as inputs to the same lookup tables as CBB_Output:
- Spread: 35% KP + 45% EM + 20% BT → rounded lookup → cover_prob → edge
- Moneyline: 35% KP + 45% EM + 20% BT win probability → edge
- Over/Under: 35% KP + 45% EM + 20% BT total → rounded lookup → cover_prob → edge
Missing BT uses 50% KP + 50% EM for that metric. Hasla is not weighted.

Reads CBB_Output.csv and writes Combo_Output.csv (filtered to remove started games).
All columns from CBB_Output.csv are preserved and filled.
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
import pytz

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

if len(df) == 0:
    print("No rows to process, writing empty Combo_Output.csv")
    df.to_csv(output_file, index=False)
    sys.exit(0)


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



def weighted_prediction(frame, kenpom_column, evanmiya_column, barttorvik_column):
    """Require KP and EM; use 35/45/20 with BT or 50/50 without it."""
    values = frame.reindex(columns=[kenpom_column, evanmiya_column, barttorvik_column])
    values = values.apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
    kp, em, bt = (values[column] for column in values.columns)
    prediction = (0.35 * kp + 0.45 * em + 0.20 * bt).where(
        bt.notna(), 0.50 * kp + 0.50 * em
    )
    return prediction.where(kp.notna() & em.notna())


BEST_BOOK_COLUMNS = [
    f'Best {market} {field}'
    for market in ('Spread', 'Moneyline', 'Over', 'Under')
    for field in (('Book', 'Price', 'Probability', 'Edge') if market == 'Moneyline'
                  else ('Book', 'Line', 'Price', 'Probability', 'Edge'))
]


def add_best_book_edges(frame, quotes, spread_lookup, total_lookup):
    """CFB-style selection: highest model probability minus quote implied probability.

    Quote lines, prices, and books always stay together. Missing lookup matches
    are excluded, never replaced by consensus probabilities or assumed prices.
    """
    frame = frame.copy()
    for column in BEST_BOOK_COLUMNS:
        frame[column] = None if column.endswith(' Book') else np.nan

    def number(value):
        try:
            result = float(value)
            return result if np.isfinite(result) else None
        except (ValueError, TypeError):
            return None

    def half(value):
        value = number(value)
        return round(value * 2) / 2 if value is not None else None

    def lookup_map(table, keys, probability):
        result = {}
        if table is None or not set(keys + [probability]).issubset(table.columns):
            return result
        for record in table.to_dict('records'):
            key = tuple(number(record[k]) for k in keys)
            value = number(record[probability])
            if None not in key and value is not None and 0 <= value <= 1:
                result[key] = value
        return result

    spread_probs = lookup_map(spread_lookup, ['total_category', 'market_spread', 'model_spread'], 'cover_prob')
    over_probs = lookup_map(total_lookup, ['spread_category', 'market_total', 'model_total'], 'over_prob')
    under_probs = lookup_map(total_lookup, ['spread_category', 'market_total', 'model_total'], 'under_prob')
    required = {'Home Team', 'Away Team', 'Game Time', 'Team', 'Market', 'Bookmaker', 'Line', 'Price'}
    if quotes is None or quotes.empty or not required.issubset(quotes.columns):
        return frame, pd.DataFrame()

    grouped = {}
    for quote in quotes.to_dict('records'):
        teams = tuple(sorted([str(quote['Home Team']), str(quote['Away Team'])]))
        grouped.setdefault((teams, str(quote['Game Time'])), []).append(quote)

    audit = []
    for index, row in frame.iterrows():
        teams = str(row.get('Game', '')).split(' vs. ')
        if len(teams) != 2:
            continue
        candidates = {market: [] for market in ('Spread', 'Moneyline', 'Over', 'Under')}
        for quote in grouped.get((tuple(sorted(teams)), str(row.get('Game Time'))), []):
            market = quote['Market']
            if market in ('Spread', 'Moneyline') and quote['Team'] != row.get('Team'):
                continue
            price = number(quote['Price'])
            if price is None or abs(price) < 100 or not quote['Bookmaker']:
                continue
            implied = american_odds_to_implied_probability(price)
            line = number(quote['Line'])
            if market == 'Spread' and line is not None:
                probability = spread_probs.get((number(row.get('total_category')), half(line), half(row.get('Predicted Outcome'))))
            elif market == 'Moneyline':
                probability = number(row.get('Moneyline Win Probability'))
            elif market in ('Over', 'Under') and line is not None:
                probabilities = over_probs if market == 'Over' else under_probs
                probability = probabilities.get((number(row.get('spread_category')), half(line), half(row.get('average_total'))))
            else:
                continue
            if probability is None or not 0 <= probability <= 1:
                continue
            edge = probability - implied
            candidate = {'Book': str(quote['Bookmaker']), 'Line': line, 'Price': price,
                         'Probability': probability, 'Edge': edge}
            candidates[market].append(candidate)
            audit.append({'Game': row.get('Game'), 'Game Time': row.get('Game Time'),
                          'Team': row.get('Team'), 'Market': market, **candidate})
        for market, options in candidates.items():
            if not options:
                continue
            # CFB breaks equal-edge ties alphabetically by sportsbook.
            best = min(options, key=lambda option: (-option['Edge'], option['Book'],
                       option['Line'] if option['Line'] is not None else 0, option['Price']))
            for field, value in best.items():
                column = f'Best {market} {field}'
                if column in BEST_BOOK_COLUMNS:
                    frame.at[index, column] = value
    return frame, pd.DataFrame(audit)


# ============================================================
# 1. SPREAD: weighted KP/EM/BT, then lookup table
# ============================================================

# Back-calculate spread implied prob from CBB_Output's existing data
# (Spread Price column is not in CBB_Output.csv)
df['spread_implied_prob'] = df['Spread Cover Probability'] - df['Edge For Covering Spread']
df['spread_implied_prob'] = df['spread_implied_prob'].fillna(SPREAD_IMPLIED_DEFAULT)

df['model_spread'] = weighted_prediction(
    df, 'spread_kenpom', 'spread_evanmiya', 'spread_barttorvik'
)

# Display and lookup use the weighted model prediction, rounded to 0.5.
df['Predicted Outcome'] = (df['model_spread'] * 2).round() / 2

# Spread lookup
try:
    spreads_lookup_df = pd.read_csv(spreads_lookup_path)
    print(f"Loaded spreads lookup table")

    df['market_spread_rounded'] = (df['market_spread'] * 2).round() / 2

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
# 2. MONEYLINE: weighted KP/EM/BT, raw (no devigged blend)
# ============================================================
df['Moneyline Win Probability'] = weighted_prediction(
    df, 'win_prob_kenpom', 'win_prob_evanmiya', 'win_prob_barttorvik'
)
ml_implied = df['Current Moneyline'].apply(american_odds_to_implied_probability)
df['Moneyline Edge'] = df['Moneyline Win Probability'] - ml_implied



# Save original CBB totals values to back-calculate implied probs later
# (Over/Under Price columns are not in CBB_Output.csv)
df['Over Cover Probability_orig'] = df['Over Cover Probability']
df['Under Cover Probability_orig'] = df['Under Cover Probability']
df['Over Total Edge_orig'] = df['Over Total Edge']
df['Under Total Edge_orig'] = df['Under Total Edge']

# ============================================================
# 3. TOTALS: weighted KP/EM/BT, non-regressed lookup
# ============================================================
df['model_total'] = weighted_prediction(
    df, 'projected_total_kenpom', 'projected_total_evanmiya', 'projected_total_barttorvik'
)

# average_total: non-regressed (raw model total), rounded to 0.5
df['average_total'] = (df['model_total'] * 2).round() / 2

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
    # Back-calculate the actual implied probs from CBB_Output's existing data
    # (Over Price / Under Price are not in CBB_Output.csv, but implied_prob = cover_prob - edge)
    df['over_implied_prob'] = df['Over Cover Probability_orig'] - df['Over Total Edge_orig']
    df['under_implied_prob'] = df['Under Cover Probability_orig'] - df['Under Total Edge_orig']
    # Fall back to -110 default if CBB values were missing
    df['over_implied_prob'] = df['over_implied_prob'].fillna(SPREAD_IMPLIED_DEFAULT)
    df['under_implied_prob'] = df['under_implied_prob'].fillna(SPREAD_IMPLIED_DEFAULT)

    df['Over Total Edge'] = df['Over Cover Probability'] - df['over_implied_prob']
    df['Under Total Edge'] = df['Under Cover Probability'] - df['under_implied_prob']

    # Clean up lookup columns
    df.drop(columns=['market_total_rounded', 'market_total_lookup', 'model_total_lookup',
                     'over_prob', 'under_prob', 'over_implied_prob', 'under_implied_prob',
                     'Over Cover Probability_orig', 'Under Cover Probability_orig',
                     'Over Total Edge_orig', 'Under Total Edge_orig'],
            inplace=True, errors='ignore')

    print(f"  Over cover prob filled: {df['Over Cover Probability'].notna().sum()}/{len(df)}")
except FileNotFoundError:
    print("WARNING: totals_lookup_combined.csv not found")
    df['Over Cover Probability'] = np.nan
    df['Under Cover Probability'] = np.nan
    df['Over Total Edge'] = np.nan
    df['Under Total Edge'] = np.nan



# Rank each actual quote by its model-based edge, as in the CFB pipeline.
quote_path = os.path.join(project_root, 'data', 'sportsbook_quotes.csv')
quotes = pd.read_csv(quote_path, keep_default_na=False) if os.path.exists(quote_path) else None
df, best_book_audit = add_best_book_edges(
    df, quotes, globals().get('spreads_lookup_df'), globals().get('totals_lookup_df')
)
os.makedirs(os.path.join(project_root, 'data'), exist_ok=True)
best_book_audit.to_csv(os.path.join(project_root, 'data', 'combo_sportsbook_odds_audit.csv'), index=False)

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

column_order += BEST_BOOK_COLUMNS

available_columns = [col for col in column_order if col in df.columns]
df = df[available_columns]

# ============================================================
# 7. FILTER STARTED GAMES
# ============================================================
et = pytz.timezone('US/Eastern')
now_et = datetime.now(et)
buffer_minutes = 15
cutoff_time = now_et - timedelta(minutes=buffer_minutes)

def parse_game_time(time_str):
    """Parse game time from format 'Nov 03 07:00PM ET' to datetime object."""
    if pd.isna(time_str) or time_str == '':
        return None
    try:
        time_str_clean = time_str.replace(' ET', '').strip()
        dt = datetime.strptime(f"{now_et.year} {time_str_clean}", "%Y %b %d %I:%M%p")
        return et.localize(dt)
    except Exception:
        return None

df['parsed_time'] = df['Game Time'].apply(parse_game_time)
df['keep'] = df['parsed_time'].apply(lambda t: True if pd.isna(t) else t >= cutoff_time)

games_removed = (~df['keep']).sum()
if games_removed > 0:
    print(f"\nFiltered {games_removed} rows for started games")
df = df[df['keep']].drop(columns=['parsed_time', 'keep'])

df.to_csv(output_file, index=False)
print(f"\nWrote {len(df)} rows to {output_file}")
print("Done.")

