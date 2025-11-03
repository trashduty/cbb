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
"""

import pandas as pd
from datetime import datetime, timedelta
import pytz
import os
import sys

# Get current Eastern Time
et = pytz.timezone('US/Eastern')
now_et = datetime.now(et)

# Define the output file path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
output_file = os.path.join(project_root, 'CBB_Output.csv')

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

df['keep'] = df.apply(should_keep_row, axis=1)

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
