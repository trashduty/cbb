import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import numpy as np

def fetch_evanmiya():
    """
    Fetches game data from evanmiya.com using Selenium
    """
    # Load environment variables
    load_dotenv()
    
    # Retrieve credentials
    USERNAME = os.getenv("EVANMIYA_USERNAME")
    PASSWORD = os.getenv("EVANMIYA_PASSWORD")
    
    if not USERNAME or not PASSWORD:
        print("Error: Missing EVANMIYA_USERNAME or EVANMIYA_PASSWORD environment variables")
        return pd.DataFrame()

    # Initialize Firefox options
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options)

    try:
        # Navigate to site
        driver.get("https://evanmiya.com/?game_predictions")
        wait = WebDriverWait(driver, 60)
        
        # Wait for page load
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(5)

        # Handle subscription popup
        try:
            pop_up = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".sweet-alert.showSweetAlert.visible")))
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "sweet-overlay")))
        except Exception:
            pass

        # Login process
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
        
        # Navigate to predictions page
        driver.get("https://evanmiya.com/?game_predictions")
        WebDriverWait(driver, 30).until(lambda d: d.execute_script('return document.readyState') == 'complete')
        time.sleep(10)

        # Set page size and date
        select_element = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "rt-page-size-select")))
        Select(select_element).select_by_visible_text("500")
        time.sleep(5)

        date_input = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, 'input.form-control[title="Date format: yyyy-mm-dd"]')
        ))
        min_date = date_input.get_attribute("data-min-date")
        driver.execute_script("arguments[0].setAttribute('data-max-date', arguments[1]);", date_input, min_date)
        driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", date_input)
        time.sleep(3)

        # Extract table data
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

        return pd.DataFrame(processed_data, columns=columns)

    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()
    
    finally:
        driver.quit()

def clean_evanmiya(df):
    """
    Cleans the DataFrame by processing spreads, win probabilities, and selecting relevant columns
    """
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
    df_clean['Home Team Spread'] = -df_clean['Line'].astype(float)
    df_clean['Away Team Spread'] = df_clean['Line'].astype(float)
    
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

