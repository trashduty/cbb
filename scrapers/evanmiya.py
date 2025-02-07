# evanmiya.py

from logger_setup import log_scraper_execution
import logging
import os
# from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import numpy as np

@log_scraper_execution
def fetch_evanmiya():
    """Fetches game data from evanmiya.com using Selenium with headless Chrome"""
    logger = logging.getLogger('evanmiya')
    
    # load_dotenv()
    USERNAME = os.getenv("EVANMIYA_USERNAME")
    PASSWORD = os.getenv("EVANMIYA_PASSWORD")

    if not USERNAME or not PASSWORD:
        logger.error("Missing EVANMIYA_USERNAME or EVANMIYA_PASSWORD environment variables")
        return pd.DataFrame()

    logger.info("Initializing Chrome driver with headless options")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        logger.info("Navigating to EvanMiya predictions page")
        driver.get("https://evanmiya.com/?game_predictions")
        wait = WebDriverWait(driver, 60)

        logger.info("Waiting for page load")
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(5)

        # Handle subscription popup
        try:
            logger.info("Attempting to handle subscription popup")
            pop_up = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".sweet-alert.showSweetAlert.visible")))
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "sweet-overlay")))
            logger.info("Successfully handled subscription popup")
        except Exception as e:
            logger.debug(f"No subscription popup found: {str(e)}")

        # Login process
        logger.info("Starting login process")
        login_button = wait.until(EC.element_to_be_clickable((By.ID, "login-login_button")))
        login_button.click()

        email_field = wait.until(EC.visibility_of_element_located((By.ID, "login-email_login")))
        email_field.clear()
        email_field.send_keys(USERNAME)

        password_field = driver.find_element(By.ID, "login-password_login")
        password_field.clear()
        password_field.send_keys(PASSWORD)
        password_field.send_keys(Keys.RETURN)

        time.sleep(5)

        # Verify login
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".far.fa-user")))
        logger.info("Login successful")

        # Navigate and set up page
        logger.info("Setting up page parameters")
        driver.get("https://evanmiya.com/?game_predictions")
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(10)

        # Set page size
        select_element = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "rt-page-size-select")))
        Select(select_element).select_by_visible_text("500")
        time.sleep(5)

        # Set date
        logger.info("Setting date parameters")
        date_input = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, 'input.form-control[title="Date format: yyyy-mm-dd"]')
        ))
        min_date = date_input.get_attribute("data-min-date")
        driver.execute_script("arguments[0].setAttribute('data-max-date', arguments[1]);", date_input, min_date)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", date_input)
        time.sleep(3)

        # Extract table data
        logger.info("Extracting table data")
        data = driver.execute_script("""
            var rows = document.querySelectorAll('div.rt-table .rt-tr-group');
            var data = [];
            rows.forEach(function(row) {
                var cells = row.querySelectorAll('div.rt-td-inner');
                var rowData = [];
                cells.forEach(function(cell) {
                    rowData.push(cell.innerText.trim());
                });
                data.push(rowData);
            });
            return data;
        """)

        # Process extracted data
        processed_data = [row[1:] for row in data if len(row) == 16 and row[0] == '⏵']
        
        columns = [
            'Home', 'Away', 'Home Rank', 'Away Rank', 'Home Score', 'Away Score',
            'Line', 'Vegas Line', 'O/U', 'Vegas O/U', 'Home Win Prob', 'Away Win Prob',
            'Venue', 'Date', 'Time'
        ]

        df = pd.DataFrame(processed_data, columns=columns)
        logger.info(f"Successfully extracted {len(df)} games")
        return df

    except Exception as e:
        logger.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame()

    finally:
        driver.quit()
        logger.info("Chrome driver closed")

@log_scraper_execution
def clean_evanmiya(df):
    """Cleans the DataFrame by processing spreads, win probabilities, and selecting relevant columns"""
    logger = logging.getLogger('evanmiya')
    if df.empty:
        return df

    # Create a copy
    df_clean = df.copy()

    # Rename basic columns
    df_clean = df_clean.rename(columns={
        'Home': 'Home Team',
        'Away': 'Away Team',
        'O/U': 'Projected Total'
    })

    # Process spreads
    df_clean['Home Team Spread'] = df_clean['Line'].astype(float)  # Remove the negation
    df_clean['Away Team Spread'] = -df_clean['Line'].astype(float)  # Negate this instead

    # Process win probabilities
    df_clean['Home Team Win Probability'] = df_clean['Home Win Prob'].str.rstrip('%').astype(float)
    df_clean['Away Team Win Probability'] = df_clean['Away Win Prob'].str.rstrip('%').astype(float)

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


def map_team_names(df):
    """Map team names using crosswalk"""
    crosswalk = pd.read_csv('crosswalk.csv')
    name_map = crosswalk.set_index('evanmiya')['API'].to_dict()

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
def transform_evanmiya_format(df):
    """
    Transforms EvanMiya DataFrame from one row per game to two rows per game
    with team-specific stats
    """
    if df.empty:
        print("Empty DataFrame received in transform_evanmiya_format")
        return df

    # Create empty list to store transformed rows
    transformed_rows = []

    for _, row in df.iterrows():
        try:
            # Create home team row
            home_row = {
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Home Team'],
                # 'Game Date': row.get('Date', None),  # Use get() in case Date column doesn't exist
                'spread_evanmiya': row['Home Team Spread'],
                'win_prob_evanmiya': row['Home Team Win Probability'] / 100,  # Convert percentage to decimal
                'projected_total_evanmiya': float(row['Projected Total'])
            }

            # Create away team row
            away_row = {
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Away Team'],
                'spread_evanmiya': row['Away Team Spread'],
                'win_prob_evanmiya': row['Away Team Win Probability'] / 100,  # Convert percentage to decimal
                'projected_total_evanmiya': float(row['Projected Total'])
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

    # Ensure columns are in consistent order
    column_order = [
        'Home Team',
        'Away Team',
        'Team',
        'spread_evanmiya',
        'win_prob_evanmiya',
        'projected_total_evanmiya'
    ]

    return new_df[column_order]

def get_evanmiya_df():
    df_raw = fetch_evanmiya()
    df_final = clean_evanmiya(df_raw)
    df_final = transform_evanmiya_format(df_final)
    df_final = map_team_names(df_final)
    return df_final

if __name__ == '__main__':
    df_raw = fetch_evanmiya()
    df_final = clean_evanmiya(df_raw)
    print("\nFinal processed data:")
    print(df_final)

    df_final = transform_evanmiya_format(df_final)
    df_final.to_csv('test_evan.csv')
