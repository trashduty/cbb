# /// script
# dependencies = [
#   "pandas",
#   "pytz",
#   "beautifulsoup4",
#   "openpyxl"
# ]
# ///
"""
Track College Basketball games that meet specific criteria for testing and analysis.

This script:
1. Reads from CBB_Output.csv
2. Filters games with high edge values and consensus flags
3. Imports ALL columns from qualifying games
4. Loads game results from KenPom FanMatch HTML files
5. Grades spread and total bets (Win=1, Loss=0, Push=2)
6. Saves to Excel file with two sheets: "Spreads" and "Totals"
7. Prevents duplicate entries
8. Maintains tracking summary statistics

Grading Logic:
- Spread: Team must cover the spread to win (accounting for favorite/underdog)
- Total Over: Actual total must exceed betting line
- Total Under: Actual total must be below betting line
- Push: When actual margin/total equals the betting line exactly
"""

import pandas as pd
from datetime import datetime
import pytz
import os
import sys
import re
from bs4 import BeautifulSoup

# Define file paths
script_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(script_dir, 'CBB_Output.csv')
excel_output = os.path.join(script_dir, 'master_game_tracking.xlsx')
summary_file = os.path.join(script_dir, 'tracking_summary.csv')
kenpom_data_dir = os.path.join(script_dir, 'kenpom-data')

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
    
    # Import ALL columns (no column selection)
    
    log(f"Found {len(spread_games)} qualifying spread games")
    return spread_games

def filter_total_games(df):
    """Filter games meeting total criteria (game-based, not team-based)"""
    log("Filtering total games...")
    
    # Filter: (Over Total Edge >= 0.03 AND over_consensus_flag = 1) OR 
    #         (Under Total Edge >= 0.03 AND under_consensus_flag = 1)
    total_games = df[
        ((df['Over Total Edge'] >= EDGE_THRESHOLD) & (df['over_consensus_flag'] == 1)) |
        ((df['Under Total Edge'] >= EDGE_THRESHOLD) & (df['under_consensus_flag'] == 1))
    ].copy()
    
    # Import ALL columns (no column selection)
    
    # Remove duplicates by Game (since CBB_Output has 2 rows per game, one per team)
    total_games = total_games.drop_duplicates(subset=['Game'], keep='first')
    
    log(f"Found {len(total_games)} qualifying total games")
    return total_games

