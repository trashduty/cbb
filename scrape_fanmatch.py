# /// script
# dependencies = [
#   "pandas",
#   "selenium",
#   "webdriver-manager",
#   "beautifulsoup4",
#   "python-dotenv"
# ]
# ///
"""
Multi-Date FanMatch Scraper

This script scrapes KenPom FanMatch pages for specific dates to retrieve game results.
It's designed to work with the game_tracker.py system to automatically fetch results
for tracked games across multiple dates.

Key Features:
- Extracts unique game dates from tracked games DataFrame
- Scrapes FanMatch pages for each date using date-specific URLs
- Handles login to KenPom (requires credentials in .env)
- Saves HTML files with proper date naming convention
- Comprehensive logging for debugging
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Set
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Configuration
KENPOM_LOGIN_URL = "https://kenpom.com/"
KENPOM_FANMATCH_BASE = "https://kenpom.com/fanmatch.php"
DEFAULT_WAIT_TIME = 10  # seconds
PAGE_LOAD_DELAY = 2  # seconds after navigation

def log(message, level="INFO"):
    """Print timestamped log message with level"""
    timestamp = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"[{timestamp}] [{level}] {message}")


def get_game_date_from_string(game_time_str: str) -> str:
    """
    Extract date from game time string in format 'Nov 11 07:00PM ET'
    
    Args:
        game_time_str: Game time string like "Nov 11 07:00PM ET"
    
    Returns:
        Date string in YYYY-MM-DD format, or None if parsing fails
    """
    try:
        # Current year for context
        et = pytz.timezone('US/Eastern')
        current_year = datetime.now(et).year
        
        # Remove " ET" suffix and parse
        time_str_clean = game_time_str.replace(' ET', '').strip()
        
        # Parse just the date part (ignore time)
        # Format: "Nov 11 07:00PM" -> extract "Nov 11"
        date_parts = time_str_clean.split()
        if len(date_parts) >= 2:
            month_str = date_parts[0]
            day_str = date_parts[1]
            
            # Parse as datetime
            dt = datetime.strptime(f"{current_year} {month_str} {day_str}", "%Y %b %d")
            return dt.strftime('%Y-%m-%d')
    except (ValueError, IndexError, AttributeError) as e:
        log(f"Error parsing game time '{game_time_str}': {e}", "WARNING")
    
    return None


def extract_unique_game_dates(games_df: pd.DataFrame) -> Set[str]:
    """
    Extract unique game dates from a DataFrame of tracked games
    
    Args:
        games_df: DataFrame with 'Game Time' column
    
    Returns:
        Set of unique date strings in YYYY-MM-DD format
    """
    if games_df.empty or 'Game Time' not in games_df.columns:
        log("No games or 'Game Time' column not found", "WARNING")
        return set()
    
    unique_dates = set()
    
    for game_time in games_df['Game Time'].unique():
        date_str = get_game_date_from_string(game_time)
        if date_str:
            unique_dates.add(date_str)
    
    log(f"Extracted {len(unique_dates)} unique game dates: {sorted(unique_dates)}")
    return unique_dates


def setup_selenium_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Set up and return a Selenium Chrome WebDriver
    
    Args:
        headless: Whether to run browser in headless mode
    
    Returns:
        Configured Chrome WebDriver instance
    """
    log("Setting up Selenium Chrome driver...")
    
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument('--headless=new')
    
    # Additional options for stability
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    
    # Create driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    log("Selenium driver ready")
    return driver


def login_to_kenpom(driver: webdriver.Chrome) -> bool:
    """
    Log in to KenPom using credentials from environment variables
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        True if login successful, False otherwise
    """
    email = os.getenv('EMAIL')
    password = os.getenv('PASSWORD')
    
    if not email or not password:
        log("KenPom credentials not found in environment variables", "ERROR")
        log("Please set EMAIL and PASSWORD in .env file", "ERROR")
        return False
    
    log("Logging in to KenPom...")
    
    try:
        # Navigate to login page
        driver.get(KENPOM_LOGIN_URL)
        time.sleep(PAGE_LOAD_DELAY)
        
        # Find and fill login form
        wait = WebDriverWait(driver, DEFAULT_WAIT_TIME)
        
        # Look for email input (try multiple possible selectors)
        try:
            email_input = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
        except TimeoutException:
            try:
                email_input = driver.find_element(By.ID, "email")
            except:
                email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
        
        email_input.clear()
        email_input.send_keys(email)
        
        # Find password input
        try:
            password_input = driver.find_element(By.NAME, "password")
        except:
            try:
                password_input = driver.find_element(By.ID, "password")
            except:
                password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        
        password_input.clear()
        password_input.send_keys(password)
        
        # Find and click submit button
        try:
            submit_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
        except:
            try:
                submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except:
                submit_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        
        submit_button.click()
        
        # Wait for login to complete
        time.sleep(PAGE_LOAD_DELAY)
        
        # Check if login was successful by looking for logout link or user menu
        try:
            # Look for indicators of successful login
            wait.until(
                EC.presence_of_element_located((By.LINK_TEXT, "Logout"))
            )
            log("Successfully logged in to KenPom")
            return True
        except TimeoutException:
            log("Login may have failed - could not find logout link", "WARNING")
            # Continue anyway - might still work
            return True
            
    except Exception as e:
        log(f"Error during login: {e}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")
        return False


