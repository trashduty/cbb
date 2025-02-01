import os
# from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options 
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import numpy as np
import re
import time
from datetime import datetime

def fetch_kenpom():
    """
    Fetches game data from kenpom.com for today and tomorrow using Selenium
    """
    # Load environment variables
    # load_dotenv()
    
    # Retrieve credentials
    USERNAME = os.getenv("KENPOM_USERNAME")
    PASSWORD = os.getenv("KENPOM_PASSWORD")
    
    if not USERNAME or not PASSWORD:
        print("Error: Missing KENPOM_USERNAME or KENPOM_PASSWORD environment variables")
        return pd.DataFrame()
        
    # Initialize Firefox options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    # Add user agent to avoid detection
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(options=chrome_options)
    
    all_games = []
    
    try:
        # Navigate to fanmatch page
        driver.get('https://kenpom.com/fanmatch.php')
        wait = WebDriverWait(driver, 30)
        
        # Login
        email_el = wait.until(EC.presence_of_element_located((By.NAME, 'email')))
        email_el.clear()
        email_el.send_keys(USERNAME)
        
        pwd_el = wait.until(EC.presence_of_element_located((By.NAME, 'password')))
        pwd_el.clear()
        pwd_el.send_keys(PASSWORD)
        pwd_el.send_keys(Keys.RETURN)
        time.sleep(5)
        
        # Function to extract date from content header
        def parse_date_from_header():
            header = wait.until(EC.presence_of_element_located((By.ID, 'content-header')))
            header_text = header.text
            print(f"Header text: {header_text}")  # Debug print
            
            # Extract date using regex
            date_match = re.search(r'for (.*?) \(', header_text)
            if not date_match:
                print("Could not find date in header")
                return None
                
            date_str = date_match.group(1)
            print(f"Extracted date string: {date_str}")  # Debug print
            
            try:
                # Parse the date with the current year
                date_obj = datetime.strptime(date_str, '%A, %B %dst')
                return date_obj.replace(year=2025)
            except ValueError:
                try:
                    date_obj = datetime.strptime(date_str, '%A, %B %dnd')
                    return date_obj.replace(year=2025)
                except ValueError:
                    try:
                        date_obj = datetime.strptime(date_str, '%A, %B %drd')
                        return date_obj.replace(year=2025)
                    except ValueError:
                        try:
                            date_obj = datetime.strptime(date_str, '%A, %B %dth')
                            return date_obj.replace(year=2025)
                        except ValueError:
                            print(f"Failed to parse date string: {date_str}")
                            return None
        
        # Function to extract table and add date
        def extract_table_with_date(date_obj):
            if date_obj is None:
                print("No valid date provided for table extraction")
                return pd.DataFrame()
                
            fanmatch_table = wait.until(EC.presence_of_element_located((By.ID, 'fanmatch-table')))
            time.sleep(2)
            table_html = fanmatch_table.get_attribute('outerHTML')
            df = pd.read_html(table_html)[0]
            df['Game Date'] = date_obj.strftime('%Y%m%d')
            return df
        
        # Get today's date and games
        today_date = parse_date_from_header()
        if today_date:
            today_games = extract_table_with_date(today_date)
            if not today_games.empty:
                all_games.append(today_games)
        
        # Find and click tomorrow's link
        try:
            tomorrow_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'fanmatch.php?d=')]")
            # Get the link that points to the next day
            tomorrow_link = next(link for link in tomorrow_links 
                               if datetime.strptime(link.get_attribute('href').split('=')[1], '%Y-%m-%d') > today_date)
            
            tomorrow_date = datetime.strptime(tomorrow_link.get_attribute('href').split('=')[1], '%Y-%m-%d')
            tomorrow_link.click()
            time.sleep(5)
            
            # Get tomorrow's games
            tomorrow_games = extract_table_with_date(tomorrow_date)
            if not tomorrow_games.empty:
                all_games.append(tomorrow_games)
                
        except Exception as e:
            print(f"Error fetching tomorrow's games: {e}")
        
        # Combine all games
        if not all_games:
            print("No games data collected")
            return pd.DataFrame()
            
        combined_df = pd.concat(all_games, ignore_index=True)
        print(f"Combined DataFrame columns: {combined_df.columns}")  # Debug print
        return combined_df
        
    except Exception as e:
        print(f"Error fetching KenPom data: {e}")
        return pd.DataFrame()
        
    finally:
        driver.quit()
def map_team_names(df):
    """Map team names using crosswalk"""
    crosswalk = pd.read_csv('crosswalk.csv')
    name_map = crosswalk.set_index('kenpom')['API'].to_dict()
    
    # Create mapping report
    unmapped_teams = {}
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])
    
    if unmapped_teams:
        print("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            print(f"- {team}: {count} occurrences")
    
    # Create mapped dataframe
    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)
    
    # Drop rows with missing mappings
    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    if len(mapped_df) < original_count:
        print(f"\nDropped {original_count - len(mapped_df)} rows due to mapping issues")
    
    return mapped_df
