#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "beautifulsoup4",
#   "python-dotenv",
#   "psycopg2-binary",
# ]
# ///

import os
import re
import csv
from bs4 import BeautifulSoup
import argparse
from datetime import datetime
import sys
import json
from dotenv import load_dotenv
import traceback
import psycopg2
from psycopg2.extras import execute_values

# Load environment variables
load_dotenv()

def validate_year(year_str):
    """Validate the year to ensure it's reasonable (not too far in future)"""
    try:
        year = int(year_str)
        current_year = datetime.now().year
        # Allow current year and a few years in the past, but not too far in the future
        if year > current_year + 1:
            return str(current_year)  # Return current year if date is too far in future
        return year_str
    except ValueError:
        return str(datetime.now().year)

def parse_fanmatch_html(html_content, date=None):
    """Parse the FanMatch HTML content and extract game data with robust error handling"""
    
    # Parse the HTML
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return []
    
    # Use provided date or try to extract from HTML
    try:
        if date:
            # Validate the date
            parts = date.split('-')
            if len(parts) == 3:
                parts[0] = validate_year(parts[0])  # Validate year
                match_date = "-".join(parts)
            else:
                match_date = date
        else:
            # Try to extract date from title
            title = soup.find('title')
            date_match = None
            if title:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', title.text)
            
            if date_match:
                date_parts = date_match.group(1).split('-')
                date_parts[0] = validate_year(date_parts[0])  # Validate year
                match_date = "-".join(date_parts)
            else:
                # Try from content header
                content_header = soup.find('div', id='content-header')
                if content_header:
                    header_text = content_header.get_text(strip=True)
                    day_match = re.search(r'for\s+(\w+),\s+(\w+)\s+(\d+)', header_text)
                    if day_match:
                        day_of_week = day_match.group(1)  # e.g., "Monday"
                        month = day_match.group(2)  # e.g., "March"
                        day = day_match.group(3)  # e.g., "15"
                        # Convert month name to month number
                        month_names = [
                            "January", "February", "March", "April", "May", "June",
                            "July", "August", "September", "October", "November", "December"
                        ]
                        month_num = str(month_names.index(month) + 1).zfill(2)
                        
                        # Use current year or extract from URL
                        current_year = datetime.now().year
                        year = str(current_year)
                        
                        # See if we can find a year in a URL
                        year_match = re.search(r'fanmatch\.php\?d=(\d{4})', str(soup))
                        if year_match:
                            year = validate_year(year_match.group(1))
                        
                        match_date = f"{year}-{month_num}-{day.zfill(2)}"
                    else:
                        match_date = datetime.now().strftime("%Y-%m-%d")
                else:
                    match_date = datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        print(f"Error extracting date: {e}")
        match_date = datetime.now().strftime("%Y-%m-%d")
    
    # Find the FanMatch table
    try:
        table = soup.find('table', id='fanmatch-table')
        if not table:
            print("Could not find table with id 'fanmatch-table' in the HTML content")
            return []
    except Exception as e:
        print(f"Error finding FanMatch table: {e}")
        return []
    
    # Extract rows from the table (skip header row)
    try:
        rows = table.find_all('tr')
        if len(rows) < 1:
            print("No rows found in FanMatch table")
            return []
        
        header_row = rows[0]
        data_rows = rows[1:]
    except Exception as e:
        print(f"Error extracting rows from table: {e}")
        return []
    
    games = []
    
    # Process each row (game)
    for row_index, row in enumerate(data_rows):
        try:
            cells = row.find_all('td')
            
            # Skip rows with insufficient cells
            if len(cells) < 5:
                continue
            
            # Initialize game data dictionary with default values
            game_data = {
                'match_date': match_date,
                'row_index': row_index,
                'away_team': None,
                'away_seed': None,
                'home_team': None,
                'home_seed': None,
                'conference': None,
                'predicted_winner': None,
                'predicted_winner_score': None,
                'predicted_loser_score': None,
                'win_probability': None,
                'brackets_value': None,
                'game_time': None,
                'network': None,
                'city_state': None,
                'venue': None,
                'thrill_score': None,
                'excitement_index': None,
                'game_quality': None,
                'home_spread': None,
                'away_spread': None,
                'home_win_probability': None,
                'away_win_probability': None,
                'total': None,
                'raw_game_text': None,
                'raw_prediction_text': None,
                'raw_time_network_text': None,
                'raw_location_text': None,
                'raw_thrill_text': None,
                'html_fragment': str(row)
            }
            
            # Extract raw text for debugging
            try:
                game_data['raw_game_text'] = cells[0].get_text(strip=True) if len(cells) > 0 else None
                game_data['raw_prediction_text'] = cells[1].get_text(strip=True) if len(cells) > 1 else None
                game_data['raw_time_network_text'] = cells[2].get_text(strip=True) if len(cells) > 2 else None
                game_data['raw_location_text'] = cells[3].get_text(strip=True) if len(cells) > 3 else None
                game_data['raw_thrill_text'] = cells[4].get_text(strip=True) if len(cells) > 4 else None
            except Exception as e:
                print(f"Warning: Error extracting raw text from row {row_index}: {e}")
            
            # Extract game data with separate try/except blocks for each section
            
            # 1. Extract team info directly from links when possible
            try:
                game_cell = cells[0]

                # Try to get team names directly from links first
                team_links = game_cell.find_all('a')
                team_links = [link for link in team_links if 'team.php' in link.get('href', '')]

                if len(team_links) >= 2:
                    # First link is usually away team, second is home team
                    game_data['away_team'] = team_links[0].get_text(strip=True)
                    game_data['home_team'] = team_links[1].get_text(strip=True)

                    # Try to extract seeds
                    seed_spans = game_cell.find_all('span', class_='seed-gray')
                    if len(seed_spans) >= 2:
                        game_data['away_seed'] = seed_spans[0].get_text(strip=True)
                        game_data['home_seed'] = seed_spans[1].get_text(strip=True)

                    # Try to extract conference
                    conf_span = game_cell.find('span', style=lambda value: value and 'font-style:italic' in value)
                    if conf_span:
                        game_data['conference'] = conf_span.get_text(strip=True)
                elif len(team_links) == 1:
                    # Handle case where only one team has a link
                    # Parse the full text to find both teams
                    full_text = game_cell.get_text(strip=True)

                    # Extract seeds (including "NR" for Not Ranked)
                    seed_spans = game_cell.find_all('span', class_='seed-gray')
                    if len(seed_spans) >= 2:
                        game_data['away_seed'] = seed_spans[0].get_text(strip=True)
                        game_data['home_seed'] = seed_spans[1].get_text(strip=True)

                    # Check for "vs." or "at" to determine game location
                    if ' at' in full_text:
                        # Away at Home format
                        # Split on "at" and extract team names
                        parts = full_text.split(' at')
                        if len(parts) == 2:
                            # Away team is before "at"
                            away_part = parts[0].strip()
                            # Remove seed if present (NR or digits, with optional space)
                            away_part = re.sub(r'^(NR|\d+)\s*', '', away_part)
                            game_data['away_team'] = away_part

                            # Home team is after "at"
                            home_part = parts[1].strip()
                            # Remove seed if present (NR or digits, with optional space)
                            home_part = re.sub(r'^(NR|\d+)\s*', '', home_part)
                            game_data['home_team'] = home_part
                    elif ' vs.' in full_text:
                        # Neutral site
                        parts = full_text.split(' vs.')
                        if len(parts) == 2:
                            away_part = parts[0].strip()
                            away_part = re.sub(r'^(NR|\d+)\s*', '', away_part)
                            game_data['away_team'] = away_part

                            home_part = parts[1].strip()
                            home_part = re.sub(r'^(NR|\d+)\s*', '', home_part)
                            game_data['home_team'] = home_part
                else:
                    # Fallback to regex parsing if links aren't found
                    team_info = game_cell.get_text(strip=True)

                    # Updated patterns to handle "NR" (Not Ranked) as well as digits
                    # Try vs. pattern first (neutral site)
                    teams_pattern = r'(NR|\d+)\s+([A-Za-z\s\.&+\-\']+?)\s+vs\.\s+(NR|\d+)\s+([A-Za-z\s\.&+\-\']+?)(?:\s+([A-Z0-9\-]+))?$'
                    teams_match = re.search(teams_pattern, team_info)

                    if teams_match:
                        game_data['away_seed'] = teams_match.group(1)
                        game_data['away_team'] = teams_match.group(2).strip()
                        game_data['home_seed'] = teams_match.group(3)
                        game_data['home_team'] = teams_match.group(4).strip()
                        if teams_match.group(5):
                            game_data['conference'] = teams_match.group(5)
                    else:
                        # Try at pattern (home/away)
                        teams_pattern_alt = r'(NR|\d+)\s+([A-Za-z\s\.&+\-\']+?)\s+at\s+(NR|\d+)\s+([A-Za-z\s\.&+\-\']+?)(?:\s+([A-Z0-9\-]+))?$'
                        teams_match_alt = re.search(teams_pattern_alt, team_info)
                        if teams_match_alt:
                            game_data['away_seed'] = teams_match_alt.group(1)
                            game_data['away_team'] = teams_match_alt.group(2).strip()
                            game_data['home_seed'] = teams_match_alt.group(3)
                            game_data['home_team'] = teams_match_alt.group(4).strip()
                            if teams_match_alt.group(5):
                                game_data['conference'] = teams_match_alt.group(5)
            except Exception as e:
                print(f"Warning: Error extracting team info for row {row_index}: {e}")
                
            # 2. Extract prediction
            try:
                if len(cells) > 1:
                    prediction_cell = cells[1]
                    prediction_text = prediction_cell.get_text(strip=True)
                    
                    # Parse prediction (format: "Team 75-70 (55%)")
                    prediction_pattern = r'([A-Za-z\s\.&+\-\']+)\s+(\d+)-(\d+)\s+\((\d+)%\)'
                    prediction_match = re.search(prediction_pattern, prediction_text)
                    
                    if prediction_match:
                        game_data['predicted_winner'] = prediction_match.group(1).strip()
                        game_data['predicted_winner_score'] = int(prediction_match.group(2))
                        game_data['predicted_loser_score'] = int(prediction_match.group(3))
                        game_data['win_probability'] = int(prediction_match.group(4)) / 100  # Convert to decimal
                    
                    # Extract brackets info if present (e.g., [69])
                    brackets_pattern = r'\[(\d+)\]'
                    brackets_match = re.search(brackets_pattern, prediction_text)
                    if brackets_match:
                        game_data['brackets_value'] = brackets_match.group(1)
            except Exception as e:
                print(f"Warning: Error extracting prediction for row {row_index}: {e}")
            
            # 3. Extract time and network
            try:
                if len(cells) > 2:
                    time_cell = cells[2]
                    time_text = time_cell.get_text(strip=True)
                    
                    # Parse time (format: "7:00 pm")
                    time_pattern = r'(\d+:\d+\s+[ap]m)'
                    time_match = re.search(time_pattern, time_text)
                    if time_match:
                        game_data['game_time'] = time_match.group(1)
                    
                    # Extract network
                    network_link = time_cell.find('a', target='blank')
                    if network_link:
                        game_data['network'] = network_link.get_text(strip=True)
            except Exception as e:
                print(f"Warning: Error extracting time/network for row {row_index}: {e}")
            
            # 4. Extract location - Fix the location parsing
            try:
                if len(cells) > 3:
                    location_cell = cells[3]
                    location_html = str(location_cell)
                    location_text = location_cell.get_text(strip=True)
                    
                    # First check for newlines in the HTML
                    if '<br/>' in location_html or '<br>' in location_html:
                        location_parts = location_cell.get_text(separator="|BREAK|", strip=True).split("|BREAK|")
                        if len(location_parts) >= 1:
                            game_data['city_state'] = location_parts[0].strip()
                        if len(location_parts) >= 2:
                            game_data['venue'] = location_parts[1].strip()
                    else:
                        # Try to separate city/state and venue using common patterns
                        # Common US state abbreviations pattern
                        state_pattern = r'([A-Z]{2})\s*([A-Za-z\s\-]+)'
                        state_match = re.search(state_pattern, location_text)
                        
                        if state_match:
                            # Found state abbreviation, split at that point
                            state = state_match.group(1)
                            venue = state_match.group(2).strip()
                            
                            # Find the city that comes before the state
                            city_match = re.search(r'([A-Za-z\s\-,]+)' + state, location_text)
                            if city_match:
                                city = city_match.group(1).strip().rstrip(',')
                                game_data['city_state'] = f"{city}, {state}"
                                game_data['venue'] = venue
                        else:
                            # Try to find a pattern with comma
                            comma_split = location_text.split(',')
                            if len(comma_split) >= 2:
                                # Assume format: "City, State Venue"
                                city_state_part = comma_split[0] + ',' + comma_split[1].split()[0]
                                venue_part = ' '.join(comma_split[1].split()[1:])
                                
                                game_data['city_state'] = city_state_part.strip()
                                game_data['venue'] = venue_part.strip()
                            else:
                                # Just store the whole thing as city_state if we can't parse it
                                game_data['city_state'] = location_text
            except Exception as e:
                print(f"Warning: Error extracting location for row {row_index}: {e}")
            
            # 5. Extract thrill score
            try:
                if len(cells) > 4:
                    thrill_cell = cells[4]
                    thrill_text = thrill_cell.get_text(strip=True)
                    
                    # The first value is the thrill score
                    thrill_parts = thrill_text.split()
                    if thrill_parts:
                        game_data['thrill_score'] = thrill_parts[0]
                        
                        # Some rows include additional metrics
                        if len(thrill_parts) > 1:
                            # Look for excitement index
                            excitement_match = re.search(r'E:(\d+)', thrill_text)
                            if excitement_match:
                                game_data['excitement_index'] = excitement_match.group(1)
                            
                            # Look for game quality
                            quality_match = re.search(r'Q:(\d+)', thrill_text)
                            if quality_match:
                                game_data['game_quality'] = quality_match.group(1)
            except Exception as e:
                print(f"Warning: Error extracting thrill score for row {row_index}: {e}")
            
            # 6. Calculate derived values (spreads, totals, etc.)
            try:
                if game_data['predicted_winner_score'] is not None and game_data['predicted_loser_score'] is not None:
                    game_data['total'] = game_data['predicted_winner_score'] + game_data['predicted_loser_score']
                    spread = game_data['predicted_winner_score'] - game_data['predicted_loser_score']
                    
                    # Determine which team is favored and assign values
                    if game_data['predicted_winner'] == game_data['home_team']:
                        # Home team is favorite
                        game_data['home_spread'] = -abs(spread)
                        game_data['away_spread'] = abs(spread)
                        game_data['home_win_probability'] = game_data['win_probability']
                        game_data['away_win_probability'] = 1 - game_data['win_probability'] if game_data['win_probability'] is not None else None
                    elif game_data['predicted_winner'] == game_data['away_team']:
                        # Away team is favorite
                        game_data['home_spread'] = abs(spread)
                        game_data['away_spread'] = -abs(spread)
                        game_data['away_win_probability'] = game_data['win_probability']
                        game_data['home_win_probability'] = 1 - game_data['win_probability'] if game_data['win_probability'] is not None else None
                    else:
                        # If we can't determine the favorite, provide a warning but don't crash
                        print(f"Warning: Could not determine favorite for game: {game_data['home_team']} vs {game_data['away_team']}")
            except Exception as e:
                print(f"Warning: Error calculating derived values for row {row_index}: {e}")
            
            # Add the game data to our list
            games.append(game_data)
            
        except Exception as e:
            print(f"Error processing row {row_index}: {e}")
            traceback.print_exc()
            # Continue with the next row instead of failing completely
    
    print(f"Successfully parsed {len(games)} games from the HTML content")
    return games

