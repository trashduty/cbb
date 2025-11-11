# /// script
# dependencies = [
#   "pandas",
#   "pytz"
# ]
# ///
"""
Track College Basketball games that meet specific criteria for testing and analysis.

This script:
1. Reads from CBB_Output.csv
2. Filters games with high edge values and consensus flags
3. Appends qualifying games to master CSV files
4. Prevents duplicate entries
5. Maintains tracking summary statistics
"""

import pandas as pd
from datetime import datetime
import pytz
import os
import sys

# Define file paths
script_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(script_dir, 'CBB_Output.csv')
spread_output = os.path.join(script_dir, 'master_spread_games.csv')
total_output = os.path.join(script_dir, 'master_total_games.csv')
summary_file = os.path.join(script_dir, 'tracking_summary.csv')

# Thresholds
EDGE_THRESHOLD = 0.03

def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"[{timestamp}] {message}")

def load_input_data():
    """Load and validate input CSV"""
    log(f"Reading input file: {input_file}")
    
    if not os.path.exists(input_file):
        log(f"ERROR: Input file not found: {input_file}")
        sys.exit(1)
    
    df = pd.read_csv(input_file)
    log(f"Loaded {len(df)} rows from input file")
    
    # Validate required columns
    required_cols = [
        'Game Time', 'Team', 'market_spread', 'model_spread', 
        'Predicted Outcome', 'Edge For Covering Spread', 'spread_consensus_flag',
        'market_total', 'model_total', 'Over Total Edge', 'Under Total Edge',
        'over_consensus_flag', 'under_consensus_flag'
    ]
    
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        log(f"ERROR: Missing required columns: {missing_cols}")
        sys.exit(1)
    
    return df

def filter_spread_games(df):
    """Filter games meeting spread criteria"""
    log("Filtering spread games...")
    
    # Filter: Edge For Covering Spread >= 0.03 AND spread_consensus_flag = 1
    spread_games = df[
        (df['Edge For Covering Spread'] >= EDGE_THRESHOLD) & 
        (df['spread_consensus_flag'] == 1)
    ].copy()
    
    # Select required columns
    spread_cols = [
        'Game Time', 'Team', 'market_spread', 'model_spread', 
        'Predicted Outcome', 'Edge For Covering Spread'
    ]
    
    spread_games = spread_games[spread_cols]
    
    log(f"Found {len(spread_games)} qualifying spread games")
    return spread_games

def filter_total_games(df):
    """Filter games meeting total criteria"""
    log("Filtering total games...")
    
    # Filter: (Over Total Edge >= 0.03 AND over_consensus_flag = 1) OR 
    #         (Under Total Edge >= 0.03 AND under_consensus_flag = 1)
    total_games = df[
        ((df['Over Total Edge'] >= EDGE_THRESHOLD) & (df['over_consensus_flag'] == 1)) |
        ((df['Under Total Edge'] >= EDGE_THRESHOLD) & (df['under_consensus_flag'] == 1))
    ].copy()
    
    # Select required columns
    total_cols = [
        'Game Time', 'Team', 'market_total', 'model_total', 
        'Over Total Edge', 'Under Total Edge'
    ]
    
    total_games = total_games[total_cols]
    
    log(f"Found {len(total_games)} qualifying total games")
    return total_games

def load_existing_data(filepath, columns):
    """Load existing master CSV or create new DataFrame"""
    if os.path.exists(filepath):
        log(f"Loading existing data from {filepath}")
        df = pd.read_csv(filepath)
        log(f"Loaded {len(df)} existing rows")
        return df
    else:
        log(f"Creating new file: {filepath}")
        return pd.DataFrame(columns=columns)

def get_game_date(game_time_str):
    """Extract date from game time string for deduplication"""
    try:
        # Parse "Nov 11 04:00PM ET" format
        et = pytz.timezone('US/Eastern')
        current_year = datetime.now(et).year
        
        # Remove " ET" suffix
        time_str_clean = game_time_str.replace(' ET', '').strip()
        
        # Parse date only (ignore time for deduplication)
        dt = datetime.strptime(f"{current_year} {time_str_clean}", "%Y %b %d %I:%M%p")
        return dt.strftime('%Y-%m-%d')
    except:
        return None

