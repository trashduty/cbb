# /// script
# dependencies = [
#   "pandas",
#   "pytz"
# ]
# ///
"""
Filter out games that have already started from CBB_Output.csv

This script reads CBB_Output.csv, removes rows for games that have started
(based on Eastern Time), and overwrites the file with only upcoming games.

IMPORTANT: Before removing games, this script captures a snapshot of all
opening and closing data to game_snapshots.csv for later grading.
"""

import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
import sys

# Get current Eastern Time
et = pytz.timezone('US/Eastern')
now_et = datetime.now(et)

# Define file paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
output_file = os.path.join(project_root, 'CBB_Output.csv')
game_snapshots_file = os.path.join(project_root, 'game_snapshots.csv')

print(f"Current ET time: {now_et.strftime('%b %d %I:%M%p ET')}")
print(f"Reading from: {output_file}")

# Check if file exists
if not os.path.exists(output_file):
    print(f"ERROR: {output_file} not found!")
    sys.exit(1)

# Read the CSV
df = pd.read_csv(output_file)
initial_row_count = len(df)
print(f"Initial row count: {initial_row_count}")

# Function to parse game time from format "Nov 03 07:00PM ET"
def parse_game_time(time_str):
    """
    Parse game time from format "Nov 03 07:00PM ET" to datetime object
    """
    if pd.isna(time_str) or time_str == '':
        return None

    try:
        # Remove the " ET" suffix
        time_str_clean = time_str.replace(' ET', '').strip()

        # Parse the datetime (assume current year)
        current_year = now_et.year
        dt = datetime.strptime(f"{current_year} {time_str_clean}", "%Y %b %d %I:%M%p")

        # Localize to Eastern Time
        dt_et = et.localize(dt)

        return dt_et
    except Exception as e:
        print(f"Warning: Could not parse time '{time_str}': {e}")
        return None

# Parse game times
df['parsed_time'] = df['Game Time'].apply(parse_game_time)

# Filter: Keep games that:
# 1. Have no game time (missing odds data - keep these for reference)
# 2. Have game time in the future
# 3. Started within last 15 minutes (grace period to avoid removing games that just started)

buffer_minutes = 15
cutoff_time = now_et - timedelta(minutes=buffer_minutes)

def should_keep_row(row):
    """Determine if a row should be kept"""
    # Keep rows with no game time (missing odds data)
    if pd.isna(row['parsed_time']):
        return True

    # Keep if game hasn't started yet or started within buffer period
    return row['parsed_time'] >= cutoff_time


