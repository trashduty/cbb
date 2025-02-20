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
from io import StringIO
from logger_setup import log_scraper_execution
import logging
from rich.table import Table
from rich.console import Console
from rich.box import MINIMAL

console = Console()

def fetch_kenpom():
    """
    Fetches game data from kenpom.com for today and tomorrow using Selenium
    """
    logger = logging.getLogger('kenpom')
    
    # Load environment variables
    # load_dotenv()

    # Retrieve credentials
    USERNAME = os.getenv("KENPOM_USERNAME")
    PASSWORD = os.getenv("KENPOM_PASSWORD")

    if not USERNAME or not PASSWORD:
        logger.error("Missing KENPOM_USERNAME or KENPOM_PASSWORD environment variables")
        return pd.DataFrame()

    # Initialize Firefox options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    # Add user agent to avoid detection
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    logger.info("Initializing Chrome driver with headless options")
    driver = webdriver.Chrome(options=chrome_options)

    all_games = []

    try:
        # Navigate to fanmatch page
        logger.info("Navigating to KenPom fanmatch page")
        driver.get('https://kenpom.com/fanmatch.php')
        wait = WebDriverWait(driver, 30)

        # Login
        logger.info("Attempting login")
        email_el = wait.until(EC.presence_of_element_located((By.NAME, 'email')))
        email_el.clear()
        email_el.send_keys(USERNAME)

        pwd_el = wait.until(EC.presence_of_element_located((By.NAME, 'password')))
        pwd_el.clear()
        pwd_el.send_keys(PASSWORD)
        pwd_el.send_keys(Keys.RETURN)
        time.sleep(5)
        logger.info("Login successful")

        # Function to extract date from content header
        def parse_date_from_header():
            header = wait.until(EC.presence_of_element_located((By.ID, 'content-header')))
            header_text = header.text
            logger.debug(f"Header text: {header_text}")

            # Extract date using regex
            date_match = re.search(r'for (.*?) \(', header_text)
            if not date_match:
                logger.warning("Could not find date in header")
                return None

            date_str = date_match.group(1)
            logger.debug(f"Extracted date string: {date_str}")

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
                            logger.error(f"Failed to parse date string: {date_str}")
                            return None

        # Function to extract table and add date
        def extract_table_with_date(date_obj):
            if date_obj is None:
                logger.warning("No valid date provided for table extraction")
                return pd.DataFrame()

            logger.info(f"Extracting table for date: {date_obj.strftime('%Y-%m-%d')}")
            fanmatch_table = wait.until(EC.presence_of_element_located((By.ID, 'fanmatch-table')))
            time.sleep(2)
            table_html = fanmatch_table.get_attribute('outerHTML')
            df = pd.read_html(StringIO(table_html))[0]
            df['Game Date'] = date_obj.strftime('%Y%m%d')
            logger.info(f"Successfully extracted {len(df)} games")
            return df

        # Get today's date and games
        logger.info("Processing today's games")
        today_date = parse_date_from_header()
        if today_date:
            today_games = extract_table_with_date(today_date)
            if not today_games.empty:
                all_games.append(today_games)

        # Find and click tomorrow's link
        try:
            logger.info("Attempting to fetch tomorrow's games")
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
            logger.error(f"Error fetching tomorrow's games: {str(e)}")

        # Combine all games
        if not all_games:
            logger.warning("No games data collected")
            return pd.DataFrame()

        combined_df = pd.concat(all_games, ignore_index=True)
        logger.info(f"Successfully combined {len(combined_df)} total games")
        logger.debug(f"Combined DataFrame columns: {combined_df.columns}")
        return combined_df

    except Exception as e:
        logger.error(f"Error fetching KenPom data: {str(e)}")
        return pd.DataFrame()

    finally:
        driver.quit()
        logger.info("Chrome driver closed")