def clean_kenpom(df):
    """
    Cleans the DataFrame by processing team names, spreads, probabilities and totals
    """
    if df.empty:
        print("Empty DataFrame received in clean_kenpom")
        return df
        
    print(f"Input DataFrame columns: {df.columns}")  # Debug print
    
    # Create a copy
    df_clean = df.copy()
    
    # Force columns to lower for consistency
    df_clean.columns = df_clean.columns.str.strip().str.lower()
    
    # Filter rows with valid game information
    df_clean = df_clean[df_clean['game'].str.contains(r'\bat\b|vs\.', case=False, na=False)].copy()
    
    # Parse home vs away teams
    def extract_teams(game_str):
        if pd.isna(game_str):
            return None, None
            
        if 'vs.' in game_str:
            parts = game_str.split('vs.')
            if len(parts) == 2:
                return parts[1].strip(), parts[0].strip()  # home, away
        elif ' at ' in game_str:
            parts = game_str.split(' at ')
            if len(parts) == 2:
                return parts[1].strip(), parts[0].strip()  # home, away
                
        return None, None
    
    # Extract teams
    df_clean['teams'] = df_clean['game'].apply(lambda x: extract_teams(x))
    df_clean = df_clean.dropna(subset=['teams'])
    df_clean['Home Team'] = df_clean['teams'].apply(lambda x: x[0])
    df_clean['Away Team'] = df_clean['teams'].apply(lambda x: x[1])
    
    # Clean team names - remove rankings and stats
    def clean_team_name(name):
        # Remove leading numbers and dots
        name = re.sub(r'^\d+\s*\.?\s*', '', name)
        # Remove trailing numbers
        name = re.sub(r'\s*\d+$', '', name)
        return name.strip()
    
    df_clean['Home Team'] = df_clean['Home Team'].apply(clean_team_name)
    df_clean['Home Team'] = df_clean['Home Team'].str.rsplit(' ', n=1).str[0]
    df_clean['Away Team'] = df_clean['Away Team'].apply(clean_team_name)
    
        # Parse prediction column for spreads and probabilities
    def parse_prediction(pred_str):
        if pd.isna(pred_str):
            return None, None, None

        # Match a pattern like:
        # rank teamname fav_score-dog_score (win_prob%)
        pattern = r'^(.+?)\s+(\d+)-(\d+).*\(([\d.]+)%\)'
        match = re.search(pattern, pred_str)
        if not match:
            return None, None, None

        fav_team = match.group(1).strip()
        fav_score = int(match.group(2))
        dog_score = int(match.group(3))
        win_prob = float(match.group(4)) / 100.0

        return fav_team, (fav_score, dog_score), win_prob

    # Apply prediction parsing
    df_clean['parsed_pred'] = df_clean['prediction'].apply(parse_prediction)
    df_clean = df_clean.dropna(subset=['parsed_pred'])
    def assign_values(row):
        fav_team, scores, win_prob = row['parsed_pred']
        fav_score, dog_score = scores
        spread = fav_score - dog_score
        total = fav_score + dog_score

        # Determine which team is favored based on Home and Away
        if row['Home Team'] == fav_team:
            # Home team is the favorite
            home_spread = -abs(spread)
            home_prob = win_prob
            away_spread = abs(spread)
            away_prob = 1 - win_prob
        elif row['Away Team'] == fav_team:
            # Away team is the favorite
            home_spread = abs(spread)
            home_prob = 1 - win_prob
            away_spread = -abs(spread)
            away_prob = win_prob
        else:
            # If the favored team is not found among Home or Away, warn user
            print("Warning: Favored team not found in game teams:",
                row['teams'], "fav_team:", fav_team)
            home_spread = away_spread = None
            home_prob = away_prob = None

        return pd.Series({
            'spread_kenpom_home': home_spread,
            'spread_kenpom_away': away_spread,
            'win_prob_kenpom_home': home_prob,
            'win_prob_kenpom_away': away_prob,
            'projected_total_kenpom': total
        })

    # Calculate final values
    final_cols = df_clean.apply(assign_values, axis=1)
    df_clean = pd.concat([df_clean[['Home Team', 'Away Team', 'game date']], final_cols], axis=1)
    
    print(f"Output DataFrame columns: {df_clean.columns}")  # Debug print
    return df_clean

def transform_kenpom_format(df):
    """
    Transforms KenPom DataFrame from one row per game to two rows per game
    """
    if df.empty:
        print("Empty DataFrame received in transform_kenpom_format")
        return df
        
    print(f"Transform input DataFrame columns: {df.columns}")  # Debug print
    
    # Create empty list to store transformed rows
    transformed_rows = []
    
    for _, row in df.iterrows():
        try:
            # Create home team row
            home_row = {
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Home Team'],
                'Game Date': row['game date'],
                'spread_kenpom': row['spread_kenpom_home'],
                'win_prob_kenpom': row['win_prob_kenpom_home'],
                'projected_total_kenpom': row['projected_total_kenpom']
            }
            
            # Create away team row
            away_row = {
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Away Team'],
                'Game Date': row['game date'],
                'spread_kenpom': row['spread_kenpom_away'],
                'win_prob_kenpom': row['win_prob_kenpom_away'],
                'projected_total_kenpom': row['projected_total_kenpom']
            }
            
            transformed_rows.extend([home_row, away_row])
            
        except KeyError as e:
            print(f"KeyError while transforming row: {e}")
            print(f"Row contents: {row}")
    
    if not transformed_rows:
        print("No rows were transformed successfully")
        return pd.DataFrame()
    
    # Create new DataFrame from transformed rows
    new_df = pd.DataFrame(transformed_rows)
    
    print(f"Transform output DataFrame columns: {new_df.columns}")  # Debug print
    
    # Ensure columns are in the requested order
    column_order = [
        'Home Team',
        'Away Team',
        'Team',
        'Game Date',
        'spread_kenpom',
        'win_prob_kenpom',
        'projected_total_kenpom'
    ]
    
    return new_df[column_order]

def get_kenpom_df():
    df = fetch_kenpom()
    df_clean = clean_kenpom(df)
    df_transformed = transform_kenpom_format(df_clean)
    final_df = map_team_names(df_transformed)
    return final_df