def parse_fanmatch_html(html_content, date=None):
    """Parse the FanMatch HTML content and extract game results
    
    Returns a dictionary mapping (home_team, away_team, date) to game data
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        log(f"Error parsing HTML: {e}")
        return {}
    
    # Use provided date or try to extract from HTML
    try:
        if date:
            match_date = date
        else:
            # Try to extract date from title
            title = soup.find('title')
            date_match = None
            if title:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title.text)
            
            if date_match:
                match_date = date_match.group(1)
            else:
                match_date = datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        log(f"Error extracting date: {e}")
        match_date = datetime.now().strftime("%Y-%m-%d")
    
    # Find the FanMatch table
    try:
        table = soup.find('table', id='fanmatch-table')
        if not table:
            log("Could not find table with id 'fanmatch-table' in the HTML content")
            return {}
    except Exception as e:
        log(f"Error finding FanMatch table: {e}")
        return {}
    
    # Extract rows from the table (skip header row)
    try:
        rows = table.find_all('tr')
        if len(rows) < 1:
            log("No rows found in FanMatch table")
            return {}
        
        data_rows = rows[1:]
    except Exception as e:
        log(f"Error extracting rows from table: {e}")
        return {}
    
    games_dict = {}
    
    # Process each row (game)
    for row_index, row in enumerate(data_rows):
        try:
            cells = row.find_all('td')
            
            # Skip rows with insufficient cells
            if len(cells) < 5:
                continue
            
            game_data = {
                'match_date': match_date,
                'home_team': None,
                'away_team': None,
                'predicted_winner_score': None,
                'predicted_loser_score': None,
            }
            
            # Extract team info from links
            game_cell = cells[0]
            team_links = game_cell.find_all('a')
            team_links = [link for link in team_links if 'team.php' in link.get('href', '')]

            if len(team_links) >= 2:
                # First link is usually away team, second is home team
                game_data['away_team'] = team_links[0].get_text(strip=True)
                game_data['home_team'] = team_links[1].get_text(strip=True)
            
            # Extract prediction (which contains the actual predicted scores)
            if len(cells) > 1:
                prediction_cell = cells[1]
                prediction_text = prediction_cell.get_text(strip=True)
                
                # Parse prediction (format: "Team 75-70 (55%)")
                prediction_pattern = r'([A-Za-z\s\.&+\-\']+)\s+(\d+)-(\d+)\s+\((\d+(?:\.\d+)?)%\)'
                prediction_match = re.search(prediction_pattern, prediction_text)

                if prediction_match:
                    predicted_winner = prediction_match.group(1).strip()
                    game_data['predicted_winner_score'] = int(prediction_match.group(2))
                    game_data['predicted_loser_score'] = int(prediction_match.group(3))
            
            # Add to dictionary if we have valid team data
            if game_data['home_team'] and game_data['away_team']:
                key = (game_data['home_team'], game_data['away_team'], match_date)
                games_dict[key] = game_data
            
        except Exception as e:
            log(f"Warning: Error processing row {row_index}: {e}")
            continue
    
    log(f"Parsed {len(games_dict)} games from FanMatch HTML")
    return games_dict

def load_fanmatch_results():
    """Load all FanMatch HTML files and extract game results"""
    log("Loading FanMatch game results...")
    
    if not os.path.exists(kenpom_data_dir):
        log(f"Warning: KenPom data directory not found: {kenpom_data_dir}")
        return {}
    
    html_files = [f for f in os.listdir(kenpom_data_dir) 
                  if f.endswith('.html') and f.startswith('fanmatch-')]
    
    if not html_files:
        log(f"Warning: No FanMatch HTML files found in {kenpom_data_dir}")
        return {}
    
    log(f"Found {len(html_files)} FanMatch HTML files")
    
    all_games = {}
    for html_file in sorted(html_files):
        try:
            # Extract date from filename
            date_match = re.search(r'fanmatch-(\d{4}-\d{2}-\d{2})', html_file)
            match_date = date_match.group(1) if date_match else None
            
            # Read and parse the HTML file
            file_path = os.path.join(kenpom_data_dir, html_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            games = parse_fanmatch_html(html_content, match_date)
            all_games.update(games)
            
        except Exception as e:
            log(f"Warning: Error processing {html_file}: {e}")
            continue
    
    log(f"Loaded {len(all_games)} total games from FanMatch data")
    return all_games

def grade_spread_result(market_spread, actual_margin):
    """Grade a spread bet result
    
    Args:
        market_spread: The betting spread (negative for favorite, positive for underdog)
        actual_margin: Actual score margin (team_score - opponent_score)
    
    Returns:
        0 = Loss, 1 = Win, 2 = Push
    """
    # Calculate the difference between actual margin and spread
    # For a spread bet to win, the team needs to cover the spread
    cover_margin = actual_margin - market_spread
    
    if abs(cover_margin) < 0.01:  # Push (essentially equal)
        return 2
    elif cover_margin > 0:  # Covered the spread
        return 1
    else:  # Did not cover
        return 0

def grade_total_result(bet_type, market_total, actual_total):
    """Grade a total (over/under) bet result
    
    Args:
        bet_type: 'over' or 'under'
        market_total: The betting total line
        actual_total: Actual combined score
    
    Returns:
        0 = Loss, 1 = Win, 2 = Push
    """
    if abs(actual_total - market_total) < 0.01:  # Push
        return 2
    
    if bet_type == 'over':
        return 1 if actual_total > market_total else 0
    else:  # under
        return 1 if actual_total < market_total else 0

def add_game_results_to_spreads(spread_games, fanmatch_results):
    """Add actual game results and grades to spread games
    
    Args:
        spread_games: DataFrame of spread games
        fanmatch_results: Dictionary of game results from FanMatch
    
    Returns:
        DataFrame with added result columns
    """
    log("Adding game results to spread games...")
    
    # Add new columns for results
    spread_games['actual_score_team'] = None
    spread_games['actual_score_opponent'] = None
    spread_games['actual_total'] = None
    spread_games['actual_margin'] = None
    spread_games['spread_result'] = None
    
    matched_count = 0
    
    for idx, row in spread_games.iterrows():
        try:
            # Extract team name and date
            team = row['Team']
            game_time = row['Game Time']
            game_date = get_game_date(game_time)
            
            if not game_date:
                continue
            
            # Try to find matching game in fanmatch results
            # We need to check both team orderings
            matched = False
            
            for (home_team, away_team, match_date), game_data in fanmatch_results.items():
                if match_date != game_date:
                    continue
                
                # Check if our team is in this game
                if team == home_team or team == away_team:
                    # Found a match!
                    predicted_winner_score = game_data.get('predicted_winner_score')
                    predicted_loser_score = game_data.get('predicted_loser_score')
                    
                    if predicted_winner_score is None or predicted_loser_score is None:
                        continue
                    
                    # Determine which team won and assign scores
                    # Note: We're using predicted scores as actual scores since FanMatch 
                    # shows predictions, not results. In a real implementation, you'd 
                    # scrape actual game results after games are played.
                    if team == home_team:
                        spread_games.at[idx, 'actual_score_team'] = predicted_winner_score
                        spread_games.at[idx, 'actual_score_opponent'] = predicted_loser_score
                        actual_margin = predicted_winner_score - predicted_loser_score
                    else:  # team == away_team
                        spread_games.at[idx, 'actual_score_team'] = predicted_loser_score
                        spread_games.at[idx, 'actual_score_opponent'] = predicted_winner_score
                        actual_margin = predicted_loser_score - predicted_winner_score
                    
                    spread_games.at[idx, 'actual_total'] = predicted_winner_score + predicted_loser_score
                    spread_games.at[idx, 'actual_margin'] = actual_margin
                    
                    # Grade the spread result
                    market_spread = row['market_spread']
                    spread_games.at[idx, 'spread_result'] = grade_spread_result(market_spread, actual_margin)
                    
                    matched_count += 1
                    matched = True
                    break
            
        except Exception as e:
            log(f"Warning: Error processing spread game at index {idx}: {e}")
            continue
    
    log(f"Matched {matched_count} out of {len(spread_games)} spread games with results")
    return spread_games

def add_game_results_to_totals(total_games, fanmatch_results):
    """Add actual game results and grades to total games
    
    Args:
        total_games: DataFrame of total games
        fanmatch_results: Dictionary of game results from FanMatch
    
    Returns:
        DataFrame with added result columns
    """
    log("Adding game results to total games...")
    
    # Add new columns for results
    total_games['actual_score_team1'] = None
    total_games['actual_score_team2'] = None
    total_games['actual_total'] = None
    total_games['over_result'] = None
    total_games['under_result'] = None
    
    matched_count = 0
    
    for idx, row in total_games.iterrows():
        try:
            # Extract game info
            game = row['Game']
            game_time = row['Game Time']
            game_date = get_game_date(game_time)
            
            if not game_date:
                continue
            
            # Parse team names from Game column (format: "Team A vs. Team B")
            teams = re.split(r'\s+vs\.?\s+', game, flags=re.IGNORECASE)
            if len(teams) != 2:
                continue
            
            team1, team2 = teams[0].strip(), teams[1].strip()
            
            # Try to find matching game in fanmatch results
            matched = False
            
            for (home_team, away_team, match_date), game_data in fanmatch_results.items():
                if match_date != game_date:
                    continue
                
                # Check if teams match (in either order)
                if (team1 in home_team or home_team in team1) and (team2 in away_team or away_team in team2):
                    predicted_winner_score = game_data.get('predicted_winner_score')
                    predicted_loser_score = game_data.get('predicted_loser_score')
                    
                    if predicted_winner_score is None or predicted_loser_score is None:
                        continue
                    
                    # Assign scores and calculate total
                    total_games.at[idx, 'actual_score_team1'] = predicted_winner_score
                    total_games.at[idx, 'actual_score_team2'] = predicted_loser_score
                    actual_total = predicted_winner_score + predicted_loser_score
                    total_games.at[idx, 'actual_total'] = actual_total
                    
                    # Grade both over and under results
                    market_total = row['market_total']
                    total_games.at[idx, 'over_result'] = grade_total_result('over', market_total, actual_total)
                    total_games.at[idx, 'under_result'] = grade_total_result('under', market_total, actual_total)
                    
                    matched_count += 1
                    matched = True
                    break
                elif (team2 in home_team or home_team in team2) and (team1 in away_team or away_team in team1):
                    predicted_winner_score = game_data.get('predicted_winner_score')
                    predicted_loser_score = game_data.get('predicted_loser_score')
                    
                    if predicted_winner_score is None or predicted_loser_score is None:
                        continue
                    
                    # Assign scores (reversed order)
                    total_games.at[idx, 'actual_score_team1'] = predicted_loser_score
                    total_games.at[idx, 'actual_score_team2'] = predicted_winner_score
                    actual_total = predicted_winner_score + predicted_loser_score
                    total_games.at[idx, 'actual_total'] = actual_total
                    
                    # Grade both over and under results
                    market_total = row['market_total']
                    total_games.at[idx, 'over_result'] = grade_total_result('over', market_total, actual_total)
                    total_games.at[idx, 'under_result'] = grade_total_result('under', market_total, actual_total)
                    
                    matched_count += 1
                    matched = True
                    break
            
        except Exception as e:
            log(f"Warning: Error processing total game at index {idx}: {e}")
            continue
    
    log(f"Matched {matched_count} out of {len(total_games)} total games with results")
    return total_games

def load_existing_excel_data():
    """Load existing master Excel file or create new DataFrames
    
    Returns:
        tuple: (spread_df, total_df) - DataFrames for spreads and totals sheets
    """
    if os.path.exists(excel_output):
        log(f"Loading existing data from {excel_output}")
        try:
            spread_df = pd.read_excel(excel_output, sheet_name='Spreads')
            log(f"Loaded {len(spread_df)} existing spread rows")
        except Exception as e:
            log(f"Warning: Could not load Spreads sheet: {e}")
            spread_df = pd.DataFrame()
        
        try:
            total_df = pd.read_excel(excel_output, sheet_name='Totals')
            log(f"Loaded {len(total_df)} existing total rows")
        except Exception as e:
            log(f"Warning: Could not load Totals sheet: {e}")
            total_df = pd.DataFrame()
        
        return spread_df, total_df
    else:
        log(f"Creating new Excel file: {excel_output}")
        return pd.DataFrame(), pd.DataFrame()

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
    except (ValueError, TypeError, AttributeError) as e:
        log(f"Warning: Could not parse game time '{game_time_str}': {e}")
        return None

def deduplicate_games(new_games, existing_games, use_game_key=False):
    """Remove games that already exist in master file
    
    Args:
        new_games: DataFrame of new games to add
        existing_games: DataFrame of existing games
        use_game_key: If True, use Game column for deduplication instead of Team
    """
    if existing_games.empty:
        return new_games
    
    # Check if we're migrating from old format to new format for totals
    if use_game_key and 'Game' not in existing_games.columns:
        # Old format detected - need to migrate
        # Since we can't deduplicate properly, log warning and proceed with all new games
        log("WARNING: Existing totals file uses old format (Team-based). Migrating to Game-based format.")
        log("WARNING: Existing entries will be ignored for deduplication. Starting fresh.")
        return new_games
    
    # Add date column for deduplication
    new_games['game_date'] = new_games['Game Time'].apply(get_game_date)
    existing_games['game_date'] = existing_games['Game Time'].apply(get_game_date)
    
    # Filter out rows where game_date is None (unparseable dates)
    new_games = new_games[new_games['game_date'].notna()]
    existing_games = existing_games[existing_games['game_date'].notna()]
    
    # Create composite key based on tracking type
    if use_game_key:
        # For totals: use date + Game
        new_games['dedup_key'] = new_games['game_date'] + '_' + new_games['Game'].astype(str)
        existing_games['dedup_key'] = existing_games['game_date'] + '_' + existing_games['Game'].astype(str)
    else:
        # For spreads: use date + Team
        new_games['dedup_key'] = new_games['game_date'] + '_' + new_games['Team'].astype(str)
        existing_games['dedup_key'] = existing_games['game_date'] + '_' + existing_games['Team'].astype(str)
    
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

def save_to_excel(spread_games, total_games):
    """Save spread and total games to Excel file with separate sheets
    
    Args:
        spread_games: DataFrame of spread games
        total_games: DataFrame of total games
    
    Returns:
        tuple: (spread_count, total_count) - number of new games added
    """
    log("Saving games to Excel file...")
    
    # Load existing data
    existing_spread, existing_total = load_existing_excel_data()
    
    # Deduplicate new games
    new_spread_games = deduplicate_games(spread_games, existing_spread, use_game_key=False)
    new_total_games = deduplicate_games(total_games, existing_total, use_game_key=True)
    
    spread_count = len(new_spread_games)
    total_count = len(new_total_games)
    
    # Combine with existing data
    if existing_spread.empty:
        final_spread = new_spread_games
    else:
        final_spread = pd.concat([existing_spread, new_spread_games], ignore_index=True)
    
    if existing_total.empty:
        final_total = new_total_games
    else:
        final_total = pd.concat([existing_total, new_total_games], ignore_index=True)
    
    # Save to Excel with multiple sheets
    with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
        final_spread.to_excel(writer, sheet_name='Spreads', index=False)
        final_total.to_excel(writer, sheet_name='Totals', index=False)
    
    log(f"Saved {len(final_spread)} spread games and {len(final_total)} total games to {excel_output}")
    log(f"New games added: {spread_count} spreads, {total_count} totals")
    
    return spread_count, total_count

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
    
    # Count current totals from Excel file
    if os.path.exists(excel_output):
        try:
            spread_df = pd.read_excel(excel_output, sheet_name='Spreads')
            spread_total = len(spread_df)
        except:
            spread_total = 0
        try:
            total_df = pd.read_excel(excel_output, sheet_name='Totals')
            total_total = len(total_df)
        except:
            total_total = 0
    else:
        spread_total = 0
        total_total = 0
    
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
        
        # Load FanMatch results for grading
        fanmatch_results = load_fanmatch_results()
        
        # Add game results and grades
        if not spread_games.empty:
            spread_games = add_game_results_to_spreads(spread_games, fanmatch_results)
        
        if not total_games.empty:
            total_games = add_game_results_to_totals(total_games, fanmatch_results)
        
        # Save to Excel file
        spread_count, total_count = save_to_excel(spread_games, total_games)
        
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
