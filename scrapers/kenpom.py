import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import numpy as np
import re
import time
from io import StringIO 

def fetch_kenpom():
    """
    Fetches game data from kenpom.com using Selenium
    """
    # Load environment variables
    load_dotenv()
    
    # Retrieve credentials
    USERNAME = os.getenv("KENPOM_USERNAME")
    PASSWORD = os.getenv("KENPOM_PASSWORD")
    
    if not USERNAME or not PASSWORD:
        print("Error: Missing KENPOM_USERNAME or KENPOM_PASSWORD environment variables")
        return pd.DataFrame()
        
    # Initialize Firefox options
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)
    
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
        
        # Wait for table and extract
        fanmatch_table = wait.until(EC.presence_of_element_located((By.ID, 'fanmatch-table')))
        time.sleep(2)
        
        table_html = fanmatch_table.get_attribute('outerHTML')
        # Use StringIO to wrap the HTML string
        raw_df = pd.read_html(StringIO(table_html))[0]
        return raw_df
        
    except Exception as e:
        print(f"Error fetching KenPom data: {e}")
        return pd.DataFrame()
        
    finally:
        driver.quit()

def clean_kenpom(df):
    """
    Cleans the DataFrame by processing team names, spreads, probabilities and totals
    """
    if df.empty:
        return df
        
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
    df_clean['Away Team'] = df_clean['Away Team'].apply(clean_team_name)
    
    # Parse prediction column for spreads and probabilities
    def parse_prediction(pred_str):
        if pd.isna(pred_str):
            return None, None, None
            
        # Extract scores using regex
        score_match = re.search(r'(\d+)-(\d+)', pred_str)
        if not score_match:
            return None, None, None
            
        fav_score = int(score_match.group(1))
        dog_score = int(score_match.group(2))
        
        # Extract win probability
        prob_match = re.search(r'\((\d+(?:\.\d+)?)%\)', pred_str)
        if not prob_match:
            return None, None, None
            
        win_prob = float(prob_match.group(1))
        
        # Determine favored team
        fav_team = clean_team_name(pred_str.split()[0])
        
        return fav_team, (fav_score, dog_score), win_prob
    
    # Apply prediction parsing
    df_clean['parsed_pred'] = df_clean['prediction'].apply(parse_prediction)
    df_clean = df_clean.dropna(subset=['parsed_pred'])
    
    # Extract components and calculate spreads/probabilities
    def assign_values(row):
        fav_team, scores, win_prob = row['parsed_pred']
        fav_score, dog_score = scores
        spread = fav_score - dog_score
        
        # Determine if home or away is favored
        if fav_team == row['Home Team']:
            home_spread = -abs(spread)
            away_spread = abs(spread)
            home_prob = win_prob
            away_prob = 100 - win_prob
        else:
            home_spread = abs(spread)
            away_spread = -abs(spread)
            home_prob = 100 - win_prob
            away_prob = win_prob
            
        total = fav_score + dog_score
        
        return pd.Series({
            'Home Team Spread': home_spread,
            'Away Team Spread': away_spread,
            'Home Team Win Probability': home_prob,
            'Away Team Win Probability': away_prob,
            'Projected Total': total
        })
    
    # Calculate final values
    final_cols = df_clean.apply(assign_values, axis=1)
    df_clean = pd.concat([df_clean[['Home Team', 'Away Team']], final_cols], axis=1)
    
    # Select final columns
    columns = [
        'Home Team',
        'Away Team',
        'Home Team Spread',
        'Away Team Spread',
        'Home Team Win Probability',
        'Away Team Win Probability',
        'Projected Total'
    ]
    
    return df_clean[columns]