def map_team_names(df):
    """Map team names using crosswalk and alternate names as fallback"""
    logger = logging.getLogger('kenpom')
    
    # Load crosswalk files
    crosswalk = pd.read_csv('crosswalk.csv')
    name_map = crosswalk.set_index('kenpom')['API'].to_dict()
    alt_map = crosswalk.set_index('kenpom_alt')['API'].to_dict()

    # Create mapping report
    unmapped_teams = {}
    found_in_alt = {}
    
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])
            # Check if team exists in alt_map
            if team in alt_map:
                found_in_alt[team] = alt_map[team]
                # Add to name_map if found in alt_map
                name_map[team] = alt_map[team]

    if unmapped_teams:
        logger.warning("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            logger.warning(f"- {team}: {count} occurrences")
            if team in found_in_alt:
                logger.info(f"  Found in alt_map as: {found_in_alt[team]}")

    # Map using combined mappings
    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)

    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    if len(mapped_df) < original_count:
        logger.warning(f"\nDropped {original_count - len(mapped_df)} rows due to mapping issues")
        
        # Print which teams are still causing drops
        still_unmapped = mapped_df[mapped_df[['Home Team', 'Away Team', 'Team']].isna().any(axis=1)]
        if not still_unmapped.empty:
            logger.warning("\nTeams still causing mapping issues:")
            for col in ['Home Team', 'Away Team', 'Team']:
                problem_teams = still_unmapped[col][still_unmapped[col].isna()].unique()
                if len(problem_teams) > 0:
                    logger.warning(f"\n{col} unmapped values:")
                    for team in problem_teams:
                        logger.warning(f"- {team}")

    logger.info(f"Successfully mapped {len(mapped_df)} games")
    return mapped_df

def clean_kenpom(df):
    """
    Cleans the DataFrame by processing team names, spreads, probabilities and totals
    """
    logger = logging.getLogger('kenpom')
    
    if df.empty:
        logger.warning("Empty DataFrame received in clean_kenpom")
        return df

    logger.debug(f"Input DataFrame columns: {df.columns}")

    # Create a copy
    df_clean = df.copy()

    # Force columns to lower for consistency
    df_clean.columns = df_clean.columns.str.strip().str.lower()

    # Filter rows with valid game information
    df_clean = df_clean[df_clean['game'].str.contains(r'\bat\b|vs\.', case=False, na=False)].copy()
    logger.info(f"Found {len(df_clean)} valid games after filtering")

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
    logger.info("Extracting home and away teams")
    df_clean['teams'] = df_clean['game'].apply(lambda x: extract_teams(x))
    df_clean = df_clean.dropna(subset=['teams'])
    df_clean['Home Team'] = df_clean['teams'].apply(lambda x: x[0])
    df_clean['Away Team'] = df_clean['teams'].apply(lambda x: x[1])

    def clean_team_name(name):
        # Remove leading numbers and dots
        name = re.sub(r'^\d+\s*\.?\s*', '', name)
        # Remove trailing numbers
        name = re.sub(r'\s*\d+$', '', name)
        return name.strip()
    
    logger.info("Cleaning team names")
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

    logger.info("Parsing predictions for spreads and probabilities")
    df_clean['parsed_pred'] = df_clean['prediction'].apply(parse_prediction)
    df_clean = df_clean.dropna(subset=['parsed_pred'])

    def assign_values(row):
        fav_team, scores, win_prob = row['parsed_pred']
        
        # Handle case where parsing failed
        if scores is None:
            return pd.Series({
                'spread_kenpom_home': None,
                'spread_kenpom_away': None,
                'win_prob_kenpom_home': None,
                'win_prob_kenpom_away': None,
                'projected_total_kenpom': None
            })
            
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
            logger.warning(f"Favored team not found in game teams: {row['teams']}, fav_team: {fav_team}")
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
    logger.info("Calculating final values")
    final_cols = df_clean.apply(assign_values, axis=1)
    df_clean = pd.concat([df_clean[['Home Team', 'Away Team', 'game date']], final_cols], axis=1)

    logger.debug(f"Output DataFrame columns: {df_clean.columns}")
    logger.info(f"Successfully cleaned {len(df_clean)} games")
    return df_clean

def transform_kenpom_format(df):
    """
    Transforms KenPom DataFrame from one row per game to two rows per game
    """
    logger = logging.getLogger('kenpom')
    
    if df.empty:
        logger.warning("Empty DataFrame received in transform_kenpom_format")
        return df

    logger.debug(f"Transform input DataFrame columns: {df.columns}")

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
            logger.error(f"KeyError while transforming row: {str(e)}")
            logger.debug(f"Row contents: {row}")

    if not transformed_rows:
        logger.warning("No rows were transformed successfully")
        return pd.DataFrame()

    # Create new DataFrame from transformed rows
    new_df = pd.DataFrame(transformed_rows)

    logger.debug(f"Transform output DataFrame columns: {new_df.columns}")

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

    logger.info(f"Successfully transformed {len(new_df)} rows")
    return new_df[column_order]