def parse_fanmatch_file(html_file):
    """Parse a local FanMatch HTML file"""
    
    try:
        # Extract date from file name
        date_match = re.search(r'fanmatch-(\d{4}-\d{2}-\d{2})', html_file)
        match_date = date_match.group(1) if date_match else None
        
        # Read the HTML file
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        return parse_fanmatch_html(html_content, match_date)
    except Exception as e:
        print(f"Error parsing file {html_file}: {e}")
        traceback.print_exc()
        return []

def transform_to_kenpom_format(games):
    """
    Transform the games data to match the format in kenpom.py
    Two rows per game - one for home team, one for away team
    """
    if not games:
        print("No games to transform")
        return []
    
    transformed_rows = []
    
    for game in games:
        try:
            # Convert date format from YYYY-MM-DD to YYYYMMDD
            game_date = game['match_date'].replace('-', '') if game['match_date'] else None
            
            # Skip games without both teams
            if not game['home_team'] or not game['away_team']:
                print(f"Warning: Skipping game with missing team info - Home: {game['home_team']}, Away: {game['away_team']}")
                continue
            
            # Try both team orderings
            # Original ordering
            home_row = {
                'Home Team': game['home_team'],
                'Away Team': game['away_team'],
                'Team': game['home_team'],
                'Game Date': game_date,
                'spread_kenpom': game['home_spread'],
                'win_prob_kenpom': game['home_win_probability'],
                'projected_total_kenpom': game['total']
            }
            
            away_row = {
                'Home Team': game['home_team'],
                'Away Team': game['away_team'],
                'Team': game['away_team'],
                'Game Date': game_date,
                'spread_kenpom': game['away_spread'],
                'win_prob_kenpom': game['away_win_probability'],
                'projected_total_kenpom': game['total']
            }
            
            # Swapped ordering
            swapped_home_row = {
                'Home Team': game['away_team'],
                'Away Team': game['home_team'],
                'Team': game['away_team'],
                'Game Date': game_date,
                'spread_kenpom': game['away_spread'],
                'win_prob_kenpom': game['away_win_probability'],
                'projected_total_kenpom': game['total']
            }
            
            swapped_away_row = {
                'Home Team': game['away_team'],
                'Away Team': game['home_team'],
                'Team': game['home_team'],
                'Game Date': game_date,
                'spread_kenpom': game['home_spread'],
                'win_prob_kenpom': game['home_win_probability'],
                'projected_total_kenpom': game['total']
            }
            
            # Add both versions to allow for flexible matching
            transformed_rows.extend([home_row, away_row, swapped_home_row, swapped_away_row])
        except Exception as e:
            print(f"Error transforming game: {e}")
            if 'match_date' in game and 'home_team' in game and 'away_team' in game:
                print(f"Game details: Date: {game['match_date']}, Teams: {game['home_team']} vs {game['away_team']}")
    
    if not transformed_rows:
        print("Warning: No rows were transformed successfully")
        return []
    
    # Define column order for consistency
    column_order = [
        'Home Team', 
        'Away Team', 
        'Team', 
        'Game Date', 
        'spread_kenpom', 
        'win_prob_kenpom', 
        'projected_total_kenpom'
    ]
    
    return transformed_rows

