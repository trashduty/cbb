# /// script
# dependencies = [
#   "pandas",
#   "beautifulsoup4",
#   "numpy",
#   "rich",
#   "selenium",
#   "webdriver-manager",
#   "lxml"
# ]
# ///

import pandas as pd
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.box import MINIMAL
import os
import sys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

console = Console()

# Determine the project root directory to save files correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
data_dir = os.path.join(project_root, 'data')

# Ensure data directory exists
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    print(f"Created data directory: {data_dir}")


def scrape_barttorvik_day(driver, date_str):
    """
    Scrape Barttorvik data for a specific date using Selenium

    Args:
        driver: Selenium WebDriver instance
        date_str: Date in YYYYMMDD format

    Returns:
        DataFrame of games for that date
    """
    url = f"https://www.barttorvik.com/schedule.php?date={date_str}&conlimit="

    try:
        driver.get(url)

        # Wait for page to load - look for team links
        wait = WebDriverWait(driver, 10)
        time.sleep(2)  # Give page time to fully render

        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'lxml')

        games = []

        # Find all table rows
        for row in soup.find_all('tr'):
            # Look for rows with exactly 2 team links
            teams = row.find_all('a', href=lambda x: x and 'team.php' in x)

            if len(teams) != 2:
                continue

            # Look for the T-Rank line link
            line_link = row.find('a', href=lambda x: x and 'trank.php' in x)

            if not line_link:
                continue

            # Extract team names
            away_team = teams[0].text.strip()
            home_team = teams[1].text.strip()

            # Extract line text (e.g., "Duke -6.5, 77-71 (73%)")
            line_text = line_link.text.strip()

            games.append({
                'Home Team': home_team,
                'Away Team': away_team,
                'T-Rank Line': line_text,
                'Game Date': date_str
            })

        return pd.DataFrame(games)

    except Exception as e:
        print(f"  ⚠️ Error scraping date {date_str}: {str(e)}")
        return pd.DataFrame()


def parse_trank_line(line_text):
    """
    Parse T-Rank line text to extract spread, win probability, and projected total

    Example input: "Duke -6.5, 77-71 (73%)"
    Returns: spread=-6.5, win_prob=0.73, total=148
    """
    import re

    # Extract spread (e.g., "Duke -6.5" or "Texas +3.5")
    spread_match = re.search(r'([+-]?\d+\.?\d*)', line_text)
    spread = float(spread_match.group(1)) if spread_match else None

    # Extract win probability (e.g., "(73%)")
    win_prob_match = re.search(r'\((\d+)%\)', line_text)
    win_prob = float(win_prob_match.group(1)) / 100 if win_prob_match else None

    # Extract scores (e.g., "77-71")
    scores_match = re.search(r'(\d+)-(\d+)', line_text)
    if scores_match:
        score1 = float(scores_match.group(1))
        score2 = float(scores_match.group(2))
        total = score1 + score2
    else:
        total = None

    return spread, win_prob, total


def transform_barttorvik_data(df):
    """
    Transform Barttorvik data to standard format (2 rows per game)

    Args:
        df: DataFrame with columns [Home Team, Away Team, T-Rank Line, Game Date]

    Returns:
        DataFrame with columns [Home Team, Away Team, Team, Game Date,
                               spread_barttorvik, win_prob_barttorvik, projected_total_barttorvik]
    """
    if df.empty:
        return pd.DataFrame(columns=[
            'Home Team', 'Away Team', 'Team', 'Game Date',
            'spread_barttorvik', 'win_prob_barttorvik', 'projected_total_barttorvik'
        ])

    transformed_rows = []

    for _, row in df.iterrows():
        home_team = row['Home Team']
        away_team = row['Away Team']
        game_date = row['Game Date']
        line_text = row['T-Rank Line']

        # Parse the line
        spread, win_prob, total = parse_trank_line(line_text)

        # Determine which team is favored based on line text
        # E.g., "Duke -6.5" means Duke is favored by 6.5
        if spread is not None:
            if home_team in line_text.split(',')[0]:
                # Home team is mentioned first in line
                home_spread = spread
                home_win_prob = win_prob
                away_spread = -spread if spread else None
                away_win_prob = 1 - win_prob if win_prob else None
            else:
                # Away team is mentioned first
                away_spread = spread
                away_win_prob = win_prob
                home_spread = -spread if spread else None
                home_win_prob = 1 - win_prob if win_prob else None
        else:
            home_spread = away_spread = None
            home_win_prob = away_win_prob = None

        # Create rows for both teams with both orderings (like other scrapers)
        # Original ordering
        transformed_rows.append({
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': home_team,
            'Game Date': game_date,
            'spread_barttorvik': home_spread,
            'win_prob_barttorvik': home_win_prob,
            'projected_total_barttorvik': total
        })

        transformed_rows.append({
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': away_team,
            'Game Date': game_date,
            'spread_barttorvik': away_spread,
            'win_prob_barttorvik': away_win_prob,
            'projected_total_barttorvik': total
        })

        # Swapped ordering
        transformed_rows.append({
            'Home Team': away_team,
            'Away Team': home_team,
            'Team': away_team,
            'Game Date': game_date,
            'spread_barttorvik': away_spread,
            'win_prob_barttorvik': away_win_prob,
            'projected_total_barttorvik': total
        })

        transformed_rows.append({
            'Home Team': away_team,
            'Away Team': home_team,
            'Team': home_team,
            'Game Date': game_date,
            'spread_barttorvik': home_spread,
            'win_prob_barttorvik': home_win_prob,
            'projected_total_barttorvik': total
        })

    return pd.DataFrame(transformed_rows)