def capture_game_snapshot(games_to_remove_df):
    """
    Capture opening and closing data for games being removed.

    This saves all relevant data to game_snapshots.csv before games are filtered out.
    This data is used by grade_bets.py for grading completed games.
    """
    if games_to_remove_df.empty:
        return

    # Define column mapping from CBB_Output.csv to game_snapshots.csv
    snapshot_data = []

    for _, row in games_to_remove_df.iterrows():
        # Parse game date from Game Time
        game_time = row.get('Game Time', '')
        try:
            # Extract date from "Nov 03 07:00PM ET" format
            time_clean = game_time.replace(' ET', '').strip() if pd.notna(game_time) else ''
            game_date = datetime.strptime(f"{now_et.year} {time_clean}", "%Y %b %d %I:%M%p").strftime('%Y-%m-%d') if time_clean else ''
        except:
            game_date = now_et.strftime('%Y-%m-%d')

        snapshot = {
            # Game identifiers
            'game': row.get('Game'),
            'team': row.get('Team'),
            'game_time': game_time,
            'game_date': game_date,
            'snapshot_time': now_et.strftime('%Y-%m-%d %H:%M:%S'),
            'data_source': 'game_snapshot',

            # Opening data (preserved first-seen values)
            'opening_spread': row.get('Opening Spread'),
            'opening_moneyline': row.get('Opening Moneyline'),
            'opening_total': row.get('Opening Total'),
            'opening_odds_time': row.get('Opening Odds Time'),
            'opening_spread_edge': row.get('Opening Spread Edge'),
            'opening_moneyline_edge': row.get('Opening Moneyline Edge'),
            'opening_over_edge': row.get('Opening Over Edge'),
            'opening_under_edge': row.get('Opening Under Edge'),

            # Closing data (current values at tip-off time)
            'closing_spread': row.get('market_spread'),
            'closing_moneyline': row.get('Current Moneyline'),
            'closing_total': row.get('market_total'),
            'closing_spread_edge': row.get('Edge For Covering Spread'),
            'closing_moneyline_edge': row.get('Moneyline Edge'),
            'closing_over_edge': row.get('Over Total Edge'),
            'closing_under_edge': row.get('Under Total Edge'),

            # Individual model predictions - Spreads
            'spread_kenpom': row.get('spread_kenpom'),
            'spread_barttorvik': row.get('spread_barttorvik'),
            'spread_evanmiya': row.get('spread_evanmiya'),
            'spread_hasla': row.get('spread_hasla'),

            # Individual model predictions - Win probabilities
            'win_prob_kenpom': row.get('win_prob_kenpom'),
            'win_prob_barttorvik': row.get('win_prob_barttorvik'),
            'win_prob_evanmiya': row.get('win_prob_evanmiya'),

            # Individual model predictions - Totals
            'projected_total_kenpom': row.get('projected_total_kenpom'),
            'projected_total_barttorvik': row.get('projected_total_barttorvik'),
            'projected_total_evanmiya': row.get('projected_total_evanmiya'),
            'projected_total_hasla': row.get('projected_total_hasla'),

            # Model outputs (aggregated probabilities)
            'model_spread': row.get('model_spread'),
            'model_total': row.get('model_total'),
            'predicted_outcome': row.get('Predicted Outcome'),
            'spread_cover_probability': row.get('Spread Cover Probability'),
            'moneyline_win_probability': row.get('Moneyline Win Probability'),
            'devigged_probability': row.get('Devigged Probability'),
            'over_cover_probability': row.get('Over Cover Probability'),
            'under_cover_probability': row.get('Under Cover Probability'),

            # Consensus flags
            'spread_consensus_flag': row.get('spread_consensus_flag'),
            'moneyline_consensus_flag': row.get('moneyline_consensus_flag'),
            'over_consensus_flag': row.get('over_consensus_flag'),
            'under_consensus_flag': row.get('under_consensus_flag'),
        }
        snapshot_data.append(snapshot)

    # Create DataFrame
    snapshot_df = pd.DataFrame(snapshot_data)

    # Append to existing file or create new one
    if os.path.exists(game_snapshots_file):
        existing_df = pd.read_csv(game_snapshots_file)

        # Avoid duplicates by checking (game, team, game_date)
        existing_keys = set(zip(existing_df['game'], existing_df['team'], existing_df['game_date']))
        new_rows = []
        for _, row in snapshot_df.iterrows():
            key = (row['game'], row['team'], row['game_date'])
            if key not in existing_keys:
                new_rows.append(row)

        if new_rows:
            new_df = pd.DataFrame(new_rows)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df.to_csv(game_snapshots_file, index=False)
            print(f"  - Captured {len(new_rows)} new game snapshots to {game_snapshots_file}")
        else:
            print(f"  - All removed games already captured in {game_snapshots_file}")
    else:
        snapshot_df.to_csv(game_snapshots_file, index=False)
        print(f"  - Created {game_snapshots_file} with {len(snapshot_df)} game snapshots")


df['keep'] = df.apply(should_keep_row, axis=1)

# Capture snapshots for games being removed BEFORE filtering
games_to_remove = df[~df['keep']]
if len(games_to_remove) > 0:
    print(f"\nCapturing game snapshots before removal...")
    capture_game_snapshot(games_to_remove)

# Count games being removed
games_removed = len(df[~df['keep']])
games_kept = len(df[df['keep']])

print(f"\nFiltering games that started before {cutoff_time.strftime('%b %d %I:%M%p ET')}:")
print(f"  - Games removed: {games_removed} rows")
print(f"  - Games kept: {games_kept} rows")

# Show sample of removed games
if games_removed > 0:
    removed_games = df[~df['keep']][['Game', 'Game Time']].drop_duplicates('Game').head(5)
    print(f"\nSample of removed games:")
    for _, game in removed_games.iterrows():
        print(f"  - {game['Game']} ({game['Game Time']})")

# Filter the dataframe
df_filtered = df[df['keep']].copy()

# Drop the helper columns
df_filtered = df_filtered.drop(columns=['parsed_time', 'keep'])

# Save back to file
df_filtered.to_csv(output_file, index=False)

print(f"\nUpdated {output_file}")
print(f"Final row count: {len(df_filtered)}")

# Exit with appropriate code
if games_removed > 0:
    print(f"\n✓ Filtered out {games_removed} rows for games that have started")
else:
    print(f"\n✓ No games to filter (all games are upcoming)")

sys.exit(0)