def save_games_to_csv(games, output_file=None, transform=True):
    """Save games to CSV file in the transformed format"""
    
    if not games:
        print("No games to save")
        return False
    
    try:
        # Default output file name based on the date of the first game
        if not output_file:
            first_game = next((g for g in games if g.get('match_date')), {'match_date': datetime.now().strftime("%Y-%m-%d")})
            first_game_date = first_game['match_date']
            output_dir = 'csv_output'
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            output_file = os.path.join(output_dir, f'fanmatch-{first_game_date}.csv')
        
        if transform:
            # Transform games to the format in kenpom.py
            transformed_data = transform_to_kenpom_format(games)
            
            if not transformed_data:
                print("Warning: Transformation resulted in empty data")
                return False
            
            # Define the columns we want in order
            fieldnames = [
                'Home Team', 
                'Away Team', 
                'Team', 
                'Game Date', 
                'spread_kenpom', 
                'win_prob_kenpom', 
                'projected_total_kenpom'
            ]
            
            # Write to CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                for row in transformed_data:
                    writer.writerow(row)
            
            print(f"Successfully saved {len(transformed_data)} rows ({len(transformed_data) // 2} games) to {output_file}")
        else:
            # Save the original format (one row per game)
            # Get all possible keys across all games
            all_keys = set()
            for game in games:
                all_keys.update(game.keys())
            
            # Remove HTML fragment to keep CSV smaller
            if 'html_fragment' in all_keys:
                all_keys.remove('html_fragment')
            
            fieldnames = list(all_keys)
            
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                # Write header
                writer.writeheader()
                
                # Write data rows
                for game in games:
                    # Create a copy without HTML fragment
                    game_copy = {k: v for k, v in game.items() if k != 'html_fragment'}
                    writer.writerow(game_copy)
            
            print(f"Successfully saved {len(games)} games to {output_file} (original format)")
        
        # Also save a JSON version for detailed inspection
        json_output_file = output_file.replace('.csv', '.json')
        with open(json_output_file, 'w', encoding='utf-8') as jsonfile:
            # Convert any non-serializable objects to strings
            serializable_games = []
            for game in games:
                serializable_game = {}
                for key, value in game.items():
                    # Skip HTML fragment for JSON too to keep it smaller
                    if key == 'html_fragment':
                        continue
                    
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_game[key] = value
                    else:
                        serializable_game[key] = str(value)
                serializable_games.append(serializable_game)
            
            json.dump(serializable_games, jsonfile, indent=2)
        
        print(f"Also saved detailed JSON data to {json_output_file}")
        
        return True
    except Exception as e:
        print(f"Error saving games to CSV: {e}")
        traceback.print_exc()
        return False