@log_scraper_execution
def get_kenpom_df():
    """Main function to fetch and process KenPom data"""
    logger = logging.getLogger('kenpom')
    
    logger.info("Starting KenPom data fetch and processing")
    df = fetch_kenpom()
    
    logger.info("Cleaning KenPom data")
    df_clean = clean_kenpom(df)
    
    logger.info("Transforming data format")
    df_transformed = transform_kenpom_format(df_clean)
    
    logger.info("Mapping team names")
    final_df = map_team_names(df_transformed)
    
    # Create summary table
    summary_table = Table(
        title="KenPom Request Summary",
        show_header=True,
        header_style="bold magenta",
        show_lines=False,
        title_style="bold cyan"
    )
    
    summary_table.add_column("Date", style="cyan")
    summary_table.add_column("Games Found", style="green")
    summary_table.add_column("Unmapped Teams", style="yellow")
    summary_table.add_column("Count", style="red")
    
    # Process each date
    for date in sorted(final_df['Game Date'].unique()):
        date_df = final_df[final_df['Game Date'] == date]
        date_games = len(date_df) // 2  # Divide by 2 since we have 2 rows per game
        
        # Find unmapped teams for this date
        crosswalk = pd.read_csv('crosswalk.csv')
        name_map = crosswalk.set_index('kenpom')['API'].to_dict()
        unmapped = []
        for team in date_df['Team'].unique():
            if team not in name_map:
                unmapped.append(team)
        
        # Add date row with game count and unmapped count
        formatted_date = datetime.strptime(str(date), '%Y%m%d').strftime('%Y-%m-%d')
        unmapped_count = len(unmapped)
        
        if unmapped:
            # First row shows date, game count, and first unmapped team
            summary_table.add_row(
                formatted_date,
                str(date_games),
                unmapped[0] if unmapped else "None",
                str(unmapped_count)
            )
            # Additional rows for remaining unmapped teams
            for team in unmapped[1:]:
                summary_table.add_row("", "", team, "")
            # Add separator after each date's entries
            summary_table.add_row("", "", "", "", style="dim")
        else:
            # If no unmapped teams, just show date and game count
            summary_table.add_row(formatted_date, str(date_games), "None", "0")
            summary_table.add_row("", "", "", "", style="dim")
    
    # Add total row
    total_games = len(final_df) // 2
    total_unmapped = len(set(team for team in final_df['Team'].unique() if team not in name_map))
    summary_table.add_row(
        "Total",
        str(total_games),
        f"{total_games} games after mapping",
        f"{total_unmapped} teams unmapped",
        style="bold"
    )

    console.print(summary_table)

    # Create detailed games table
    games_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_lines=False,
        title_style="bold cyan",
        padding=(0, 1)
    )
    
    games_table.add_column("Date", style="cyan", width=10)
    games_table.add_column("Matchup", style="green", width=65)  # Increased width to accommodate longer names
    games_table.add_column("Spread", style="yellow", width=10)
    games_table.add_column("Win Prob", style="cyan", width=10)
    games_table.add_column("Total", style="magenta", width=10)
    
    # Process each date's games
    current_date = None
    for _, row in final_df.iterrows():
        date = row['Game Date']
        if row['Team'] != row['Home Team']:
            continue  # Skip away team rows
            
        # Add separator row if date changes
        if current_date != date:
            formatted_date = datetime.strptime(str(date), '%Y%m%d').strftime('%m-%d')
            if current_date is not None:
                games_table.add_row("", "", "", "", "")
            games_table.add_row(formatted_date, "=" * 63, "", "", "", style="dim")  # Adjusted separator length
            current_date = date
        
        # Format the data
        spread = f"{row['spread_kenpom']:+.1f}" if pd.notnull(row['spread_kenpom']) else "N/A"
        win_prob = f"{row['win_prob_kenpom']*100:.0f}%" if pd.notnull(row['win_prob_kenpom']) else "N/A"
        total = f"{row['projected_total_kenpom']:.1f}" if pd.notnull(row['projected_total_kenpom']) else "N/A"
        
        # Create matchup string without truncation
        matchup = f"{row['Away Team']} @ {row['Home Team']}"
        
        # Add game row
        games_table.add_row(
            "",
            matchup,
            spread,
            win_prob,
            total
        )
    
    console.print(games_table)
    logger.info(f"[green]✓[/green] Successfully processed {total_games} games from KenPom")
    
    return final_df