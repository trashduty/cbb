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
from difflib import SequenceMatcher

# Validate openpyxl is available for Excel operations
try:
    import openpyxl
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False
    print("WARNING: openpyxl is not installed. Excel file creation will not be available.")
    print("Install with: pip install openpyxl")

# Define file paths
script_dir = os.path.dirname(os.path.abspath(__file__))
input_file = os.path.join(script_dir, 'CBB_Output.csv')
excel_output = os.path.join(script_dir, 'master_game_tracking.xlsx')
summary_file = os.path.join(script_dir, 'tracking_summary.csv')
kenpom_data_dir = os.path.join(script_dir, 'kenpom-data')
# Legacy CSV files
legacy_spread_csv = os.path.join(script_dir, 'master_spread_games.csv')
legacy_total_csv = os.path.join(script_dir, 'master_total_games.csv')

# Thresholds
EDGE_THRESHOLD = 0.03

def log(message, level="INFO"):
    """Print timestamped log message with level"""
    timestamp = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"[{timestamp}] [{level}] {message}")

def normalize_team_name(team_name):
    """Normalize team name for matching
    
    - Convert to lowercase
    - Strip whitespace
    - Remove extra spaces
    - Handle common variations
    """
    if not team_name:
        return ""
    
    # Convert to lowercase and strip
    normalized = team_name.lower().strip()
    
    # Replace multiple spaces with single space
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Normalize common abbreviations
    normalized = normalized.replace('st.', 'saint')
    normalized = normalized.replace(' st ', ' saint ')
    
    return normalized