def map_team_names(df, name_map):
    """Map team names using crosswalk"""
    if df.empty:
        return df

    # Track unmapped teams
    unmapped_teams = set()

    def map_name(name):
        if pd.isna(name):
            return name
        mapped = name_map.get(name, name)
        if mapped == name and name not in name_map.values():
            unmapped_teams.add(name)
        return mapped

    df['Home Team'] = df['Home Team'].apply(map_name)
    df['Away Team'] = df['Away Team'].apply(map_name)
    df['Team'] = df['Team'].apply(map_name)

    # Report unmapped teams
    if unmapped_teams:
        console.print("\n[yellow]Unmapped teams and their occurrence count:[/yellow]")
        for team in sorted(unmapped_teams):
            count = ((df['Home Team'] == team) | (df['Away Team'] == team) | (df['Team'] == team)).sum()
            console.print(f"- {team}: {count} occurrences")

    # Drop rows with unmapped teams
    initial_len = len(df)
    df = df[
        df['Home Team'].isin(name_map.values()) &
        df['Away Team'].isin(name_map.values()) &
        df['Team'].isin(name_map.values())
    ].copy()

    dropped = initial_len - len(df)
    if dropped > 0:
        console.print(f"\n[yellow]⚠[/yellow] Dropped {dropped} rows due to mapping issues")

    return df


def get_barttorvik_df(days_ahead=10):
    """
    Main function to scrape Barttorvik data using Selenium

    Args:
        days_ahead: Number of days to scrape (default 10)

    Returns:
        DataFrame with mapped team names
    """
    console.print(f"[cyan]Initializing Barttorvik scraper (Selenium)[/cyan]")

    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    # Install and configure ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        all_games = []
        current_date = datetime.now()

        console.print(f"[cyan]Scraping {days_ahead} days of Barttorvik data[/cyan]")

        for day_offset in range(days_ahead):
            fetch_date = current_date + timedelta(days=day_offset)
            date_str = fetch_date.strftime('%Y%m%d')

            console.print(f"  Fetching {date_str} (day {day_offset + 1}/{days_ahead})")

            df = scrape_barttorvik_day(driver, date_str)

            if not df.empty:
                all_games.append(df)
                console.print(f"    [green]✓[/green] Found {len(df)} games")
            else:
                console.print(f"    [dim]No games found[/dim]")

        # Combine all days
        if all_games:
            combined_df = pd.concat(all_games, ignore_index=True)
            console.print(f"\n[green]✓[/green] Total: {len(combined_df)} games across {days_ahead} days")
        else:
            console.print("[yellow]⚠[/yellow] No games found for any date")
            combined_df = pd.DataFrame()

        # Transform to standard format
        transformed_df = transform_barttorvik_data(combined_df)

        # Map team names
        crosswalk_path = os.path.join(data_dir, 'crosswalk.csv')
        if os.path.exists(crosswalk_path) and not transformed_df.empty:
            console.print("\n[cyan]Mapping team names...[/cyan]")
            crosswalk = pd.read_csv(crosswalk_path)
            name_map = crosswalk.set_index('barttorvik')['API'].to_dict()
            mapped_df = map_team_names(transformed_df, name_map)
        else:
            mapped_df = transformed_df

        # Save to file
        output_path = os.path.join(data_dir, 'bt_mapped.csv')
        mapped_df.to_csv(output_path, index=False)
        console.print(f"\n[green]✓[/green] Saved to: {output_path}")
        console.print(f"Final shape: {mapped_df.shape}")

        return mapped_df

    finally:
        driver.quit()
        console.print("[green]✓[/green] Chrome driver closed")


if __name__ == "__main__":
    df = get_barttorvik_df(days_ahead=10)
    console.print(f"\n[green]✓[/green] Barttorvik scraper completed successfully")