def save_games_to_database(games, db_url=None):
    """
    Save games to a PostgreSQL database in the transformed format.
    
    Args:
        games (list): List of game dictionaries
        db_url (str): Database URL string, defaults to DATABASE_URL env variable
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not games:
        print("No games to save to database")
        return False
    
    # Get database URL from environment if not provided
    if not db_url:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("Error: DATABASE_URL environment variable not found.")
            return False
    
    # Make sure we have a valid database URL
    if not db_url.startswith(('postgres://', 'postgresql://')):
        print(f"Error: Invalid database URL format. Expected postgres:// or postgresql://, got: {db_url[:10]}...")
        return False
    
    conn = None
    cursor = None
    
    try:
        # Transform games to the desired format
        transformed_data = transform_to_kenpom_format(games)
        
        if not transformed_data:
            print("Warning: Transformation resulted in empty data")
            return False
        
        # Connect to the database
        print(f"Connecting to database...")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Create the Kenpom table if it doesn't exist
        create_table_query = """
        CREATE TABLE IF NOT EXISTS Kenpom (
            id SERIAL PRIMARY KEY,
            home_team VARCHAR(100) NOT NULL,
            away_team VARCHAR(100) NOT NULL,
            team VARCHAR(100) NOT NULL,
            game_date DATE NOT NULL,
            spread_kenpom NUMERIC,
            win_prob_kenpom NUMERIC,
            projected_total_kenpom NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_table_query)
        
        # Create an index on game_date for better performance
        cursor.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = 'kenpom_game_date_idx'
            ) THEN
                CREATE INDEX kenpom_game_date_idx ON Kenpom(game_date);
            END IF;
        END
        $$;
        """)
        
        # Prepare data for insertion
        columns = ['home_team', 'away_team', 'team', 'game_date', 
                   'spread_kenpom', 'win_prob_kenpom', 'projected_total_kenpom']
        
        # Convert dictionary keys to database column names (lowercase)
        values = []
        skipped_count = 0
        inserted_count = 0
        
        for row in transformed_data:
            row_values = []
            # Format date from YYYYMMDD to YYYY-MM-DD for SQL
            game_date = row.get('Game Date')
            if game_date and len(game_date) == 8:
                formatted_date = f"{game_date[:4]}-{game_date[4:6]}-{game_date[6:8]}"
            else:
                formatted_date = None
                
            home_team = row.get('Home Team')
            away_team = row.get('Away Team')
            team = row.get('Team')
            spread_kenpom = row.get('spread_kenpom')
            win_prob_kenpom = row.get('win_prob_kenpom')
            projected_total_kenpom = row.get('projected_total_kenpom')
            
            # Skip records with missing critical data
            if not all([home_team, away_team, team, formatted_date]):
                print(f"Skipping record with missing critical data: {row}")
                skipped_count += 1
                continue
                
            # Check if an identical record already exists
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM Kenpom 
                    WHERE game_date = %s 
                    AND home_team = %s 
                    AND away_team = %s 
                    AND team = %s
                    AND spread_kenpom = %s
                    AND win_prob_kenpom = %s
                    AND projected_total_kenpom = %s
                """, (formatted_date, home_team, away_team, team, 
                     spread_kenpom, win_prob_kenpom, projected_total_kenpom))
                
                count = cursor.fetchone()[0]
                if count > 0:
                    # Skip if exactly the same record already exists
                    skipped_count += 1
                    if skipped_count <= 5:  # Limit logging to prevent console spam
                        print(f"Skipping identical record: {formatted_date} - {home_team} vs {away_team} ({team})")
                    elif skipped_count == 6:
                        print(f"... and more identical records (limiting output)")
                else:
                    # Only add if this exact record doesn't exist yet
                    row_values = [
                        home_team, 
                        away_team, 
                        team, 
                        formatted_date, 
                        spread_kenpom, 
                        win_prob_kenpom, 
                        projected_total_kenpom
                    ]
                    values.append(row_values)
                    inserted_count += 1
            except Exception as e:
                print(f"Error checking for duplicate record: {e}")
                # Continue processing other records
                continue
        
        if values:
            # Use execute_values for efficient bulk insert
            insert_query = """
            INSERT INTO Kenpom (
                home_team, away_team, team, game_date, 
                spread_kenpom, win_prob_kenpom, projected_total_kenpom
            )
            VALUES %s
            """
            
            try:
                # Execute the bulk insert for new records
                execute_values(cursor, insert_query, values)
                
                # Commit the transaction
                conn.commit()
                print(f"Successfully inserted {inserted_count} new rows into Kenpom table")
                if skipped_count > 0:
                    print(f"Skipped {skipped_count} identical records that already existed")
            except Exception as e:
                print(f"Error during bulk insert: {e}")
                conn.rollback()
                return False
        else:
            print("No new records to insert, all records already exist in the database")
        
        return True
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        print("Check your DATABASE_URL environment variable and make sure the database is accessible")
        return False
    except Exception as e:
        print(f"Error saving games to database: {e}")
        traceback.print_exc()
        return False
    finally:
        # Always close cursor and connection if they exist
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as e:
            print(f"Error closing database connection: {e}")