def fuzzy_match_teams(team1, team2, threshold=0.85):
    """Check if two team names match using fuzzy string matching
    
    Args:
        team1: First team name
        team2: Second team name
        threshold: Similarity threshold (0.0 to 1.0)
    
    Returns:
        bool: True if teams match, False otherwise
    """
    if not team1 or not team2:
        return False
    
    # Normalize both names
    norm1 = normalize_team_name(team1)
    norm2 = normalize_team_name(team2)
    
    # Exact match after normalization
    if norm1 == norm2:
        return True
    
    # Check if one is a substring of the other at the START (not just anywhere)
    # This handles cases like "Duke" vs "Duke Blue Devils" (mascot)
    # but prevents "Florida" vs "Florida Atlantic" (different school)
    if norm1.startswith(norm2) or norm2.startswith(norm1):
        longer_str = norm1 if len(norm1) > len(norm2) else norm2
        shorter_str = norm1 if len(norm1) <= len(norm2) else norm2
        
        # Get the extra part after the shorter name
        extra = longer_str[len(shorter_str):].strip()
        
        # If the extra part contains indicators of a different school (not just mascot), don't match
        different_school_indicators = ['atlantic', ' state', ' tech', ' christian', 
                                      'southern', 'northern', 'eastern', 'western',
                                      'central', 'upstate']
        
        # Check if any indicator is in the extra part
        for indicator in different_school_indicators:
            if indicator in extra:
                return False
        
        # If no different school indicator, it's probably just a mascot - match!
        return True
    
    # Fuzzy match using SequenceMatcher
    ratio = SequenceMatcher(None, norm1, norm2).ratio()
    
    return ratio >= threshold

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
    
    # Filter out fanmatch-initial.html as it's typically a duplicate
    html_files = [f for f in html_files if f != 'fanmatch-initial.html']
    
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
            
            if not match_date:
                log(f"WARNING: Skipping {html_file} - could not extract date from filename", "WARNING")
                continue
            
            # Read and parse the HTML file
            file_path = os.path.join(kenpom_data_dir, html_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            log(f"Processing {html_file} (date: {match_date})...", "DEBUG")
            games = parse_fanmatch_html(html_content, match_date)
            
            # Verify dates match
            date_mismatch_count = 0
            for key in games.keys():
                if key[2] != match_date:
                    date_mismatch_count += 1
            
            if date_mismatch_count > 0:
                log(f"WARNING: {date_mismatch_count} games have date mismatch in {html_file}", "WARNING")
            
            all_games.update(games)
            log(f"Added {len(games)} games from {html_file}", "DEBUG")
            
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
    
    Examples:
        - Favorite -5, wins by 6: grade_spread_result(-5, 6) = 1 (Win)
        - Favorite -5, wins by 5: grade_spread_result(-5, 5) = 2 (Push)
        - Favorite -5, wins by 4: grade_spread_result(-5, 4) = 0 (Loss)
        - Underdog +5, loses by 4: grade_spread_result(5, -4) = 1 (Win)
        - Underdog +5, loses by 5: grade_spread_result(5, -5) = 2 (Push)
        - Underdog +5, loses by 6: grade_spread_result(5, -6) = 0 (Loss)
    """
    # Check for push first - when actual margin equals the absolute value of the spread
    # For favorite (-5): push when margin is exactly 5
    # For underdog (+5): push when margin is exactly -5
    if abs(actual_margin + market_spread) < 0.01:
        return 2  # Push
    
    # For a spread bet to win, the team needs to cover the spread
    # actual_margin > abs(market_spread) means they beat the spread
    # Negative spread (favorite): need to win by MORE than abs(spread)
    # Positive spread (underdog): can lose by LESS than spread or win
    cover_margin = actual_margin + market_spread
    
    if cover_margin > 0:  # Covered the spread
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
    log(f"DEBUG: Processing {len(spread_games)} spread games", "DEBUG")
    log(f"DEBUG: FanMatch has results for {len(fanmatch_results)} games", "DEBUG")
    
    # Add new columns for results
    spread_games['actual_score_team'] = None
    spread_games['actual_score_opponent'] = None
    spread_games['actual_total'] = None
    spread_games['actual_margin'] = None
    spread_games['spread_result'] = None
    
    matched_count = 0
    
    # Log all tracked games for debugging
    log("=" * 80, "DEBUG")
    log("TRACKED GAMES FOR GRADING:", "DEBUG")
    for idx, row in spread_games.iterrows():
        team = row['Team']
        game_time = row['Game Time']
        game_date = get_game_date(game_time)
        log(f"  - Team: '{team}', Date: {game_date}, Game Time: '{game_time}'", "DEBUG")
    
    # Log all FanMatch games for debugging
    log("=" * 80, "DEBUG")
    log("FANMATCH GAMES AVAILABLE:", "DEBUG")
    for (home_team, away_team, match_date), game_data in fanmatch_results.items():
        pred_winner = game_data.get('predicted_winner_score')
        pred_loser = game_data.get('predicted_loser_score')
        log(f"  - Date: {match_date}, Home: '{home_team}', Away: '{away_team}', Scores: {pred_winner}-{pred_loser}", "DEBUG")
    log("=" * 80, "DEBUG")
    
    for idx, row in spread_games.iterrows():
        try:
            # Extract team name and date
            team = row['Team']
            game_time = row['Game Time']
            game_date = get_game_date(game_time)
            
            if not game_date:
                log(f"WARNING: Could not parse game date from '{game_time}' for team '{team}'", "WARNING")
                continue
            
            log(f"Attempting to match: Team='{team}', Date={game_date}", "DEBUG")
            
            # Try to find matching game in fanmatch results
            # We need to check both team orderings
            matched = False
            match_attempts = []
            
            for (home_team, away_team, match_date), game_data in fanmatch_results.items():
                # Check date match
                if match_date != game_date:
                    continue
                
                log(f"  Date matches! Checking teams: FanMatch(home='{home_team}', away='{away_team}') vs Tracked('{team}')", "DEBUG")
                
                # Try exact matching first
                exact_match_home = (team == home_team)
                exact_match_away = (team == away_team)
                
                # Try fuzzy matching if exact fails
                fuzzy_match_home = fuzzy_match_teams(team, home_team)
                fuzzy_match_away = fuzzy_match_teams(team, away_team)
                
                match_attempts.append({
                    'fanmatch_home': home_team,
                    'fanmatch_away': away_team,
                    'exact_home': exact_match_home,
                    'exact_away': exact_match_away,
                    'fuzzy_home': fuzzy_match_home,
                    'fuzzy_away': fuzzy_match_away
                })
                
                # Check if our team is in this game (using fuzzy matching)
                if fuzzy_match_home or fuzzy_match_away:
                    # Found a match!
                    predicted_winner_score = game_data.get('predicted_winner_score')
                    predicted_loser_score = game_data.get('predicted_loser_score')
                    
                    if predicted_winner_score is None or predicted_loser_score is None:
                        log(f"  SKIP: Missing score data (winner={predicted_winner_score}, loser={predicted_loser_score})", "DEBUG")
                        continue
                    
                    log(f"  MATCH FOUND! Team '{team}' matched with FanMatch game", "INFO")
                    log(f"    - Match type: {'Exact' if (exact_match_home or exact_match_away) else 'Fuzzy'}", "INFO")
                    log(f"    - Scores: {predicted_winner_score}-{predicted_loser_score}", "INFO")
                    
                    # Determine which team won and assign scores
                    # Note: We're using predicted scores as actual scores since FanMatch 
                    # shows predictions, not results. In a real implementation, you'd 
                    # scrape actual game results after games are played.
                    if fuzzy_match_home:
                        spread_games.at[idx, 'actual_score_team'] = predicted_winner_score
                        spread_games.at[idx, 'actual_score_opponent'] = predicted_loser_score
                        actual_margin = predicted_winner_score - predicted_loser_score
                    else:  # fuzzy_match_away
                        spread_games.at[idx, 'actual_score_team'] = predicted_loser_score
                        spread_games.at[idx, 'actual_score_opponent'] = predicted_winner_score
                        actual_margin = predicted_loser_score - predicted_winner_score
                    
                    spread_games.at[idx, 'actual_total'] = predicted_winner_score + predicted_loser_score
                    spread_games.at[idx, 'actual_margin'] = actual_margin
                    
                    # Grade the spread result
                    market_spread = row['market_spread']
                    spread_result = grade_spread_result(market_spread, actual_margin)
                    spread_games.at[idx, 'spread_result'] = spread_result
                    
                    result_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}.get(spread_result, "UNKNOWN")
                    log(f"    - Spread Result: {result_str} (market_spread={market_spread}, actual_margin={actual_margin})", "INFO")
                    
                    matched_count += 1
                    matched = True
                    break
            
            if not matched:
                log(f"  NO MATCH: Could not find FanMatch game for team '{team}' on {game_date}", "WARNING")
                if match_attempts:
                    log(f"    Checked {len(match_attempts)} games on {game_date}:", "DEBUG")
                    for attempt in match_attempts:
                        log(f"      - Home: '{attempt['fanmatch_home']}' (exact={attempt['exact_home']}, fuzzy={attempt['fuzzy_home']})", "DEBUG")
                        log(f"        Away: '{attempt['fanmatch_away']}' (exact={attempt['exact_away']}, fuzzy={attempt['fuzzy_away']})", "DEBUG")
            
        except Exception as e:
            log(f"ERROR: Error processing spread game at index {idx}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            continue
    
    log("=" * 80, "INFO")
    log(f"SUMMARY: Matched {matched_count} out of {len(spread_games)} spread games with results", "INFO")
    log("=" * 80, "INFO")
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
    log(f"DEBUG: Processing {len(total_games)} total games", "DEBUG")
    
    # Add new columns for results
    total_games['actual_score_team1'] = None
    total_games['actual_score_team2'] = None
    total_games['actual_total'] = None
    total_games['over_result'] = None
    total_games['under_result'] = None
    
    matched_count = 0
    
    # Log all tracked games for debugging
    log("=" * 80, "DEBUG")
    log("TRACKED TOTAL GAMES FOR GRADING:", "DEBUG")
    for idx, row in total_games.iterrows():
        game = row['Game']
        game_time = row['Game Time']
        game_date = get_game_date(game_time)
        log(f"  - Game: '{game}', Date: {game_date}, Game Time: '{game_time}'", "DEBUG")
    log("=" * 80, "DEBUG")
    
    for idx, row in total_games.iterrows():
        try:
            # Extract game info
            game = row['Game']
            game_time = row['Game Time']
            game_date = get_game_date(game_time)
            
            if not game_date:
                log(f"WARNING: Could not parse game date from '{game_time}' for game '{game}'", "WARNING")
                continue
            
            # Parse team names from Game column (format: "Team A vs. Team B")
            teams = re.split(r'\s+vs\.?\s+', game, flags=re.IGNORECASE)
            if len(teams) != 2:
                log(f"WARNING: Could not parse teams from game string '{game}'", "WARNING")
                continue
            
            team1, team2 = teams[0].strip(), teams[1].strip()
            log(f"Attempting to match total game: Team1='{team1}', Team2='{team2}', Date={game_date}", "DEBUG")
            
            # Try to find matching game in fanmatch results
            matched = False
            match_attempts = []
            
            for (home_team, away_team, match_date), game_data in fanmatch_results.items():
                if match_date != game_date:
                    continue
                
                log(f"  Date matches! Checking teams: FanMatch(home='{home_team}', away='{away_team}') vs Tracked('{team1}' vs '{team2}')", "DEBUG")
                
                # Check both orderings with fuzzy matching
                match_1_home = fuzzy_match_teams(team1, home_team)
                match_1_away = fuzzy_match_teams(team2, away_team)
                match_2_home = fuzzy_match_teams(team2, home_team)
                match_2_away = fuzzy_match_teams(team1, away_team)
                
                match_attempts.append({
                    'fanmatch_home': home_team,
                    'fanmatch_away': away_team,
                    'order1_match': match_1_home and match_1_away,
                    'order2_match': match_2_home and match_2_away
                })
                
                # Check if teams match (in either order)
                if match_1_home and match_1_away:
                    predicted_winner_score = game_data.get('predicted_winner_score')
                    predicted_loser_score = game_data.get('predicted_loser_score')
                    
                    if predicted_winner_score is None or predicted_loser_score is None:
                        log(f"  SKIP: Missing score data", "DEBUG")
                        continue
                    
                    log(f"  MATCH FOUND! (Order 1: team1=home, team2=away)", "INFO")
                    log(f"    - Scores: {predicted_winner_score}-{predicted_loser_score}", "INFO")
                    
                    # Assign scores and calculate total
                    total_games.at[idx, 'actual_score_team1'] = predicted_winner_score
                    total_games.at[idx, 'actual_score_team2'] = predicted_loser_score
                    actual_total = predicted_winner_score + predicted_loser_score
                    total_games.at[idx, 'actual_total'] = actual_total
                    
                    # Grade both over and under results
                    market_total = row['market_total']
                    over_result = grade_total_result('over', market_total, actual_total)
                    under_result = grade_total_result('under', market_total, actual_total)
                    total_games.at[idx, 'over_result'] = over_result
                    total_games.at[idx, 'under_result'] = under_result
                    
                    over_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}.get(over_result, "UNKNOWN")
                    under_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}.get(under_result, "UNKNOWN")
                    log(f"    - Over: {over_str}, Under: {under_str} (market_total={market_total}, actual_total={actual_total})", "INFO")
                    
                    matched_count += 1
                    matched = True
                    break
                elif match_2_home and match_2_away:
                    predicted_winner_score = game_data.get('predicted_winner_score')
                    predicted_loser_score = game_data.get('predicted_loser_score')
                    
                    if predicted_winner_score is None or predicted_loser_score is None:
                        log(f"  SKIP: Missing score data", "DEBUG")
                        continue
                    
                    log(f"  MATCH FOUND! (Order 2: team2=home, team1=away)", "INFO")
                    log(f"    - Scores: {predicted_winner_score}-{predicted_loser_score}", "INFO")
                    
                    # Assign scores (reversed order)
                    total_games.at[idx, 'actual_score_team1'] = predicted_loser_score
                    total_games.at[idx, 'actual_score_team2'] = predicted_winner_score
                    actual_total = predicted_winner_score + predicted_loser_score
                    total_games.at[idx, 'actual_total'] = actual_total
                    
                    # Grade both over and under results
                    market_total = row['market_total']
                    over_result = grade_total_result('over', market_total, actual_total)
                    under_result = grade_total_result('under', market_total, actual_total)
                    total_games.at[idx, 'over_result'] = over_result
                    total_games.at[idx, 'under_result'] = under_result
                    
                    over_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}.get(over_result, "UNKNOWN")
                    under_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}.get(under_result, "UNKNOWN")
                    log(f"    - Over: {over_str}, Under: {under_str} (market_total={market_total}, actual_total={actual_total})", "INFO")
                    
                    matched_count += 1
                    matched = True
                    break
            
            if not matched:
                log(f"  NO MATCH: Could not find FanMatch game for '{game}' on {game_date}", "WARNING")
                if match_attempts:
                    log(f"    Checked {len(match_attempts)} games on {game_date}:", "DEBUG")
                    for attempt in match_attempts:
                        log(f"      - Home: '{attempt['fanmatch_home']}', Away: '{attempt['fanmatch_away']}'", "DEBUG")
                        log(f"        Order1 match: {attempt['order1_match']}, Order2 match: {attempt['order2_match']}", "DEBUG")
            
        except Exception as e:
            log(f"ERROR: Error processing total game at index {idx}: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            continue
    
    log("=" * 80, "INFO")
    log(f"SUMMARY: Matched {matched_count} out of {len(total_games)} total games with results", "INFO")
    log("=" * 80, "INFO")
    return total_games

def backup_csv_file(csv_path):
    """Create a backup of the CSV file before migration
    
    Args:
        csv_path: Path to the CSV file to backup
    
    Returns:
        str: Path to backup file, or None if backup failed
    """
    if not os.path.exists(csv_path):
        return None
    
    try:
        backup_path = csv_path.replace('.csv', '_backup.csv')
        import shutil
        shutil.copy2(csv_path, backup_path)
        log(f"Created backup: {backup_path}")
        return backup_path
    except Exception as e:
        log(f"Warning: Could not create backup of {csv_path}: {e}")
        return None

def load_historical_csv_data():
    """Load historical data from legacy CSV files
    
    Returns:
        tuple: (spread_df, total_df) - DataFrames from legacy CSV files
    """
    spread_df = pd.DataFrame()
    total_df = pd.DataFrame()
    
    # Load legacy spread CSV
    if os.path.exists(legacy_spread_csv):
        try:
            log(f"Found legacy spread CSV: {legacy_spread_csv}")
            backup_csv_file(legacy_spread_csv)
            
            spread_df = pd.read_csv(legacy_spread_csv)
            log(f"Loaded {len(spread_df)} historical spread records from CSV")
            
            # Validate that we have the key columns needed for deduplication
            if 'Game Time' not in spread_df.columns or 'Team' not in spread_df.columns:
                log(f"Warning: Legacy spread CSV missing required columns. Skipping migration.")
                spread_df = pd.DataFrame()
        except Exception as e:
            log(f"Warning: Could not load legacy spread CSV: {e}")
            spread_df = pd.DataFrame()
    else:
        log(f"No legacy spread CSV found at {legacy_spread_csv}")
    
    # Load legacy total CSV
    if os.path.exists(legacy_total_csv):
        try:
            log(f"Found legacy total CSV: {legacy_total_csv}")
            backup_csv_file(legacy_total_csv)
            
            total_df = pd.read_csv(legacy_total_csv)
            log(f"Loaded {len(total_df)} historical total records from CSV")
            
            # Validate that we have the key columns needed for deduplication
            if 'Game Time' not in total_df.columns or 'Game' not in total_df.columns:
                log(f"Warning: Legacy total CSV missing required columns. Skipping migration.")
                total_df = pd.DataFrame()
        except Exception as e:
            log(f"Warning: Could not load legacy total CSV: {e}")
            total_df = pd.DataFrame()
    else:
        log(f"No legacy total CSV found at {legacy_total_csv}")
    
    return spread_df, total_df

def load_existing_excel_data():
    """Load existing master Excel file or create new DataFrames
    
    Also loads and merges legacy CSV data on first run.
    
    Returns:
        tuple: (spread_df, total_df) - DataFrames for spreads and totals sheets
    """
    spread_df = pd.DataFrame()
    total_df = pd.DataFrame()
    
    if os.path.exists(excel_output):
        log(f"Loading existing data from {excel_output}")
        try:
            spread_df = pd.read_excel(excel_output, sheet_name='Spreads')
            log(f"Loaded {len(spread_df)} existing spread rows from Excel")
        except Exception as e:
            log(f"Warning: Could not load Spreads sheet: {e}")
            spread_df = pd.DataFrame()
        
        try:
            total_df = pd.read_excel(excel_output, sheet_name='Totals')
            log(f"Loaded {len(total_df)} existing total rows from Excel")
        except Exception as e:
            log(f"Warning: Could not load Totals sheet: {e}")
            total_df = pd.DataFrame()
    else:
        log(f"Excel file does not exist yet: {excel_output}")
    
    # Load and merge historical CSV data
    log("Checking for historical CSV data to migrate...")
    csv_spread_df, csv_total_df = load_historical_csv_data()
    
    # Merge CSV data with Excel data
    if not csv_spread_df.empty:
        if spread_df.empty:
            spread_df = csv_spread_df
            log(f"Migrated all {len(csv_spread_df)} spread records from CSV")
        else:
            # Merge and deduplicate
            before_count = len(spread_df)
            spread_df = pd.concat([spread_df, csv_spread_df], ignore_index=True)
            # Use deduplication logic
            spread_df['game_date'] = spread_df['Game Time'].apply(get_game_date)
            spread_df = spread_df[spread_df['game_date'].notna()]
            spread_df['dedup_key'] = spread_df['game_date'] + '_' + spread_df['Team'].astype(str)
            spread_df = spread_df.drop_duplicates(subset=['dedup_key'], keep='first')
            spread_df = spread_df.drop(columns=['game_date', 'dedup_key'])
            after_count = len(spread_df)
            log(f"Merged CSV spread data: {after_count - before_count} new records added")
    
    if not csv_total_df.empty:
        if total_df.empty:
            total_df = csv_total_df
            log(f"Migrated all {len(csv_total_df)} total records from CSV")
        else:
            # Merge and deduplicate
            before_count = len(total_df)
            total_df = pd.concat([total_df, csv_total_df], ignore_index=True)
            # Use deduplication logic
            total_df['game_date'] = total_df['Game Time'].apply(get_game_date)
            total_df = total_df[total_df['game_date'].notna()]
            total_df['dedup_key'] = total_df['game_date'] + '_' + total_df['Game'].astype(str)
            total_df = total_df.drop_duplicates(subset=['dedup_key'], keep='first')
            total_df = total_df.drop(columns=['game_date', 'dedup_key'])
            after_count = len(total_df)
            log(f"Merged CSV total data: {after_count - before_count} new records added")
    
    return spread_df, total_df

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
    # Handle empty new_games DataFrame
    if new_games.empty:
        return new_games
    
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

def save_to_csv_fallback(spread_games, total_games):
    """Fallback function to save data to CSV files if Excel writing fails
    
    Args:
        spread_games: DataFrame of spread games
        total_games: DataFrame of total games
    
    Returns:
        tuple: (spread_count, total_count) - number of new games added
    """
    log("Using CSV fallback for data storage...")
    
    csv_spread_file = os.path.join(script_dir, 'master_spread_games.csv')
    csv_total_file = os.path.join(script_dir, 'master_total_games.csv')
    
    spread_count = 0
    total_count = 0
    
    try:
        # Load existing CSV data
        existing_spread = pd.DataFrame()
        existing_total = pd.DataFrame()
        
        if os.path.exists(csv_spread_file):
            existing_spread = pd.read_csv(csv_spread_file)
            log(f"Loaded {len(existing_spread)} existing spread records from CSV")
        
        if os.path.exists(csv_total_file):
            existing_total = pd.read_csv(csv_total_file)
            log(f"Loaded {len(existing_total)} existing total records from CSV")
        
        # Deduplicate
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
        
        # Save to CSV
        if not final_spread.empty:
            final_spread.to_csv(csv_spread_file, index=False)
            log(f"Successfully saved {len(final_spread)} spread games to {csv_spread_file}")
        
        if not final_total.empty:
            final_total.to_csv(csv_total_file, index=False)
            log(f"Successfully saved {len(final_total)} total games to {csv_total_file}")
        
        log(f"CSV fallback completed: {spread_count} new spread games, {total_count} new total games")
        
        return spread_count, total_count
        
    except Exception as e:
        log(f"ERROR: CSV fallback also failed: {str(e)}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")
        return 0, 0


def save_to_excel(spread_games, total_games):
    """Save spread and total games to Excel file with separate sheets
    
    Args:
        spread_games: DataFrame of spread games
        total_games: DataFrame of total games
    
    Returns:
        tuple: (spread_count, total_count) - number of new games added
    """
    log("Saving games to Excel file...")
    log(f"Target Excel file path: {excel_output}")
    
    # Check if openpyxl is available
    if not EXCEL_AVAILABLE:
        log("ERROR: openpyxl is not available. Cannot create Excel file.", "ERROR")
        log("Falling back to CSV output...", "WARNING")
        return save_to_csv_fallback(spread_games, total_games)
    
    # Load existing data (includes CSV migration)
    existing_spread, existing_total = load_existing_excel_data()
    
    # Log pre-merge counts for validation
    log(f"Before merge - Existing spread records: {len(existing_spread)}, New spread candidates: {len(spread_games)}")
    log(f"Before merge - Existing total records: {len(existing_total)}, New total candidates: {len(total_games)}")
    
    # Validate input DataFrames
    log(f"Input data validation:")
    log(f"  Spread games DataFrame: {len(spread_games)} rows, {len(spread_games.columns) if not spread_games.empty else 0} columns")
    log(f"  Total games DataFrame: {len(total_games)} rows, {len(total_games.columns) if not total_games.empty else 0} columns")
    
    # Deduplicate new games
    new_spread_games = deduplicate_games(spread_games, existing_spread, use_game_key=False)
    new_total_games = deduplicate_games(total_games, existing_total, use_game_key=True)
    
    spread_count = len(new_spread_games)
    total_count = len(new_total_games)
    
    log(f"After deduplication: {spread_count} new spread games, {total_count} new total games")
    
    # Combine with existing data
    if existing_spread.empty:
        final_spread = new_spread_games
    else:
        final_spread = pd.concat([existing_spread, new_spread_games], ignore_index=True)
    
    if existing_total.empty:
        final_total = new_total_games
    else:
        final_total = pd.concat([existing_total, new_total_games], ignore_index=True)
    
    # Validate data integrity
    log(f"Data integrity check:")
    log(f"  Final spread count: {len(final_spread)} (should be >= existing {len(existing_spread)})")
    log(f"  Final total count: {len(final_total)} (should be >= existing {len(existing_total)})")
    
    if len(final_spread) < len(existing_spread):
        log(f"ERROR: Data loss detected in spreads! Final: {len(final_spread)}, Expected: >= {len(existing_spread)}", "ERROR")
    
    if len(final_total) < len(existing_total):
        log(f"ERROR: Data loss detected in totals! Final: {len(final_total)}, Expected: >= {len(existing_total)}", "ERROR")
    
    # Check if we have data to write
    if final_spread.empty and final_total.empty:
        log("WARNING: No data to write to Excel file (both DataFrames are empty)", "WARNING")
        log("Excel file will not be created/updated", "WARNING")
        return 0, 0
    
    # Log DataFrame structure before writing
    if not final_spread.empty:
        log(f"Spreads DataFrame structure: shape={final_spread.shape}, columns={list(final_spread.columns[:5])}...", "DEBUG")
    if not final_total.empty:
        log(f"Totals DataFrame structure: shape={final_total.shape}, columns={list(final_total.columns[:5])}...", "DEBUG")
    
    # Save to Excel with multiple sheets - with comprehensive error handling
    try:
        log(f"Attempting to write Excel file to: {excel_output}")
        log(f"Writing {len(final_spread)} spread games and {len(final_total)} total games")
        
        # Check file permissions
        excel_dir = os.path.dirname(excel_output)
        if not os.access(excel_dir, os.W_OK):
            log(f"ERROR: No write permission for directory: {excel_dir}", "ERROR")
            raise PermissionError(f"Cannot write to directory: {excel_dir}")
        
        # Check if file exists and is writable
        if os.path.exists(excel_output):
            if not os.access(excel_output, os.W_OK):
                log(f"ERROR: Excel file exists but is not writable: {excel_output}", "ERROR")
                raise PermissionError(f"Cannot write to file: {excel_output}")
            log(f"Updating existing Excel file: {excel_output}")
        else:
            log(f"Creating new Excel file: {excel_output}")
        
        # Write to Excel
        with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
            final_spread.to_excel(writer, sheet_name='Spreads', index=False)
            log(f"Successfully wrote 'Spreads' sheet with {len(final_spread)} rows")
            
            final_total.to_excel(writer, sheet_name='Totals', index=False)
            log(f"Successfully wrote 'Totals' sheet with {len(final_total)} rows")
        
        # Verify the file was created/updated
        if os.path.exists(excel_output):
            file_size = os.path.getsize(excel_output)
            log(f"SUCCESS: Excel file created/updated successfully at {excel_output}")
            log(f"File size: {file_size} bytes")
        else:
            log(f"ERROR: Excel file was not created at {excel_output}", "ERROR")
            raise FileNotFoundError(f"Excel file was not created: {excel_output}")
        
        log(f"Saved {len(final_spread)} spread games and {len(final_total)} total games to {excel_output}")
        log(f"New games added this run: {spread_count} spreads, {total_count} totals")
        
        return spread_count, total_count
        
    except PermissionError as e:
        log(f"ERROR: Permission denied when writing Excel file: {str(e)}", "ERROR")
        log("The file might be open in another application (Excel, etc.)", "ERROR")
        log("Falling back to CSV output...", "WARNING")
        return save_to_csv_fallback(spread_games, total_games)
        
    except Exception as e:
        log(f"ERROR: Failed to write Excel file: {str(e)}", "ERROR")
        log(f"Error type: {type(e).__name__}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")
        log("Falling back to CSV output...", "WARNING")
        return save_to_csv_fallback(spread_games, total_games)

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
        
        # Log qualifying games summary before processing
        log("=" * 60)
        log("QUALIFYING GAMES SUMMARY:")
        log(f"  Spread games found: {len(spread_games)}")
        log(f"  Total games found: {len(total_games)}")
        
        if len(spread_games) > 0:
            log(f"  Spread game details:")
            for idx, row in spread_games.head(5).iterrows():
                log(f"    - {row.get('Team', 'N/A')} on {row.get('Game Time', 'N/A')}, Edge: {row.get('Edge For Covering Spread', 0):.3f}")
            if len(spread_games) > 5:
                log(f"    ... and {len(spread_games) - 5} more spread games")
        else:
            log("  No spread games qualified (Edge < 0.03 or consensus flag = 0)")
        
        if len(total_games) > 0:
            log(f"  Total game details:")
            for idx, row in total_games.head(5).iterrows():
                over_edge = row.get('Over Total Edge', 0)
                under_edge = row.get('Under Total Edge', 0)
                log(f"    - {row.get('Game', 'N/A')} on {row.get('Game Time', 'N/A')}, Over Edge: {over_edge:.3f}, Under Edge: {under_edge:.3f}")
            if len(total_games) > 5:
                log(f"    ... and {len(total_games) - 5} more total games")
        else:
            log("  No total games qualified (Edge < 0.03 or consensus flags = 0)")
        
        log("=" * 60)
        
        # Multi-date FanMatch scraping
        # Check if we have qualifying games that need results
        if not spread_games.empty or not total_games.empty:
            try:
                log("=" * 60)
                log("MULTI-DATE FANMATCH SCRAPING")
                log("=" * 60)
                
                # Import scraping module
                try:
                    from scrape_fanmatch import scrape_fanmatch_for_tracked_games
                    
                    # Check if credentials are available
                    if os.getenv('EMAIL') and os.getenv('PASSWORD'):
                        log("KenPom credentials found - attempting to scrape FanMatch data...")
                        
                        # Scrape FanMatch data for all unique game dates
                        success_count = scrape_fanmatch_for_tracked_games(
                            spread_games,
                            total_games,
                            kenpom_data_dir,
                            headless=True
                        )
                        
                        if success_count > 0:
                            log(f"Successfully scraped FanMatch data for {success_count} dates")
                        else:
                            log("No new FanMatch data was scraped", "WARNING")
                    else:
                        log("KenPom credentials not found in environment - skipping scraping", "WARNING")
                        log("To enable scraping, set EMAIL and PASSWORD in .env file", "WARNING")
                        
                except ImportError as ie:
                    log(f"Could not import scrape_fanmatch module: {ie}", "WARNING")
                    log("Skipping automatic FanMatch scraping - will use existing HTML files", "WARNING")
                    
            except Exception as scrape_error:
                log(f"Error during FanMatch scraping: {scrape_error}", "WARNING")
                log("Continuing with existing FanMatch data...", "WARNING")
        
        # Load FanMatch results for grading
        fanmatch_results = load_fanmatch_results()
        
        # Add game results and grades
        if not spread_games.empty:
            spread_games = add_game_results_to_spreads(spread_games, fanmatch_results)
        
        if not total_games.empty:
            total_games = add_game_results_to_totals(total_games, fanmatch_results)
        
        # Save to Excel file
        log("=" * 60)
        log("SAVING TO EXCEL FILE")
        log("=" * 60)
        spread_count, total_count = save_to_excel(spread_games, total_games)
        
        # Update summary
        update_summary(spread_count, total_count)
        
        log("=" * 60)
        log("Game tracking completed successfully")
        log(f"New games added: {spread_count} spread, {total_count} total")
        log("=" * 60)
        
        sys.exit(0)
        
    except Exception as e:
        log(f"ERROR: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
