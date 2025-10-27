# /// script
# dependencies = [
#   "pandas",
#   "requests",
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
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import numpy as np
from rich.table import Table
from rich.console import Console
from datetime import datetime, timedelta
import os
import re
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

def scrape_hasla():
    """Scrapes data from haslametrics.com and returns a DataFrame"""
    print("[cyan]Initializing Chrome driver with headless options[/cyan]")
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Install and configure ChromeDriver - fixed initialization
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        print("[cyan]Navigating to Hasla Metrics page[/cyan]")
        driver.get("https://haslametrics.com/")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "odd")))
        time.sleep(2)

        # Initialize list to store all soups
        all_soups = []
        
        # Get initial page source
        initial_source = driver.page_source
        all_soups.append(BeautifulSoup(initial_source, 'lxml'))
        print("[green]✓[/green] Captured initial day's games")

        try:
            # Get the dropdown element
            dropdown = driver.find_element(By.ID, "cboUpcomingDates")
            current_index = int(dropdown.get_attribute("selectedIndex"))
            
            # Get next two days
            for day_offset in range(1, 3):
                print(f"[cyan]Selecting date offset: {day_offset}[/cyan]")
                new_index = current_index + day_offset
                
                # Select next date and trigger refresh
                driver.execute_script(
                    "document.getElementById('cboUpcomingDates').selectedIndex = arguments[0]; "
                    "refreshUpcomingGames();", 
                    new_index
                )
                time.sleep(2)  # Wait for update
                
                # Get updated page source and add to soups
                next_day_source = driver.page_source
                all_soups.append(BeautifulSoup(next_day_source, 'lxml'))
                print(f"[green]✓[/green] Captured games for date offset {day_offset}")
                
        except Exception as e:
            print(f"[red]✗[/red] Error selecting dates: {str(e)}")

        # Create summary table
        summary_table = Table(
            title="Hasla Metrics Data Summary",
            show_header=True,
            header_style="bold magenta",
            show_lines=False,
            title_style="bold cyan"
        )
        
        summary_table.add_column("Date", style="cyan")
        summary_table.add_column("Games Found", style="green")
        summary_table.add_column("Games with Spreads", style="yellow")
        summary_table.add_column("Games with Totals", style="magenta")

        # Regex to match either "tdUpcoming_x_y" or "tdUpcoming_x_y_sc"
        pattern = re.compile(r'^tdUpcoming_(\d+)_(\d+)(?:_sc)?$')

        # Dictionaries for storing text
        text_dict = defaultdict(dict)
        score_dict = defaultdict(dict)

        def clean_team_name(name):
            if not name or not name.strip():
                return None
            cleaned = re.sub(r'\d+\s*', '', name).strip()
            if not cleaned:
                return None
            return cleaned

        print("[cyan]Extracting game data from all pages[/cyan]")
        valid_games = []
        row_offset = 0
        
        for soup_idx, soup in enumerate(all_soups):
            games_found = 0
            games_with_spreads = 0
            games_with_totals = 0
            
            # Find all elements with id matching the pattern
            game_elements = soup.find_all(id=lambda x: x and pattern.match(x))
            
            if not game_elements:
                print(f"[yellow]⚠[/yellow] No game elements found on page {soup_idx+1}")
                continue
                
            # Calculate current max row with valid ids
            max_rows = [row_offset]
            for item in game_elements:
                match = pattern.match(item["id"])
                if match:
                    max_rows.append(row_offset + int(match.group(1)))
            
            current_max_row = max(max_rows)
            
            for item in game_elements:
                match = pattern.match(item["id"])
                if not match:
                    continue
                    
                row_idx = row_offset + int(match.group(1))
                col_idx = int(match.group(2))

                if item["id"].endswith("_sc"):
                    score = item.get_text(strip=True)
                    score_dict[row_idx][col_idx] = score
                    if score:
                        games_with_totals += 1
                else:
                    text = item.get_text(strip=True)
                    if text:
                        text_dict[row_idx][col_idx] = text
                        if row_idx not in valid_games:
                            valid_games.append(row_idx)
                            games_found += 1

            # Add row to summary table
            date = (datetime.now() + timedelta(days=soup_idx)).strftime('%Y-%m-%d')
            summary_table.add_row(
                date,
                str(games_found // 2),  # Divide by 2 since each game has two teams
                str(games_with_spreads),
                str(games_with_totals // 2)
            )
            
            row_offset = current_max_row + 1

        console.print(summary_table)
        print(f"[green]✓[/green] Found {len(valid_games)} potential valid games across all dates")

        # Create games table
        games_table = Table(
            show_header=True,
            header_style="bold magenta",
            show_lines=False,
            title_style="bold cyan",
            padding=(0, 1)
        )
        
        games_table.add_column("Date", style="cyan", width=10)
        games_table.add_column("Matchup", style="green", width=65)
        games_table.add_column("Spread", style="yellow", width=10)
        games_table.add_column("Total", style="magenta", width=10)

        rows = []
        game_count = 0
        current_date = None
        
        # Store game date for each entry
        game_dates = {}
        
        for soup_idx, soup in enumerate(all_soups):
            date = (datetime.now() + timedelta(days=soup_idx)).strftime('%Y%m%d')
            for row_idx in valid_games:
                if row_idx in text_dict:
                    game_dates[row_idx] = date
        
        for row_idx in sorted(valid_games):
            teamA_name = clean_team_name(text_dict[row_idx].get(1, ""))
            teamA_score = score_dict[row_idx].get(1, "")
            teamB_name = clean_team_name(text_dict[row_idx].get(2, ""))
            teamB_score = score_dict[row_idx].get(2, "")
            game_date = game_dates.get(row_idx, (datetime.now()).strftime('%Y%m%d'))

            if not teamA_name or not teamB_name:
                print(f"[yellow]⚠[/yellow] Skipping row {row_idx} due to missing team name: A='{teamA_name}', B='{teamB_name}'")
                continue

            print(f"Processing game: {teamA_name} vs {teamB_name} (Scores: {teamA_score}-{teamB_score})")

            # Calculate spread
            spread = None
            if teamA_score and teamB_score:
                try:
                    spread = float(teamB_score) - float(teamA_score)
                    spread = round(spread, 1)
                except ValueError:
                    spread = None

            # Convert scores to float or None
            try:
                teamA_total = float(teamA_score) if teamA_score else None
                teamB_total = float(teamB_score) if teamB_score else None
                total = teamA_total + teamB_total if teamA_total is not None and teamB_total is not None else None
            except ValueError:
                teamA_total = None
                teamB_total = None
                total = None

            # Add game to table
            display_date = datetime.strptime(game_date, '%Y%m%d').strftime('%m-%d')
            if current_date != display_date:
                if current_date is not None:
                    games_table.add_row("", "", "", "")
                games_table.add_row(display_date, "=" * 63, "", "", style="dim")
                current_date = display_date

            matchup = f"{teamB_name} @ {teamA_name}"
            spread_str = f"{spread:+.1f}" if spread is not None else "N/A"
            total_str = f"{total:.1f}" if total is not None else "N/A"
            
            games_table.add_row("", matchup, spread_str, total_str)

            # Add rows for DataFrame - original ordering
            rows.append({
                'Home Team': teamA_name,
                'Away Team': teamB_name,
                'Team': teamA_name,
                'Game Date': game_date,
                'spread_hasla': spread if spread is not None else None,
                'win_prob_hasla': None,  # Hasla doesn't provide win probability
                'projected_total_hasla': total
            })

            rows.append({
                'Home Team': teamA_name,
                'Away Team': teamB_name,
                'Team': teamB_name,
                'Game Date': game_date,
                'spread_hasla': -spread if spread is not None else None,
                'win_prob_hasla': None,  # Hasla doesn't provide win probability
                'projected_total_hasla': total
            })

            # Add rows for DataFrame - swapped ordering
            rows.append({
                'Home Team': teamB_name,
                'Away Team': teamA_name,
                'Team': teamB_name,
                'Game Date': game_date,
                'spread_hasla': -spread if spread is not None else None,
                'win_prob_hasla': None,  # Hasla doesn't provide win probability
                'projected_total_hasla': total
            })

            rows.append({
                'Home Team': teamB_name,
                'Away Team': teamA_name,
                'Team': teamA_name,
                'Game Date': game_date,
                'spread_hasla': spread if spread is not None else None,
                'win_prob_hasla': None,  # Hasla doesn't provide win probability
                'projected_total_hasla': total
            })

            game_count += 1

        console.print(games_table)
        df = pd.DataFrame(rows)
        print(f"[green]✓[/green] Successfully created DataFrame with {game_count} games")
        
        # Log column names and data types
        print("\nDataFrame Info:")
        for col in df.columns:
            non_null = df[col].count()
            dtype = df[col].dtype
            print(f"[cyan]{col}:[/cyan] {non_null} non-null values, dtype: {dtype}")
        
        return df

    except Exception as e:
        print(f"[red]✗[/red] Error scraping Hasla data: {str(e)}")
        return pd.DataFrame()
        
    finally:
        driver.quit()
        print("[green]✓[/green] Chrome driver closed")

def map_team_names(df):
    """Map team names using crosswalk"""
    if df.empty:
        print("[yellow]⚠[/yellow] Empty DataFrame received in map_team_names")
        return df

    crosswalk_path = os.path.join(data_dir, 'crosswalk.csv')
    if not os.path.exists(crosswalk_path):
        print(f"[red]✗[/red] Crosswalk file not found at {crosswalk_path}")
        return df
        
    crosswalk = pd.read_csv(crosswalk_path)
    
    # Create a mapping from hasla names to API names
    # We'll assume the crosswalk.csv has columns 'hasla' and 'API'
    # If not, we'll adapt to what's available
    
    if 'hasla' in crosswalk.columns and 'API' in crosswalk.columns:
        name_map = crosswalk.set_index('hasla')['API'].to_dict()
    else:
        # If no hasla column, we'll use barttorvik column as a fallback
        # since team names might be similar
        print("[yellow]⚠[/yellow] No 'hasla' column in crosswalk, using 'barttorvik' as fallback")
        if 'barttorvik' in crosswalk.columns and 'API' in crosswalk.columns:
            name_map = crosswalk.set_index('barttorvik')['API'].to_dict()
        else:
            print("[red]✗[/red] Could not find appropriate mapping columns in crosswalk file")
            return df
    
    # Create unmapped teams report
    unmapped_teams = {}
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])

    if unmapped_teams:
        print("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            print(f"- {team}: {count} occurrences")
    
    # Map team names to API format
    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)

    # Drop rows with missing mappings
    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    
    if len(mapped_df) < original_count:
        print(f"[yellow]⚠[/yellow] Dropped {original_count - len(mapped_df)} rows due to mapping issues")

    # Report final DataFrame state
    print("\n[cyan]Final DataFrame State:[/cyan]")
    for col in mapped_df.columns:
        non_null = mapped_df[col].count()
        dtype = mapped_df[col].dtype
        print(f"[green]{col}:[/green] {non_null} non-null values, dtype: {dtype}")

    return mapped_df

