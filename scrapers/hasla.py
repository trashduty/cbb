import re
import time
from collections import defaultdict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
from logger_setup import log_scraper_execution
import logging
from rich.table import Table
from rich.console import Console
from datetime import datetime, timedelta

console = Console()

def scrape_hasla():
    """Scrapes data from haslametrics.com and returns a DataFrame"""
    logger = logging.getLogger('hasla')
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    logger.info("[cyan]Initializing Chrome driver with headless options[/cyan]")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        logger.info("[cyan]Navigating to Hasla Metrics page[/cyan]")
        driver.get("https://haslametrics.com/")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "odd")))
        time.sleep(2)

        # Initialize list to store all soups
        all_soups = []
        
        # Get initial page source
        initial_source = driver.page_source
        all_soups.append(BeautifulSoup(initial_source, 'lxml'))
        logger.info("[green]✓[/green] Captured initial day's games")

        try:
            # Get the dropdown element
            dropdown = driver.find_element(By.ID, "cboUpcomingDates")
            current_index = int(dropdown.get_attribute("selectedIndex"))
            
            # Get next two days
            for day_offset in range(1, 3):
                logger.info(f"[cyan]Selecting date offset: {day_offset}[/cyan]")
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
                logger.info(f"[green]✓[/green] Captured games for date offset {day_offset}")
                
        except Exception as e:
            logger.error(f"[red]✗[/red] Error selecting dates: {str(e)}")

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
            logger.debug(f"Cleaned team name: {cleaned}")
            return cleaned

        logger.info("[cyan]Extracting game data from all pages[/cyan]")
        valid_games = []
        row_offset = 0
        
        for soup_idx, soup in enumerate(all_soups):
            games_found = 0
            games_with_spreads = 0
            games_with_totals = 0
            
            current_max_row = max([row_offset] + [row_offset + int(pattern.match(item["id"]).group(1)) 
                                                for item in soup.find_all(id=pattern) if pattern.match(item["id"])])
            
            for item in soup.find_all(id=pattern):
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
                str(games_with_spreads // 2),
                str(games_with_totals // 2)
            )
            
            row_offset = current_max_row + 1

        console.print(summary_table)
        logger.info(f"[green]✓[/green] Found {len(valid_games)} potential valid games across all dates")

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
        
        for row_idx in sorted(valid_games):
            teamA_name = clean_team_name(text_dict[row_idx].get(1, ""))
            teamA_score = score_dict[row_idx].get(1, "")
            teamB_name = clean_team_name(text_dict[row_idx].get(2, ""))
            teamB_score = score_dict[row_idx].get(2, "")

            if not teamA_name or not teamB_name:
                logger.warning(f"[yellow]⚠[/yellow] Skipping row {row_idx} due to missing team name: A='{teamA_name}', B='{teamB_name}'")
                continue

            logger.debug(f"Processing game: {teamA_name} vs {teamB_name} (Scores: {teamA_score}-{teamB_score})")

            # Calculate spread
            spread = None
            if teamA_score and teamB_score:
                try:
                    spread = float(teamA_score) - float(teamB_score)
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
            date_str = (datetime.now() + timedelta(days=game_count//10)).strftime('%m-%d')
            if current_date != date_str:
                if current_date is not None:
                    games_table.add_row("", "", "", "", style="dim")
                games_table.add_row(date_str, "=" * 63, "", "", style="dim")
                current_date = date_str

            matchup = f"{teamB_name} @ {teamA_name}"
            spread_str = f"{spread:+.1f}" if spread is not None else "N/A"
            total_str = f"{total:.1f}" if total is not None else "N/A"
            
            games_table.add_row("", matchup, spread_str, total_str)

            # Add rows for DataFrame
            rows.append({
                'Home Team': teamB_name,
                'Away Team': teamA_name,
                'Team': teamA_name,
                'spread_hasla': -spread if spread is not None else None,
                'win_prob_hasla': None,
                'projected_total_hasla': teamA_total + teamB_total
            })

            rows.append({
                'Home Team': teamB_name,
                'Away Team': teamA_name,
                'Team': teamB_name,
                'spread_hasla': spread,
                'win_prob_hasla': None,
                'projected_total_hasla': teamB_total + teamA_total
            })
            game_count += 1

        console.print(games_table)
        df = pd.DataFrame(rows)
        logger.info(f"[green]✓[/green] Successfully created DataFrame with {game_count} games")
        
        # Log column names and data types
        logger.info("\nDataFrame Info:")
        for col in df.columns:
            non_null = df[col].count()
            dtype = df[col].dtype
            logger.info(f"[cyan]{col}:[/cyan] {non_null} non-null values, dtype: {dtype}")
        
        return df

    except Exception as e:
        logger.error(f"[red]✗[/red] Error scraping Hasla data: {str(e)}")
        return pd.DataFrame()
        
    finally:
        driver.quit()
        logger.info("[green]✓[/green] Chrome driver closed")

def transform_hasla_format(df):
    """
    Transforms the Hasla data into the standard format with two rows per game
    """
    logger = logging.getLogger('hasla')
    
    if df.empty:
        logger.warning("[yellow]⚠[/yellow] Empty DataFrame received in transform_hasla_format")
        return df

    # Log initial state
    logger.info("\n[cyan]Transform Input DataFrame State:[/cyan]")
    logger.info(f"Columns: {df.columns.tolist()}")
    for col in df.columns:
        non_null = df[col].count()
        sample_values = df[col].dropna().head(3).tolist()
        logger.info(f"[green]{col}:[/green] {non_null} non-null values, Sample values: {sample_values}")
    
    # Convert numeric columns to float, replacing empty strings with None
    numeric_cols = ['spread_hasla', 'projected_total_hasla']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        logger.info(f"[cyan]After converting {col}:[/cyan] {df[col].count()} non-null values")

    # Log final state
    logger.info(f"[green]✓[/green] Successfully transformed Hasla data with {len(df)} rows")
    return df
def map_team_names(df):
    """Map team names using crosswalk"""
    logger = logging.getLogger('hasla')
    
    crosswalk = pd.read_csv('crosswalk.csv')
    name_map = crosswalk.set_index('hasla')['API'].to_dict()
    
    # Create mapped dataframe
    mapped_df = df.copy()
    
    # Map the Team column directly just like the others
    mapped_df['Home Team'] = mapped_df['Home Team'].map(name_map)
    mapped_df['Away Team'] = mapped_df['Away Team'].map(name_map)
    mapped_df['Team'] = mapped_df['Team'].map(name_map)

    # Drop rows with missing mappings
    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    
    # Log final state including numeric columns
    logger.info("\n[cyan]Final DataFrame State:[/cyan]")
    for col in mapped_df.columns:
        non_null = mapped_df[col].count()
        dtype = mapped_df[col].dtype
        sample_values = mapped_df[col].dropna().head(3).tolist()
        logger.info(f"[green]{col}:[/green] {non_null} non-null values, dtype: {dtype}, Sample values: {sample_values}")

    if len(mapped_df) < original_count:
        logger.warning(f"[yellow]⚠[/yellow] Dropped {original_count - len(mapped_df)} rows due to mapping issues")

    return mapped_df
@log_scraper_execution
def get_hasla_df():
    """
    Main function to get processed Hasla data in the standard format
    """
    logger = logging.getLogger('hasla')
    
    logger.info("[cyan]Starting Hasla data fetch and processing[/cyan]")
    
    # Scrape the data directly into a DataFrame
    raw_df = scrape_hasla()
    
    if raw_df.empty:
        logger.error("[red]✗[/red] Failed to scrape Hasla data")
        return pd.DataFrame()

    # Transform into standard format
    logger.info("[cyan]Transforming data format[/cyan]")
    transformed_df = transform_hasla_format(raw_df)
    
    # Map team names to match API format
    logger.info("[cyan]Mapping team names[/cyan]")
    final_df = map_team_names(transformed_df)
    
    # Log final output state
    logger.info("\n[cyan]Final Output DataFrame:[/cyan]")
    logger.info(f"Shape: {final_df.shape}")
    logger.info(f"Columns: {final_df.columns.tolist()}")
    for col in ['spread_hasla', 'projected_total_hasla']:
        non_null = final_df[col].count()
        sample_values = final_df[col].dropna().head(3).tolist()
        logger.info(f"[green]{col}:[/green] {non_null} non-null values, Sample values: {sample_values}")
    
    logger.info(f"[green]✓[/green] Completed Hasla processing with {len(final_df)} final rows")
    return final_df

if __name__ == "__main__":
    df = get_hasla_df()
    print(df.head())
