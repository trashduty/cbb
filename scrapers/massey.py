from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
import numpy as np

def fetch_massey():
    """
    Fetches college basketball game data from masseyratings.com using Selenium
    """
    options = Options()
    options.headless = True
    
    try:
        driver = webdriver.Firefox(options=options)
        # Use URL with date parameter and CB-D1 filter
        today = datetime.now().strftime("%Y%m%d")
        driver.get(f"https://masseyratings.com/games?dt={today}&id=308932#CB-D1")        
        # Wait for table to load
        wait = WebDriverWait(driver, 10)
                # Get updated table and parse with pandas
        table = driver.find_element(By.ID, "tableflex")
        df = pd.read_html(table.get_attribute('outerHTML'))[0]
        
        # Validate columns
        required_cols = ['Team', 'Pred', 'Pwin', 'Margin']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            print(f"Missing required columns: {missing}")
            return pd.DataFrame()
            
        return df
        
    except Exception as e:
        print(f"Error fetching Massey data: {e}")
        return pd.DataFrame()
        
    finally:
        driver.quit()

def clean_massey(df):
    """
    Cleans the DataFrame by processing team names, scores, probabilities and spreads
    """
    if df.empty:
        return df
        
    # Create a copy
    df_clean = df.copy()
    
    # Filter valid rows (has exactly one @ and reasonable length)
    df_clean = df_clean[
        (df_clean['Team'].str.count('@') == 1) & 
        (df_clean['Team'].str.len() < 40)
    ].copy()
    
    # Split teams
    teams = df_clean['Team'].str.split('@', n=1, expand=True)
    df_clean['Away Team'] = teams[0].str.strip()
    df_clean['Home Team'] = teams[1].str.strip()
    
    # Process win probabilities
    prob_pattern = r'^(\d+)\s*%\s*(\d+)\s*%$'
    probs = df_clean['Pwin'].str.extract(prob_pattern)
    df_clean['Away Team Win Probability'] = pd.to_numeric(probs[0], errors='coerce')
    df_clean['Home Team Win Probability'] = pd.to_numeric(probs[1], errors='coerce')
    
    # Keep only rows with valid probabilities
    df_clean = df_clean.dropna(subset=['Away Team Win Probability', 'Home Team Win Probability'])
    
    # Process predicted scores
    def parse_pred(pred):
        pred = str(pred)
        pred_len = len(pred)
        
        if pred_len == 4:
            away, home = pred[:2], pred[2:]
        elif pred_len == 5:
            if pred[2] == '1':
                away, home = pred[:2], pred[2:]
            else:
                away, home = pred[:3], pred[3:]
        elif pred_len == 6:
            away, home = pred[:3], pred[3:]
        else:
            return None, None
            
        try:
            away_score = int(away)
            home_score = int(home)
            if 0 <= away_score <= 200 and 0 <= home_score <= 200:
                return away_score, home_score
        except ValueError:
            pass
            
        return None, None
    
    # Apply score parsing
    scores = df_clean['Pred'].apply(parse_pred)
    df_clean['Away Score'] = scores.apply(lambda x: x[0])
    df_clean['Home Score'] = scores.apply(lambda x: x[1])
    
    # Keep only rows with valid scores
    df_clean = df_clean.dropna(subset=['Away Score', 'Home Score'])
    
    # Calculate projected total
    df_clean['Projected Total'] = df_clean['Away Score'] + df_clean['Home Score']
    
    # Extract spread
    def extract_spread(margin):
        numbers = re.findall(r'\d+\.?\d*', str(margin))
        return float(numbers[0]) if numbers else None
        
    df_clean['Spread'] = df_clean['Margin'].apply(extract_spread)
    
    # Keep only rows with valid spreads
    df_clean = df_clean.dropna(subset=['Spread'])
    
    # Assign spreads based on predicted scores
    df_clean['Home Team Spread'] = np.where(
        df_clean['Home Score'] > df_clean['Away Score'],
        -df_clean['Spread'],
        df_clean['Spread']
    )
    df_clean['Away Team Spread'] = -df_clean['Home Team Spread']
    
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