def deduplicate_games(new_games, existing_games):
    """Remove games that already exist in master file"""
    if existing_games.empty:
        return new_games
    
    # Add date column for deduplication
    new_games['game_date'] = new_games['Game Time'].apply(get_game_date)
    existing_games['game_date'] = existing_games['Game Time'].apply(get_game_date)
    
    # Create composite key: date + team
    new_games['dedup_key'] = new_games['game_date'] + '_' + new_games['Team']
    existing_games['dedup_key'] = existing_games['game_date'] + '_' + existing_games['Team']
    
    # Filter out duplicates
    before_count = len(new_games)
    new_games = new_games[~new_games['dedup_key'].isin(existing_games['dedup_key'])]
    after_count = len(new_games)
    
    # Drop helper columns
    new_games = new_games.drop(columns=['game_date', 'dedup_key'])
    
    duplicates_removed = before_count - after_count
    if duplicates_removed > 0:
        log(f"Removed {duplicates_removed} duplicate entries")
    
    return new_games

def append_to_master(new_games, filepath, columns):
    """Append new games to master file"""
    if new_games.empty:
        log("No new games to append")
        return 0
    
    # Load existing data
    existing_games = load_existing_data(filepath, columns)
    
    # Remove duplicates
    new_games = deduplicate_games(new_games, existing_games)
    
    if new_games.empty:
        log("All games already exist in master file")
        return 0
    
    # Append and save
    if existing_games.empty:
        updated_games = new_games
    else:
        updated_games = pd.concat([existing_games, new_games], ignore_index=True)
    updated_games.to_csv(filepath, index=False)
    
    log(f"Appended {len(new_games)} new games to {filepath}")
    log(f"Total games in master file: {len(updated_games)}")
    
    return len(new_games)

def update_summary(spread_count, total_count):
    """Update tracking summary with run statistics"""
    log("Updating tracking summary...")
    
    # Load existing summary
    if os.path.exists(summary_file):
        summary = pd.read_csv(summary_file)
    else:
        summary = pd.DataFrame(columns=[
            'run_timestamp', 'spread_games_added', 'total_games_added', 
            'total_spread_games', 'total_total_games'
        ])
    
    # Count current totals
    spread_total = len(pd.read_csv(spread_output)) if os.path.exists(spread_output) else 0
    total_total = len(pd.read_csv(total_output)) if os.path.exists(total_output) else 0
    
    # Add new row
    new_row = pd.DataFrame([{
        'run_timestamp': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'spread_games_added': spread_count,
        'total_games_added': total_count,
        'total_spread_games': spread_total,
        'total_total_games': total_total
    }])
    
    summary = pd.concat([summary, new_row], ignore_index=True)
    summary.to_csv(summary_file, index=False)
    
    log(f"Summary updated: {spread_count} spread, {total_count} total games added")

def main():
    """Main execution function"""
    log("=" * 60)
    log("Starting College Basketball Game Tracker")
    log("=" * 60)
    
    try:
        # Load input data
        df = load_input_data()
        
        # Filter games
        spread_games = filter_spread_games(df)
        total_games = filter_total_games(df)
        
        # Append to master files
        spread_count = append_to_master(
            spread_games, 
            spread_output, 
            spread_games.columns if not spread_games.empty else [
                'Game Time', 'Team', 'market_spread', 'model_spread', 
                'Predicted Outcome', 'Edge For Covering Spread'
            ]
        )
        
        total_count = append_to_master(
            total_games,
            total_output,
            total_games.columns if not total_games.empty else [
                'Game Time', 'Team', 'market_total', 'model_total', 
                'Over Total Edge', 'Under Total Edge'
            ]
        )
        
        # Update summary
        update_summary(spread_count, total_count)
        
        log("=" * 60)
        log("Game tracking completed successfully")
        log(f"New games added: {spread_count} spread, {total_count} total")
        log("=" * 60)
        
        sys.exit(0)
        
    except Exception as e:
        log(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