if __name__ == "__main__":
    print("=== Starting Hasla scraper ===")
    
    # Scrape data
    df = scrape_hasla()
    
    if df.empty:
        print("[yellow]⚠[/yellow] No games found in Hasla scraper")
        # Create empty DataFrame with correct columns
        df = pd.DataFrame(columns=[
            'Home Team', 'Away Team', 'Team', 'Game Date',
            'spread_hasla', 'win_prob_hasla', 'projected_total_hasla'
        ])
        # Save empty DataFrame
        output_file = os.path.join(data_dir, 'hasla_mapped.csv')
        df.to_csv(output_file, index=False)
        print(f"[green]✓[/green] Saved empty Hasla data to: {output_file}")
        print(f"Final dataframe shape: {df.shape}")
        print("=== Hasla scraper completed with empty dataset ===")
        sys.exit(0)  # Exit with success code
        
    # Clean and transform data
    print("\n[cyan]Mapping team names...[/cyan]")
    mapped_df = map_team_names(df)
    
    # Sort the DataFrame by Game Date
    print("\n[cyan]Sorting DataFrame by Game Date...[/cyan]")
    mapped_df['Game Date'] = pd.to_datetime(mapped_df['Game Date'], format='%Y%m%d')
    mapped_df = mapped_df.sort_values(by='Game Date')
    # Convert back to string format for consistency
    mapped_df['Game Date'] = mapped_df['Game Date'].dt.strftime('%Y%m%d')
    print(f"[green]✓[/green] DataFrame sorted by Game Date")
    
    # Save output to CSV
    output_file = os.path.join(data_dir, 'hasla_mapped.csv')
    mapped_df.to_csv(output_file, index=False)
    print(f"[green]✓[/green] Saved Hasla data to: {output_file}")
    
    print(f"Final dataframe shape: {mapped_df.shape}")
    print("=== Hasla scraper completed successfully ===")