def scrape_fanmatch_for_date(driver: webdriver.Chrome, date_str: str, output_dir: str) -> bool:
    """
    Scrape FanMatch page for a specific date and save HTML
    
    Args:
        driver: Selenium WebDriver instance
        date_str: Date in YYYY-MM-DD format
        output_dir: Directory to save HTML file
    
    Returns:
        True if successful, False otherwise
    """
    # Construct URL with date parameter
    url = f"{KENPOM_FANMATCH_BASE}?d={date_str}"
    
    log(f"Scraping FanMatch for date {date_str}...")
    log(f"URL: {url}", "DEBUG")
    
    try:
        # Navigate to the page
        driver.get(url)
        time.sleep(PAGE_LOAD_DELAY)
        
        # Wait for table to load
        wait = WebDriverWait(driver, DEFAULT_WAIT_TIME)
        try:
            wait.until(
                EC.presence_of_element_located((By.ID, "fanmatch-table"))
            )
        except TimeoutException:
            log(f"FanMatch table not found for date {date_str} - page may not have loaded", "WARNING")
            # Continue anyway to save what we got
        
        # Get page HTML
        html_content = driver.page_source
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Save HTML file with date in filename
        filename = f"fanmatch-{date_str}.html"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        log(f"Saved FanMatch HTML to {filepath}")
        return True
        
    except Exception as e:
        log(f"Error scraping FanMatch for date {date_str}: {e}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")
        return False


def scrape_multiple_fanmatch_dates(dates: Set[str], output_dir: str, headless: bool = True) -> int:
    """
    Scrape FanMatch pages for multiple dates
    
    Args:
        dates: Set of date strings in YYYY-MM-DD format
        output_dir: Directory to save HTML files
        headless: Whether to run browser in headless mode
    
    Returns:
        Number of dates successfully scraped
    """
    if not dates:
        log("No dates to scrape", "WARNING")
        return 0
    
    log(f"Starting multi-date FanMatch scraping for {len(dates)} dates...")
    
    driver = None
    success_count = 0
    
    try:
        # Set up Selenium driver
        driver = setup_selenium_driver(headless=headless)
        
        # Login to KenPom
        if not login_to_kenpom(driver):
            log("Failed to login to KenPom - aborting scraping", "ERROR")
            return 0
        
        # Scrape each date
        for date_str in sorted(dates):
            if scrape_fanmatch_for_date(driver, date_str, output_dir):
                success_count += 1
            
            # Small delay between requests to be respectful
            time.sleep(1)
        
        log(f"Successfully scraped {success_count}/{len(dates)} dates")
        
    except Exception as e:
        log(f"Error during multi-date scraping: {e}", "ERROR")
        import traceback
        log(f"Traceback: {traceback.format_exc()}", "ERROR")
        
    finally:
        # Clean up
        if driver:
            try:
                driver.quit()
                log("Closed Selenium driver")
            except:
                pass
    
    return success_count


def scrape_fanmatch_for_tracked_games(
    spread_games_df: pd.DataFrame,
    total_games_df: pd.DataFrame,
    output_dir: str,
    headless: bool = True
) -> int:
    """
    Main function to scrape FanMatch data for all tracked games
    
    Args:
        spread_games_df: DataFrame of spread games with 'Game Time' column
        total_games_df: DataFrame of total games with 'Game Time' column
        output_dir: Directory to save HTML files
        headless: Whether to run browser in headless mode
    
    Returns:
        Number of dates successfully scraped
    """
    log("=" * 80)
    log("MULTI-DATE FANMATCH SCRAPING")
    log("=" * 80)
    
    # Extract unique dates from both DataFrames
    all_dates = set()
    
    if not spread_games_df.empty:
        spread_dates = extract_unique_game_dates(spread_games_df)
        all_dates.update(spread_dates)
    
    if not total_games_df.empty:
        total_dates = extract_unique_game_dates(total_games_df)
        all_dates.update(total_dates)
    
    if not all_dates:
        log("No valid dates found in tracked games", "WARNING")
        return 0
    
    log(f"Total unique dates to scrape: {len(all_dates)}")
    log(f"Dates: {sorted(all_dates)}")
    
    # Scrape all dates
    success_count = scrape_multiple_fanmatch_dates(all_dates, output_dir, headless=headless)
    
    log("=" * 80)
    log(f"SCRAPING COMPLETE: {success_count}/{len(all_dates)} dates scraped successfully")
    log("=" * 80)
    
    return success_count


def main():
    """
    Main function for standalone testing
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape KenPom FanMatch data for specific dates')
    parser.add_argument('--dates', nargs='+', help='Dates in YYYY-MM-DD format')
    parser.add_argument('--output-dir', default='kenpom-data', help='Output directory for HTML files')
    parser.add_argument('--no-headless', action='store_true', help='Run browser in visible mode')
    
    args = parser.parse_args()
    
    if not args.dates:
        log("No dates provided. Please specify dates with --dates", "ERROR")
        sys.exit(1)
    
    dates = set(args.dates)
    success_count = scrape_multiple_fanmatch_dates(dates, args.output_dir, headless=not args.no_headless)
    
    if success_count == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