def main():
    """Main function"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Parse KenPom FanMatch HTML files and save all available data')
    parser.add_argument('--html-file', help='Path to the FanMatch HTML file (optional)')
    parser.add_argument('--html-dir', help='Directory containing FanMatch HTML files to process (default: kenpom-data)', default='kenpom-data')
    parser.add_argument('--output', help='Output CSV file path (optional, defaults to csv_output/fanmatch-DATE.csv)')
    parser.add_argument('--no-transform', action='store_true', help='Save in original format (one row per game) instead of transformed format')
    parser.add_argument('--save-to-db', action='store_true', help='Save the processed data to the PostgreSQL database')
    parser.add_argument('--db-url', help='PostgreSQL connection string (defaults to DATABASE_URL env variable)')
    parser.add_argument('--verbose', action='store_true', help='Show more detailed logs')
    
    args = parser.parse_args()
    
    games = []
    success = True
    
    # Process either a single file or a directory of HTML files
    if args.html_dir:
        # If no html_file is specified, use the kenpom-data directory as default
        html_dir = args.html_dir
        
        # Create the directory if it doesn't exist
        if not os.path.isdir(html_dir):
            try:
                os.makedirs(html_dir, exist_ok=True)
                print(f"Created directory: {html_dir}")
                print(f"No HTML files found. Please run kenpom-scraper.js first to download HTML files.")
                return
            except Exception as e:
                print(f"Error creating directory {html_dir}: {e}")
                sys.exit(1)
            
        html_files = [f for f in os.listdir(html_dir) if f.endswith('.html') and f.startswith('fanmatch-')]
        if not html_files:
            print(f"No fanmatch HTML files found in {html_dir}")
            print(f"Please run kenpom-scraper.js first to download HTML files.")
            sys.exit(1)
            
        print(f"Found {len(html_files)} HTML files to process in {html_dir}")
        for html_file in sorted(html_files):
            file_path = os.path.join(html_dir, html_file)
            print(f"Processing {file_path}")
            file_games = parse_fanmatch_file(file_path)
            if file_games:
                games.extend(file_games)
                print(f"Added {len(file_games)} games from {html_file}")
            else:
                print(f"No games found in {html_file}")
    elif args.html_file:
        print(f"Parsing local file: {args.html_file}")
        if not os.path.exists(args.html_file):
            print(f"Error: File {args.html_file} does not exist.")
            sys.exit(1)
        games = parse_fanmatch_file(args.html_file)
    else:
        # Default to the kenpom-data directory if no specific arguments are provided
        html_dir = 'kenpom-data'
        
        # Create the directory if it doesn't exist
        if not os.path.isdir(html_dir):
            try:
                os.makedirs(html_dir, exist_ok=True)
                print(f"Created directory: {html_dir}")
                print(f"No HTML files found. Please run kenpom-scraper.js first to download HTML files.")
                return
            except Exception as e:
                print(f"Error creating directory {html_dir}: {e}")
                sys.exit(1)
            
        html_files = [f for f in os.listdir(html_dir) if f.endswith('.html') and f.startswith('fanmatch-')]
        if not html_files:
            print(f"No fanmatch HTML files found in {html_dir}")
            print(f"Please run kenpom-scraper.js first to download HTML files.")
            sys.exit(1)
            
        print(f"Found {len(html_files)} HTML files to process in {html_dir}")
        for html_file in sorted(html_files):
            file_path = os.path.join(html_dir, html_file)
            print(f"Processing {file_path}")
            file_games = parse_fanmatch_file(file_path)
            if file_games:
                games.extend(file_games)
                print(f"Added {len(file_games)} games from {html_file}")
            else:
                print(f"No games found in {html_file}")
    
    # Save games to CSV and/or database
    if games:
        # Save to CSV if needed
        if not args.save_to_db or args.output:
            if save_games_to_csv(games, args.output, transform=not args.no_transform):
                if args.no_transform:
                    print(f"Successfully saved {len(games)} games to CSV in original format.")
                else:
                    print(f"Successfully saved {len(games)} games to CSV in transformed format (two rows per game).")
            else:
                print(f"Failed to save games to CSV.")
                success = False
        
        # Save to database if requested
        if args.save_to_db:
            print("Saving games to database...")
            if save_games_to_database(games, args.db_url):
                print(f"Successfully saved games to database.")
            else:
                print(f"Failed to save games to database.")
                success = False
    else:
        print("No games parsed.")
        sys.exit(1)
    
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    main() 