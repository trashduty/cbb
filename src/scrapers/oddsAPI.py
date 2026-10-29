# /// script
# dependencies = [
#   "pandas",
#   "requests",
#   "numpy",
#   "rich",
#   "python-dotenv",
#   "pytz",
#   "openpyxl"
# ]
# ///

import os
import sys
import pandas as pd
import requests
import numpy as np
from datetime import datetime, timedelta
import pytz
from pytz import timezone
from statistics import median
from rich.console import Console
from rich.table import Table
from rich.box import MINIMAL
from rich import print as rprint
from rich.logging import RichHandler
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("rich")
console = Console()

# Bookmakers to fetch from The Odds API (5 major US books)
ALLOWED_BOOKMAKERS = ["draftkings", "fanduel", "betmgm", "caesars", "espnbet"]
BOOKMAKERS_PARAM = ",".join(ALLOWED_BOOKMAKERS)

# Determine the project root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
data_dir = os.path.join(project_root, 'data')

# Ensure data directory exists
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    logger.info(f"Created data directory: {data_dir}")

# Load environment variables
load_dotenv()

def get_odds_data(sport="basketball_ncaab", region="us", markets="h2h,spreads,totals"):
    """
    Fetches odds data from the API for specified sport and markets.
    Only returns games that haven't started yet.
    """
    key = os.getenv("ODDS_API_KEY")
    if not key:
        logger.error("[red]✗[/red] ODDSAPI key not found in environment variables.")
        raise ValueError("ODDSAPI key not found in environment variables.")

    base_url = "https://api.the-odds-api.com"
    odds_url = f"{base_url}/v4/sports/{sport}/odds/?apiKey={key}&bookmakers={BOOKMAKERS_PARAM}&markets={markets}&oddsFormat=american"

    try:
        logger.info(f"[cyan]Fetching odds data for {sport}[/cyan]")
        response = requests.get(odds_url)
        response.raise_for_status()
        data = response.json()
        
        if data:
            # Log raw timestamps from API
            logger.info("\n[cyan]Sample raw timestamps from API:[/cyan]")
            for game in data[:3]:
                logger.info(f"Game: {game['away_team']} @ {game['home_team']}")
                logger.info(f"Raw timestamp: {game['commence_time']}")
            
            # Note: Don't filter started games here - let filter_started_games.py handle it
            # so game snapshots can be captured before removal

            # Create a rich table to display the data
            table = Table(
                title=f"OddsAPI Request ({len(data)} games)",
                show_header=True,
                header_style="bold magenta",
                show_lines=False,
                title_style="bold cyan",
                padding=(0, 1),
                box=MINIMAL
            )
            
            # Add columns
            table.add_column("Date", style="cyan", width=5)
            table.add_column("Time", style="cyan", width=7)
            table.add_column("Matchup", style="green", width=60)
            
            # Sort games by time
            sorted_games = sorted(data, key=lambda x: x['commence_time'])
            
            # Track date changes for visual separation
            current_date = None
            
            # Add rows for each game
            for game in sorted_games:
                # Convert UTC to ET and format time
                game_time = datetime.strptime(game['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
                # Subtract 5 hours for ET
                et_time = game_time - timedelta(hours=5)
                date_str = et_time.strftime('%m-%d')
                time_str = et_time.strftime('%I:%M%p').lstrip('0').lower()
                
                # Add separator row if date changes
                if current_date != date_str:
                    if current_date is not None:
                        table.add_row("", "", "─" * 60, style="dim")
                    current_date = date_str
                
                # Format matchup more compactly
                matchup = f"{game['away_team']} @ {game['home_team']}"
                
                # Color code based on conference/matchup importance
                style = get_matchup_style(game['home_team'], game['away_team'])
                
                table.add_row(date_str, time_str, matchup, style=style)
            
            # Log the table
            console.print(table)
            logger.info(f"[green]✓[/green] Successfully fetched {len(data)} upcoming games from Odds API")
        
        return data
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"[red]✗[/red] HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        logger.error(f"[red]✗[/red] Error occurred: {err}")
        return None

def get_matchup_style(home_team, away_team):
    """
    Returns a style string based on the matchup importance/conference.
    Add conference-specific or rivalry-specific styling here.
    """
    # Example conference/matchup styling - expand this based on your needs
    power_conferences = ['Kentucky', 'North Carolina', 'Duke', 'Kansas', 'UCLA']
    if any(team in power_conferences for team in [home_team, away_team]):
        return "bold yellow"
    return None

def american_odds_to_implied_probability(odds):
    """
    Convert American odds to implied probability
    
    Args:
        odds (float): American odds (positive or negative)
        
    Returns:
        float: Implied probability between 0 and 1
    """
    if not odds or pd.isna(odds):
        return None
    
    try:
        odds = float(odds)
        if odds > 0:
            return 100 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    except (ValueError, TypeError):
        return None

def devig_moneyline_odds(home_odds, away_odds):
    """
    Remove the vig from moneyline odds using the basic method of proportionally 
    adjusting implied probabilities to sum to 1.
    
    Args:
        home_odds (float): American odds for home team
        away_odds (float): American odds for away team
        
    Returns:
        tuple: (devigged home probability, devigged away probability)
    """
    # Convert to implied probabilities 
    home_prob = american_odds_to_implied_probability(home_odds)
    away_prob = american_odds_to_implied_probability(away_odds)
    
    if home_prob is None or away_prob is None:
        return None, None
        
    # Calculate sum of probabilities (with vig)
    total_prob = home_prob + away_prob
    
    # Remove the vig by proportionally adjusting probabilities to sum to 1
    devigged_home = home_prob / total_prob
    devigged_away = away_prob / total_prob
    
    return devigged_home, devigged_away

def get_moneyline_odds(data):
    """
    Processes moneyline odds into a DataFrame with two rows per game (home and away teams),
    using the median price across all available bookmakers and includes devigged probabilities.
    Also extracts DraftKings-specific values for opening odds.
    Only includes games where both home and away prices are available for proper devigging.
    """
    # Dictionary to store all moneylines for each team in each game
    moneyline_dict = {}
    # Dictionary to store DraftKings-specific moneylines
    dk_moneyline_dict = {}

    for game in data:
        game_time = game.get('commence_time')  # Keep original ISO format
        home_team = game.get('home_team')
        away_team = game.get('away_team')

        if not all([game_time, home_team, away_team]):
            continue

        # Use game time + teams as unique identifier
        game_key = f"{game_time}_{home_team}_vs_{away_team}"

        # Initialize empty lists to hold moneylines from each bookmaker
        moneyline_dict.setdefault((game_key, 'home'), [])
        moneyline_dict.setdefault((game_key, 'away'), [])
        # Initialize DraftKings tracking
        dk_moneyline_dict.setdefault((game_key, 'home'), None)
        dk_moneyline_dict.setdefault((game_key, 'away'), None)

        # Collect all moneylines from each sportsbook
        for bookmaker in game.get('bookmakers', []):
            sportsbook = bookmaker.get('title')
            sportsbook_key = bookmaker.get('key')
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'h2h':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        team_name = outcome.get('name')
                        price = outcome.get('price')

                        if team_name == home_team and price is not None:
                            moneyline_dict[(game_key, 'home')].append(price)
                            # Track DraftKings specifically
                            if sportsbook_key == 'draftkings':
                                dk_moneyline_dict[(game_key, 'home')] = price
                        elif team_name == away_team and price is not None:
                            moneyline_dict[(game_key, 'away')].append(price)
                            # Track DraftKings specifically
                            if sportsbook_key == 'draftkings':
                                dk_moneyline_dict[(game_key, 'away')] = price

    # Build final records with median prices and devigged probabilities
    h2h_records = []
    for game_key in set(k[0] for k in moneyline_dict.keys()):
        home_prices = moneyline_dict.get((game_key, 'home'), [])
        away_prices = moneyline_dict.get((game_key, 'away'), [])
        
        # Skip games where we don't have both home and away prices
        if not home_prices or not away_prices:
            logger.info(f"[yellow]⚠[/yellow] Skipping game {game_key} due to missing moneyline prices")
            continue
        home_probs = [american_odds_to_implied_probability(price) for price in home_prices]
        away_probs = [american_odds_to_implied_probability(price) for price in away_prices]

        med_home_prob = median([p for p in home_probs if p is not None]) if any(p is not None for p in home_probs) else None
        med_away_prob = median([p for p in away_probs if p is not None]) if any(p is not None for p in away_probs) else None

        if med_home_prob is None or med_away_prob is None:
            continue

        # Convert back to American odds
        def implied_probability_to_american_odds(prob):
            if prob >= 0.5:
                return -1 * (prob * 100)/(1 - prob)
            else:
                return (100 - prob * 100)/prob

        med_home_price = implied_probability_to_american_odds(med_home_prob)
        med_away_price = implied_probability_to_american_odds(med_away_prob)
        # Calculate devigged probabilities
        devigged_home_prob, devigged_away_prob = devig_moneyline_odds(med_home_price, med_away_price)

        # Parse game info from the key
        game_time, teams = game_key.split('_', 1)
        home_team, away_team = teams.split('_vs_')

        # Get DraftKings-specific moneylines
        dk_home_ml = dk_moneyline_dict.get((game_key, 'home'))
        dk_away_ml = dk_moneyline_dict.get((game_key, 'away'))

        # Add home team record
        h2h_records.append({
            'Game Time': game_time,  # Keep ISO format
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': home_team,
            'Moneyline': med_home_price,
            'Devigged Probability': devigged_home_prob,
            'DK_Moneyline': dk_home_ml,
            'Sportsbook': 'CONSENSUS'
        })

        # Add away team record
        h2h_records.append({
            'Game Time': game_time,  # Keep ISO format
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': away_team,
            'Moneyline': med_away_price,
            'Devigged Probability': devigged_away_prob,
            'DK_Moneyline': dk_away_ml,
            'Sportsbook': 'CONSENSUS'
        })

    return pd.DataFrame(h2h_records)

def get_spread_odds(data):
    """
    Processes spread odds into a DataFrame with two rows per game (home and away teams),
    using the median of all available sportsbooks.
    Also extracts DraftKings-specific values for opening odds.
    """
    # Dictionary to store all spreads and prices for each team in each game
    spread_dict = {}
    # Dictionary to store DraftKings-specific spreads
    dk_spread_dict = {}

    # Add debugging for raw data
    logger.info("[cyan]Processing spread odds from API data[/cyan]")

    for game in data:
        game_time = game.get('commence_time')
        home_team = game.get('home_team')
        away_team = game.get('away_team')

        if not all([game_time, home_team, away_team]):
            continue

        # Use game time + teams as unique identifier
        game_key = f"{game_time}_{home_team}_vs_{away_team}"

        # Initialize empty lists to hold spreads and prices from each bookmaker
        spread_dict.setdefault((game_key, 'home'), {'points': [], 'prices': []})
        spread_dict.setdefault((game_key, 'away'), {'points': [], 'prices': []})
        # Initialize DraftKings tracking
        dk_spread_dict.setdefault((game_key, 'home'), {'point': None, 'price': None})
        dk_spread_dict.setdefault((game_key, 'away'), {'point': None, 'price': None})

        # Collect spreads from each sportsbook
        for bookmaker in game.get('bookmakers', []):
            sportsbook_key = bookmaker.get('key')
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'spreads':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        team_name = outcome.get('name')
                        point = outcome.get('point')
                        price = outcome.get('price')

                        if team_name == home_team and point is not None and price is not None:
                            spread_dict[(game_key, 'home')]['points'].append(point)
                            spread_dict[(game_key, 'home')]['prices'].append(price)
                            # Track DraftKings specifically
                            if sportsbook_key == 'draftkings':
                                dk_spread_dict[(game_key, 'home')]['point'] = point
                                dk_spread_dict[(game_key, 'home')]['price'] = price
                        elif team_name == away_team and point is not None and price is not None:
                            spread_dict[(game_key, 'away')]['points'].append(point)
                            spread_dict[(game_key, 'away')]['prices'].append(price)
                            # Track DraftKings specifically
                            if sportsbook_key == 'draftkings':
                                dk_spread_dict[(game_key, 'away')]['point'] = point
                                dk_spread_dict[(game_key, 'away')]['price'] = price

    # Build final records with median spreads and prices
    spreads_records = []
    for (game_key, side), values in spread_dict.items():
        if not values['points'] or not values['prices']:
            logger.info(f"[yellow]Missing spread data for game:[/yellow] {game_key}, side: {side}")
            continue

        # Calculate medians
        med_point = median(values['points'])
        med_price = median(values['prices'])

        # Parse game info from the key
        game_time, teams = game_key.split('_', 1)
        home_team, away_team = teams.split('_vs_')

        if side == 'home':
            team_name = home_team
        else:
            team_name = away_team

        # Get DraftKings-specific values
        dk_values = dk_spread_dict.get((game_key, side), {})

        spreads_records.append({
            'Game Time': game_time,
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': team_name,
            'Spread': med_point,
            'Spread Price': med_price,
            'DK_Spread': dk_values.get('point'),
            'DK_Spread_Price': dk_values.get('price'),
            'Sportsbook': 'CONSENSUS'  # Indicates this is a median across books
        })

    return pd.DataFrame(spreads_records)

def get_totals_odds(data):
    """
    Processes totals odds into a DataFrame with one row per game,
    using the median of all available sportsbooks for over/under lines and prices.
    Also extracts DraftKings-specific values for opening odds.
    """
    # Dictionary to store all totals data for each game
    totals_dict = {}
    # Dictionary to store DraftKings-specific totals
    dk_totals_dict = {}

    for game in data:
        game_time = game.get('commence_time')
        home_team = game.get('home_team')
        away_team = game.get('away_team')

        if not all([game_time, home_team, away_team]):
            continue

        # Use game time + teams as unique identifier
        game_key = f"{game_time}_{home_team}_vs_{away_team}"

        # Initialize data structure for this game
        if game_key not in totals_dict:
            totals_dict[game_key] = {
                'over_points': [],
                'over_prices': [],
                'under_points': [],
                'under_prices': []
            }
        # Initialize DraftKings tracking
        if game_key not in dk_totals_dict:
            dk_totals_dict[game_key] = {'total': None}

        # Collect totals from each sportsbook
        for bookmaker in game.get('bookmakers', []):
            sportsbook_key = bookmaker.get('key')
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'totals':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        if outcome.get('name') == 'Over':
                            if outcome.get('point') is not None:
                                totals_dict[game_key]['over_points'].append(outcome['point'])
                                # Track DraftKings specifically (over point = total)
                                if sportsbook_key == 'draftkings':
                                    dk_totals_dict[game_key]['total'] = outcome['point']
                            if outcome.get('price') is not None:
                                totals_dict[game_key]['over_prices'].append(outcome['price'])
                        elif outcome.get('name') == 'Under':
                            if outcome.get('point') is not None:
                                totals_dict[game_key]['under_points'].append(outcome['point'])
                            if outcome.get('price') is not None:
                                totals_dict[game_key]['under_prices'].append(outcome['price'])

    # Build final records with median values
    totals_records = []
    for game_key, values in totals_dict.items():
        if not values['over_points'] or not values['under_points']:
            continue

        # Calculate medians
        med_over_point = median(values['over_points'])
        med_over_price = median(values['over_prices']) if values['over_prices'] else None
        med_under_point = median(values['under_points'])
        med_under_price = median(values['under_prices']) if values['under_prices'] else None

        # Calculate projected total as average of median over/under points
        projected_total = (med_over_point + med_under_point) / 2

        # Parse game info from the key
        game_time, teams = game_key.split('_', 1)
        home_team, away_team = teams.split('_vs_')

        # Get DraftKings-specific total
        dk_values = dk_totals_dict.get(game_key, {})

        totals_records.append({
            'Game Time': game_time,
            'Home Team': home_team,
            'Away Team': away_team,
            'Projected Total': projected_total,
            'Over Point': med_over_point,
            'Over Price': med_over_price,
            'Under Point': med_under_point,
            'Under Price': med_under_price,
            'DK_Total': dk_values.get('total'),
            'Sportsbook': 'CONSENSUS'  # Indicates this is a median across books
        })

    return pd.DataFrame(totals_records)

def get_combined_odds():
    """
    Fetches odds data from API and returns a combined DataFrame with all odds info
    """
    data = get_odds_data()
    if not data:
        return pd.DataFrame()

    # Remove the time-based filtering completely
    # Keep all games, regardless of their start time
    filtered_data = data

    # If everything got filtered out, return empty DataFrame
    if not filtered_data:
        return pd.DataFrame()

    # Get DataFrames and process using all data
    moneyline_df = get_moneyline_odds(filtered_data).drop(columns=['Sportsbook'])
    logger.info(f"\n[cyan]Sample Game Times from moneyline_df:[/cyan]\n{moneyline_df['Game Time'].head()}")
    
    spreads_df = get_spread_odds(filtered_data).drop(columns=['Sportsbook']).rename(
        columns={'Spread': 'Consensus Spread'})
    logger.info(f"\n[cyan]Sample Game Times from spreads_df:[/cyan]\n{spreads_df['Game Time'].head()}")
    
    totals_df = get_totals_odds(filtered_data).drop(columns=['Sportsbook'])
    logger.info(f"\n[cyan]Sample Game Times from totals_df:[/cyan]\n{totals_df['Game Time'].head()}")

    # Merge data
    combined_df = pd.merge(
        moneyline_df,
        spreads_df,
        on=['Game Time', 'Home Team', 'Away Team', 'Team'],
        how='outer'
    )
    logger.info(f"\n[cyan]Sample Game Times after first merge:[/cyan]\n{combined_df['Game Time'].head()}")

    combined_df = pd.merge(
        combined_df,
        totals_df,
        on=['Game Time', 'Home Team', 'Away Team'],
        how='outer'
    )
    logger.info(f"\n[cyan]Sample Game Times after second merge:[/cyan]\n{combined_df['Game Time'].head()}")

    # Create game identifier
    combined_df.insert(0, 'Game',
        combined_df['Home Team'] + " vs. " + combined_df['Away Team'])

    # Convert Game Time to datetime, handling both formats
    def convert_game_time(time_str):
        try:
            # Try ISO format first
            dt = pd.to_datetime(time_str)
            # Convert to ET
            et = timezone('US/Eastern')
            if dt.tzinfo is None:
                dt = dt.tz_localize('UTC')
            dt = dt.tz_convert(et)
            return dt
        except (ValueError, TypeError) as e:
            logger.error(f"[red]Error converting time {time_str}: {str(e)}[/red]")
            return pd.NaT

    logger.info(f"\n[cyan]Sample Game Times before conversion:[/cyan]\n{combined_df['Game Time'].head()}")
    
    # Convert all times to ET format after merges are complete
    combined_df['Game Time'] = combined_df['Game Time'].apply(convert_game_time)
    logger.info(f"\n[cyan]Sample Game Times after datetime conversion:[/cyan]\n{combined_df['Game Time'].head()}")
    
    # Format the Game Time column to Month Abbr, Day Time (ET)
    combined_df['Game Time'] = combined_df['Game Time'].dt.strftime('%b %d %I:%M%p ET')
    logger.info(f"\n[cyan]Sample Game Times after formatting:[/cyan]\n{combined_df['Game Time'].head()}")
    
    combined_df = combined_df.sort_values('Game Time', ascending=True)

    return combined_df

def merge_with_combined_data(odds_df):
    """
    Merges odds data with the combined data from previous steps.
    Tries both home/away team orderings to maximize matches.
    """
    logger.info("[cyan]Loading combined data from CSV...[/cyan]")
    combined_data_path = os.path.join(data_dir, 'combined_data.csv')
    
    if not os.path.exists(combined_data_path):
        logger.error(f"[red]✗[/red] Combined data file not found at {combined_data_path}")
        return pd.DataFrame()
    
    # Load the combined data
    combined_df = pd.read_csv(combined_data_path)
    logger.info(f"[green]✓[/green] Loaded combined data with shape: {combined_df.shape}")
    
    # Preview data
    logger.info("\n[cyan]Preview of combined_data.csv:[/cyan]")
    logger.info(f"Columns: {', '.join(combined_df.columns[:10])}")
    logger.info(f"First few teams: {combined_df['Team'].head().tolist()}")
    
    logger.info("\n[cyan]Preview of odds data:[/cyan]")
    logger.info(f"Columns: {', '.join(odds_df.columns)}")
    logger.info(f"First few teams: {odds_df['Team'].head().tolist()}")
    
    # Try original team ordering
    logger.info("[cyan]Attempting merge with original team ordering...[/cyan]")
    result_df = pd.merge(
        combined_df,
        odds_df,
        on=['Team', 'Home Team', 'Away Team'],
        how='left'
    )
    original_matches = result_df['Moneyline'].notna().sum()
    logger.info(f"Original ordering matches: {original_matches}")
    
    # Create swapped version of odds data
    logger.info("[cyan]Creating swapped team version...[/cyan]")
    swapped_odds_df = odds_df.copy()
    swapped_odds_df['Home Team'], swapped_odds_df['Away Team'] = odds_df['Away Team'], odds_df['Home Team']
    # Adjust spreads and probabilities for the swap
    swapped_odds_df['Consensus Spread'] = -swapped_odds_df['Consensus Spread']
    if 'DK_Spread' in swapped_odds_df.columns:
        swapped_odds_df['DK_Spread'] = -swapped_odds_df['DK_Spread']
    if 'Devigged Probability' in swapped_odds_df.columns:
        swapped_odds_df['Devigged Probability'] = 1 - swapped_odds_df['Devigged Probability']
    
    # Try merge with swapped teams
    logger.info("[cyan]Attempting merge with swapped team ordering...[/cyan]")
    swapped_result_df = pd.merge(
        combined_df,
        swapped_odds_df,
        on=['Team', 'Home Team', 'Away Team'],
        how='left'
    )
    swapped_matches = swapped_result_df['Moneyline'].notna().sum()
    logger.info(f"Swapped ordering matches: {swapped_matches}")
    
    # Use whichever version got more matches
    if swapped_matches > original_matches:
        logger.info("[green]✓[/green] Using swapped team ordering (more matches)")
        result_df = swapped_result_df
    else:
        logger.info("[green]✓[/green] Using original team ordering (more matches)")
    
    logger.info(f"[green]✓[/green] Merged data has shape: {result_df.shape}")
    merge_success_count = result_df['Moneyline'].notna().sum()
    logger.info(f"[cyan]Successfully matched odds for {merge_success_count} / {len(result_df)} rows[/cyan]")

    # Filter out rows without Game Time (these are teams with no odds data available)
    rows_before = len(result_df)
    result_df = result_df[result_df['Game Time'].notna() & (result_df['Game Time'] != '')]
    rows_after = len(result_df)
    logger.info(f"[cyan]Filtered out {rows_before - rows_after} rows without game times[/cyan]")

    return result_df

def calculate_spread_implied_prob_safe(spread_price):
    """
    Safely calculate spread implied probability with validation and defaults.
    Defaults to -110 (standard spread odds) for missing/invalid data.

    Args:
        spread_price: American odds for the spread (e.g., -110, +105)

    Returns:
        float: Implied probability between 0 and 1
    """
    # Missing data: use standard -110 odds
    if pd.isna(spread_price) or spread_price is None:
        return 0.5238095238095238  # -110 odds = 52.38% implied probability

    try:
        spread_price = float(spread_price)
    except (ValueError, TypeError):
        logger.warning(f"Invalid spread price type: {spread_price}, using -110 default")
        return 0.5238095238095238

    # Validate spread prices are reasonable (-200 to +200)
    # Spreads are typically -110 to -120, rarely outside -200 to +200
    if abs(spread_price) > 200:
        logger.warning(f"Outlier spread price detected: {spread_price}, using -110 default")
        return 0.5238095238095238

    # Spread prices should not be between -100 and +100 (except exactly -100 or +100)
    # This catches cases where the spread line (e.g., 2.5) was mistakenly used as price
    if -100 < spread_price < -99 or 99 < spread_price < 100:
        prob = american_odds_to_implied_probability(spread_price)
        if prob is not None:
            return prob
    elif 0 < abs(spread_price) < 100:
        logger.warning(f"Suspicious spread price (likely spread line, not odds): {spread_price}, using -110 default")
        return 0.5238095238095238

    return american_odds_to_implied_probability(spread_price)

def process_final_dataframe(final_df):
    """
    Process the final dataframe with spreads and totals lookup tables.
    Apply the requested calculations and return a formatted dataframe.
    """
    logger.info("[cyan]Processing final dataframe with lookup tables...[/cyan]")
    # Set theoddsapi_total for the lookups
    final_df['theoddsapi_total'] = final_df['Projected Total']

    # Calculate median of spreads across all models (only use columns that exist)
    spread_models = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    available_spread_models = [col for col in spread_models if col in final_df.columns]
    if available_spread_models:
        final_df['forecasted_spread'] = final_df[available_spread_models].median(axis=1)
        logger.info(f"[cyan]Using spread models: {available_spread_models}[/cyan]")
    else:
        final_df['forecasted_spread'] = 0
        logger.warning("[yellow]⚠[/yellow] No spread model columns available")

    # Rename columns for clarity and round market_spread to nearest 0.5
    final_df['market_spread'] = (final_df['Consensus Spread'] * 2).round() / 2
    final_df['model_spread'] = final_df['forecasted_spread']

    # Create total_category based on market total (for spread predictions)
    final_df['total_category'] = pd.cut(
        final_df['theoddsapi_total'],
        bins=[-float('inf'), 137.5, 145.5, float('inf')],
        labels=[1, 2, 3]
    ).astype('Int64')

    # Calculate Predicted Outcome using market_spread and model_spread, rounded to nearest 0.5
    final_df['Predicted Outcome'] = ((0.6 * final_df['market_spread'] +
                                    0.4 * final_df['model_spread']) * 2).round() / 2

    # Load spreads lookup data using new combined framework
    try:
        spreads_lookup_path = os.path.join(project_root, 'spreads_lookup_combined.csv')
        logger.info(f"[cyan]Loading spreads lookup data from {spreads_lookup_path}[/cyan]")
        spreads_lookup_df = pd.read_csv(spreads_lookup_path)

        # Round market_spread to nearest 0.5 for matching
        # Predicted Outcome is already rounded to 0.5 from line 624-625
        final_df['market_spread_rounded'] = (final_df['market_spread'] * 2).round() / 2

        # Calculate spread implied probability from Spread Price using safe validation
        if 'Spread Price' in final_df.columns:
            logger.info("[cyan]Calculating spread implied probabilities with validation...[/cyan]")
            final_df['spread_implied_prob'] = final_df['Spread Price'].apply(calculate_spread_implied_prob_safe)

            # Log data quality stats
            missing_count = final_df['Spread Price'].isna().sum()
            total_count = len(final_df)
            default_count = (final_df['spread_implied_prob'] == 0.5238095238095238).sum()
            logger.info(f"[cyan]Spread Price data quality: {missing_count}/{total_count} missing, {default_count}/{total_count} using -110 default[/cyan]")
        else:
            # If Spread Price doesn't exist, initialize with standard -110 odds (52.38%)
            logger.warning("[yellow]⚠[/yellow] 'Spread Price' column not found, using -110 default for all games")
            final_df['spread_implied_prob'] = 0.5238095238095238

        # Merge with lookup data using total_category, market_spread, and Predicted Outcome (instead of model_spread)
        # Predicted Outcome already incorporates market (60%) and model (40%) weighting
        final_df = final_df.merge(
            spreads_lookup_df,
            left_on=['total_category', 'market_spread_rounded', 'Predicted Outcome'],
            right_on=['total_category', 'market_spread', 'model_spread'],
            how='left',
            suffixes=('', '_lookup')
        )

        # Calculate cover probability and edge
        final_df['Spread Cover Probability'] = final_df['cover_prob']
        final_df['Edge For Covering Spread'] = (
            final_df['Spread Cover Probability'] -
            final_df['spread_implied_prob']
        )

        # Clean up temporary and duplicate columns
        final_df.drop(columns=['market_spread_rounded',
                               'market_spread_lookup', 'model_spread_lookup'],
                     inplace=True, errors='ignore')

        logger.info(f"[green]✓[/green] Successfully applied spreads lookup")
    except FileNotFoundError:
        logger.warning("[yellow]⚠[/yellow] spreads_lookup_combined.csv not found")
        final_df['Spread Cover Probability'] = np.nan
        final_df['Edge For Covering Spread'] = np.nan
    
    # Calculate totals projections
    projected_total_models = ['projected_total_barttorvik',
                            'projected_total_kenpom',
                            'projected_total_evanmiya',
                            'projected_total_hasla']

    # Handle missing totals data
    final_df['theoddsapi_total'] = pd.to_numeric(final_df['theoddsapi_total'], errors='coerce')

    # Make sure theoddsapi_total is rounded to nearest 0.5 for proper lookup
    final_df['theoddsapi_total_rounded'] = (final_df['theoddsapi_total'] * 2).round() / 2

    final_df['forecasted_total'] = final_df[projected_total_models].median(axis=1, skipna=True)

    # Rename columns for clarity
    final_df['market_total'] = final_df['theoddsapi_total']
    final_df['model_total'] = final_df['forecasted_total']

    # Create spread_category based on market spread (for total predictions)
    # Use absolute value so both teams in same game get same category
    final_df['spread_category'] = pd.cut(
        abs(final_df['market_spread']),
        bins=[0, 2.5, 10.0, float('inf')],
        labels=[1, 2, 3]
    ).astype('Int64')

    # Add totals standard deviation here
    final_df['Totals Std. Dev.'] = final_df[projected_total_models].std(axis=1, skipna=True).round(1)

    # Fill missing averages with market_total and model_total, round to nearest 0.5
    final_df['average_total'] = (
        (0.6 * final_df['market_total'].fillna(0) +
        0.4 * final_df['model_total'].fillna(final_df['market_total'])) * 2
    ).round() / 2

    # Load and process totals lookup data using new combined framework
    try:
        totals_lookup_path = os.path.join(project_root, 'totals_lookup_combined.csv')
        logger.info(f"[cyan]Loading totals lookup data from {totals_lookup_path}[/cyan]")
        totals_lookup_df = pd.read_csv(totals_lookup_path)

        # Drop any duplicate rows before merging
        final_df = final_df.drop_duplicates(subset=['Game', 'Team'], keep='first')

        # Round market_total to nearest 0.5 for matching
        # average_total is already rounded to 0.5 from line 707-710
        final_df['market_total_rounded'] = (final_df['market_total'] * 2).round() / 2

        # Merge with lookup data using spread_category, market_total, and average_total (instead of model_total)
        # average_total already incorporates market (60%) and model (40%) weighting
        final_df = final_df.merge(
            totals_lookup_df,
            left_on=['spread_category', 'market_total_rounded', 'average_total'],
            right_on=['spread_category', 'market_total', 'model_total'],
            how='left',
            suffixes=('', '_lookup')
        )

        # Map probabilities from lookup table
        final_df['Over Cover Probability'] = final_df['over_prob']
        final_df['Under Cover Probability'] = final_df['under_prob']

        # Clean up temporary and duplicate columns
        final_df.drop(columns=['theoddsapi_total_rounded', 'market_total_rounded',
                               'market_total_lookup', 'model_total_lookup'],
                     inplace=True, errors='ignore')

        logger.info(f"[green]✓[/green] Successfully applied totals lookup")
    except FileNotFoundError:
        logger.warning("[yellow]⚠[/yellow] totals_lookup_combined.csv not found. Skipping Over/Under probabilities.")
        final_df['Over Cover Probability'] = np.nan
        final_df['Under Cover Probability'] = np.nan
        # Clean up temporary columns even if lookup failed
        final_df.drop(columns=['theoddsapi_total_rounded'], inplace=True, errors='ignore')

    # Calculate totals implied probabilities and edges
    final_df['over_implied_prob'] = final_df['Over Price'].apply(american_odds_to_implied_probability)
    final_df['under_implied_prob'] = final_df['Under Price'].apply(american_odds_to_implied_probability)
    final_df['Over Total Edge'] = final_df['Over Cover Probability'] - final_df['over_implied_prob']
    final_df['Under Total Edge'] = final_df['Under Cover Probability'] - final_df['under_implied_prob']

    # Calculate spread standard deviation (only use columns that exist)
    spread_std_models = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    available_spread_std_models = [col for col in spread_std_models if col in final_df.columns]
    if available_spread_std_models:
        final_df['Spread Std. Dev.'] = final_df[available_spread_std_models].std(axis=1, skipna=True).round(1)
    else:
        final_df['Spread Std. Dev.'] = 0
    
    # Calculate totals standard deviation (only use columns that exist)
    projected_total_models = ['projected_total_barttorvik', 'projected_total_kenpom',
                             'projected_total_evanmiya', 'projected_total_hasla']
    available_total_models = [col for col in projected_total_models if col in final_df.columns]
    if available_total_models:
        final_df['Totals Std. Dev.'] = final_df[available_total_models].std(axis=1, skipna=True).round(1)
    else:
        final_df['Totals Std. Dev.'] = 0

    # Calculate moneyline standard deviation (only use columns that exist)
    win_prob_models = ['win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya']
    available_win_prob_models = [col for col in win_prob_models if col in final_df.columns]
    if available_win_prob_models:
        final_df['Moneyline Std. Dev.'] = final_df[available_win_prob_models].std(axis=1, skipna=True).round(3)
    else:
        final_df['Moneyline Std. Dev.'] = 0

    # Calculate moneyline probabilities and edge using devigged probabilities
    win_prob_cols = ['win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya']
    available_win_prob_cols = [col for col in win_prob_cols if col in final_df.columns]
    if available_win_prob_cols:
        final_df['Moneyline Win Probability'] = final_df[available_win_prob_cols].median(axis=1, skipna=True)
    else:
        final_df['Moneyline Win Probability'] = 0.5
    final_df['Moneyline Win Probability'] = (0.5*final_df['Moneyline Win Probability']+0.5*final_df['Devigged Probability'])
    final_df['ml_implied_prob'] = final_df['Moneyline'].apply(american_odds_to_implied_probability)
    final_df['Moneyline Edge'] = final_df['Moneyline Win Probability'] - final_df['ml_implied_prob']

    # Keep rows with missing devigged probabilities, just fill with 0
    final_df['Devigged Probability'] = final_df['Devigged Probability'].fillna(0)
    final_df['Moneyline Edge'] = final_df['Moneyline Edge'].fillna(0)

    # Create Current Moneyline from consensus
    if 'Moneyline' in final_df.columns:
        final_df['Current Moneyline'] = final_df['Moneyline'].round().astype('Int64')
    else:
        logger.warning("[yellow]⚠[/yellow] 'Moneyline' column not found, creating empty Current Moneyline column")
        final_df['Current Moneyline'] = np.nan

    # Create Opening columns from DraftKings-specific values
    # Opening Spread: Use DraftKings spread (wait for DK if not available)
    if 'DK_Spread' in final_df.columns:
        final_df['Opening Spread'] = final_df['DK_Spread']
        logger.info(f"[cyan]DraftKings spread data available for {final_df['DK_Spread'].notna().sum()} games[/cyan]")
    else:
        final_df['Opening Spread'] = np.nan
        logger.warning("[yellow]⚠[/yellow] 'DK_Spread' column not found, Opening Spread will be empty")

    # Opening Moneyline: Use DraftKings moneyline (wait for DK if not available)
    if 'DK_Moneyline' in final_df.columns:
        final_df['Opening Moneyline'] = final_df['DK_Moneyline'].round().astype('Int64')
        logger.info(f"[cyan]DraftKings moneyline data available for {final_df['DK_Moneyline'].notna().sum()} games[/cyan]")
    else:
        final_df['Opening Moneyline'] = pd.NA
        logger.warning("[yellow]⚠[/yellow] 'DK_Moneyline' column not found, Opening Moneyline will be empty")

    # Opening Total: Use DraftKings total (wait for DK if not available)
    if 'DK_Total' in final_df.columns:
        final_df['Opening Total'] = final_df['DK_Total']
        logger.info(f"[cyan]DraftKings total data available for {final_df['DK_Total'].notna().sum()} games[/cyan]")
    else:
        final_df['Opening Total'] = np.nan
        logger.warning("[yellow]⚠[/yellow] 'DK_Total' column not found, Opening Total will be empty")

    # Create Opening Edge columns (only set when DraftKings opening data exists)
    # These capture the edge at the time DraftKings first posted odds
    has_dk_spread = final_df['Opening Spread'].notna()
    has_dk_moneyline = final_df['Opening Moneyline'].notna()
    has_dk_total = final_df['Opening Total'].notna()

    final_df['Opening Spread Edge'] = np.where(has_dk_spread, final_df['Edge For Covering Spread'], np.nan)
    final_df['Opening Moneyline Edge'] = np.where(has_dk_moneyline, final_df['Moneyline Edge'], np.nan)
    final_df['Opening Over Edge'] = np.where(has_dk_total, final_df['Over Total Edge'], np.nan)
    final_df['Opening Under Edge'] = np.where(has_dk_total, final_df['Under Total Edge'], np.nan)

    # Add 'Opening Odds Time' timestamp (when opening odds were first captured)
    # This will be preserved via preserve_opening_odds() for existing games
    final_df['Opening Odds Time'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    # Drop any remaining duplicates after all processing
    final_df = final_df.drop_duplicates(subset=['Game', 'Team'], keep='first')

    logger.info(f"[cyan]Final shape after handling missing devigged probabilities:[/cyan] {final_df.shape}")

    # Calculate consensus flags
    logger.info("[cyan]Calculating consensus flags...[/cyan]")
    final_df['spread_consensus_flag'] = final_df.apply(calculate_spread_consensus, axis=1)
    final_df['moneyline_consensus_flag'] = final_df.apply(calculate_moneyline_consensus, axis=1)
    final_df['over_consensus_flag'] = final_df.apply(calculate_over_consensus, axis=1)
    final_df['under_consensus_flag'] = final_df.apply(calculate_under_consensus, axis=1)
    logger.info(f"[green]✓[/green] Consensus flags calculated")

    final_df = final_df.sort_values('Game Time', ascending=True)
    
    # Define final column order
    column_order = [
        'Game', 'Game Time', 'Opening Odds Time', 'Team',
        # Spread framework columns
        'total_category', 'market_spread', 'Consensus Spread', 'model_spread', 'Predicted Outcome', 'Spread Cover Probability',
        'Opening Spread', 'Edge For Covering Spread', 'Opening Spread Edge', 'Spread Std. Dev.', 'spread_barttorvik',
        'spread_kenpom', 'spread_evanmiya', 'spread_hasla',
        # Moneyline columns
        'Moneyline Win Probability', 'Opening Moneyline', 'Current Moneyline', 'Devigged Probability', 'Moneyline Edge', 'Opening Moneyline Edge', 'Moneyline Std. Dev.',
        'win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya',
        # Totals framework columns
        'spread_category', 'market_total', 'model_total', 'average_total', 'Opening Total', 'theoddsapi_total', 'Totals Std. Dev.',
        'projected_total_barttorvik', 'projected_total_kenpom', 'projected_total_evanmiya', 'projected_total_hasla',
        'Over Cover Probability', 'Under Cover Probability',
        'Over Total Edge', 'Under Total Edge', 'Opening Over Edge', 'Opening Under Edge',
        # Consensus flags
        'spread_consensus_flag', 'moneyline_consensus_flag', 'over_consensus_flag', 'under_consensus_flag'
    ]
    
    # Only keep columns that exist in the dataframe
    available_columns = [col for col in column_order if col in final_df.columns]
    
    logger.info(f"[green]✓[/green] Final dataframe processing complete")
    return final_df[available_columns].reset_index(drop=True)

def calculate_spread_consensus(row):
    """
    Calculate spread consensus flag.
    Returns 1 if all model spreads (in absolute value) are either all greater than
    or all less than the market spread (in absolute value).
    Returns 0 otherwise or if any values are missing.
    """
    try:
        # Get required values (use consensus spread for market comparison)
        market_spread = row.get('Consensus Spread')

        # Model spreads
        spread_kenpom = row.get('spread_kenpom')
        spread_evanmiya = row.get('spread_evanmiya')
        spread_barttorvik = row.get('spread_barttorvik')
        spread_hasla = row.get('spread_hasla')

        # Check for missing values
        if pd.isna(market_spread):
            return 0
        if pd.isna(spread_kenpom) or pd.isna(spread_evanmiya) or pd.isna(spread_barttorvik) or pd.isna(spread_hasla):
            return 0

        # Use absolute values for comparison
        abs_market_spread = abs(market_spread)
        abs_kenpom = abs(spread_kenpom)
        abs_evanmiya = abs(spread_evanmiya)
        abs_barttorvik = abs(spread_barttorvik)
        abs_hasla = abs(spread_hasla)

        # Check if all models are on the same side
        all_above = (abs_kenpom > abs_market_spread and
                     abs_evanmiya > abs_market_spread and
                     abs_barttorvik > abs_market_spread and
                     abs_hasla > abs_market_spread)

        all_below = (abs_kenpom < abs_market_spread and
                     abs_evanmiya < abs_market_spread and
                     abs_barttorvik < abs_market_spread and
                     abs_hasla < abs_market_spread)

        if all_above or all_below:
            return 1

        return 0
    except Exception as e:
        logger.debug(f"Error calculating spread consensus: {e}")
        return 0

def calculate_moneyline_consensus(row):
    """
    Calculate moneyline consensus flag.
    Returns 1 if all model win probabilities are on the same side of devigged probability.
    Returns 0 otherwise or if any values are missing.
    """
    try:
        # Get required values
        devigged_prob = row.get('Devigged Probability')
        win_prob_kenpom = row.get('win_prob_kenpom')
        win_prob_evanmiya = row.get('win_prob_evanmiya')
        win_prob_barttorvik = row.get('win_prob_barttorvik')

        # Check for missing values
        if pd.isna(devigged_prob):
            return 0
        if pd.isna(win_prob_kenpom) or pd.isna(win_prob_evanmiya) or pd.isna(win_prob_barttorvik):
            return 0

        # Check if all models agree on direction
        all_above = (win_prob_kenpom > devigged_prob and
                    win_prob_evanmiya > devigged_prob and
                    win_prob_barttorvik > devigged_prob)

        all_below = (win_prob_kenpom < devigged_prob and
                    win_prob_evanmiya < devigged_prob and
                    win_prob_barttorvik < devigged_prob)

        if all_above or all_below:
            return 1

        return 0
    except Exception as e:
        logger.debug(f"Error calculating moneyline consensus: {e}")
        return 0

def calculate_over_consensus(row):
    """
    Calculate over consensus flag.
    Returns 1 if all model projected totals are above market total.
    Returns 0 otherwise or if any values are missing.
    """
    try:
        # Get required values
        market_total = row.get('market_total')
        projected_total_kenpom = row.get('projected_total_kenpom')
        projected_total_evanmiya = row.get('projected_total_evanmiya')
        projected_total_barttorvik = row.get('projected_total_barttorvik')
        projected_total_hasla = row.get('projected_total_hasla')

        # Check for missing values
        if pd.isna(market_total):
            return 0
        if (pd.isna(projected_total_kenpom) or pd.isna(projected_total_evanmiya) or
            pd.isna(projected_total_barttorvik) or pd.isna(projected_total_hasla)):
            return 0

        # Check if all models favor Over
        if (projected_total_kenpom > market_total and
            projected_total_evanmiya > market_total and
            projected_total_barttorvik > market_total and
            projected_total_hasla > market_total):
            return 1

        return 0
    except Exception as e:
        logger.debug(f"Error calculating over consensus: {e}")
        return 0

def calculate_under_consensus(row):
    """
    Calculate under consensus flag.
    Returns 1 if all model projected totals are below market total.
    Returns 0 otherwise or if any values are missing.
    """
    try:
        # Get required values
        market_total = row.get('market_total')
        projected_total_kenpom = row.get('projected_total_kenpom')
        projected_total_evanmiya = row.get('projected_total_evanmiya')
        projected_total_barttorvik = row.get('projected_total_barttorvik')
        projected_total_hasla = row.get('projected_total_hasla')

        # Check for missing values
        if pd.isna(market_total):
            return 0
        if (pd.isna(projected_total_kenpom) or pd.isna(projected_total_evanmiya) or
            pd.isna(projected_total_barttorvik) or pd.isna(projected_total_hasla)):
            return 0

        # Check if all models favor Under
        if (projected_total_kenpom < market_total and
            projected_total_evanmiya < market_total and
            projected_total_barttorvik < market_total and
            projected_total_hasla < market_total):
            return 1

        return 0
    except Exception as e:
        logger.debug(f"Error calculating under consensus: {e}")
        return 0


def backup_daily_output(csv_path):
    """
    Creates a daily backup of the output CSV file in the historical_data folder.
    Only creates {date}_output.csv once per day (first capture).

    Args:
        csv_path (str): Path to the CBB_Output.csv file to backup
    """
    try:
        import shutil

        # Get current date in ET timezone
        et = timezone('US/Eastern')
        current_date = datetime.now(et).strftime('%Y-%m-%d')

        # Create historical_data directory if it doesn't exist
        historical_dir = os.path.join(project_root, 'historical_data')
        if not os.path.exists(historical_dir):
            os.makedirs(historical_dir)
            logger.info(f"[cyan]Created historical_data directory: {historical_dir}[/cyan]")

        # Daily backup - only created once per day (first capture)
        backup_filename = f"{current_date}_output.csv"
        backup_path = os.path.join(historical_dir, backup_filename)

        if not os.path.exists(backup_path):
            shutil.copy2(csv_path, backup_path)
            logger.info(f"[green]✓[/green] Created daily backup: {backup_filename}")
        else:
            logger.info(f"[cyan]Daily backup already exists: {backup_filename}[/cyan]")

    except Exception as e:
        logger.warning(f"[yellow]⚠[/yellow] Failed to create daily backup: {str(e)}")
        # Don't fail the entire pipeline if backup fails


def preserve_opening_odds(new_df, existing_csv_path='CBB_Output.csv'):
    """
    Preserve existing DraftKings opening odds and edge values from the previous output.

    Opening values are DraftKings-specific. When a game first appears:
    - If DraftKings has odds: those become the opening values
    - If DraftKings doesn't have odds yet: opening columns remain empty until DK data appears

    Once opening values are set (when DraftKings data is first received), they are preserved
    across all subsequent runs regardless of line movement.

    Args:
        new_df (pd.DataFrame): New dataframe with current odds
        existing_csv_path (str): Path to existing CBB_Output.csv

    Returns:
        pd.DataFrame: Dataframe with preserved opening values
    """
    if not os.path.exists(existing_csv_path):
        logger.info("[cyan]No existing CBB_Output.csv found, all values are opening values[/cyan]")
        return new_df

    try:
        existing_df = pd.read_csv(existing_csv_path)

        # Create lookup from existing data keyed by (Game, Team)
        existing_lookup = {}
        for _, row in existing_df.iterrows():
            key = (row.get('Game'), row.get('Team'))
            existing_lookup[key] = {
                'Opening Spread': row.get('Opening Spread'),
                'Opening Moneyline': row.get('Opening Moneyline'),
                'Opening Total': row.get('Opening Total'),
                'Opening Odds Time': row.get('Opening Odds Time'),
                # Opening edge values (preserved like opening lines)
                'Opening Spread Edge': row.get('Opening Spread Edge'),
                'Opening Moneyline Edge': row.get('Opening Moneyline Edge'),
                'Opening Over Edge': row.get('Opening Over Edge'),
                'Opening Under Edge': row.get('Opening Under Edge'),
            }

        # Preserve opening values for games that already exist
        preserved_count = 0
        for idx, row in new_df.iterrows():
            key = (row.get('Game'), row.get('Team'))
            if key in existing_lookup:
                existing_vals = existing_lookup[key]

                # Only preserve if existing value is not null
                if pd.notna(existing_vals.get('Opening Spread')):
                    new_df.at[idx, 'Opening Spread'] = existing_vals['Opening Spread']
                if pd.notna(existing_vals.get('Opening Moneyline')):
                    new_df.at[idx, 'Opening Moneyline'] = existing_vals['Opening Moneyline']
                if pd.notna(existing_vals.get('Opening Total')):
                    new_df.at[idx, 'Opening Total'] = existing_vals['Opening Total']
                if pd.notna(existing_vals.get('Opening Odds Time')):
                    new_df.at[idx, 'Opening Odds Time'] = existing_vals['Opening Odds Time']
                # Preserve opening edge values
                if pd.notna(existing_vals.get('Opening Spread Edge')):
                    new_df.at[idx, 'Opening Spread Edge'] = existing_vals['Opening Spread Edge']
                if pd.notna(existing_vals.get('Opening Moneyline Edge')):
                    new_df.at[idx, 'Opening Moneyline Edge'] = existing_vals['Opening Moneyline Edge']
                if pd.notna(existing_vals.get('Opening Over Edge')):
                    new_df.at[idx, 'Opening Over Edge'] = existing_vals['Opening Over Edge']
                if pd.notna(existing_vals.get('Opening Under Edge')):
                    new_df.at[idx, 'Opening Under Edge'] = existing_vals['Opening Under Edge']
                preserved_count += 1

        if preserved_count > 0:
            logger.info(f"[green]✓[/green] Preserved opening odds and edges for {preserved_count} existing games")

        return new_df

    except Exception as e:
        logger.warning(f"[yellow]⚠[/yellow] Error preserving opening odds: {e}")
        return new_df


def run_oddsapi_etl():
    """
    Main ETL function to run the OddsAPI workflow
    """
    logger.info("=== Starting OddsAPI ETL process ===")

    # Get odds data
    logger.info("[cyan]Fetching odds data from API...[/cyan]")
    odds_df = get_combined_odds()

    if odds_df.empty:
        logger.error("[red]✗[/red] Failed to get odds data from API")
        return pd.DataFrame()

    logger.info(f"[green]✓[/green] Successfully fetched odds data with {len(odds_df)} rows")

    # Temporary save for inspection
    odds_csv_path = os.path.join(data_dir, 'oddsapi_raw.csv')
    odds_df.to_csv(odds_csv_path, index=False)
    logger.info(f"[green]✓[/green] Saved raw odds data to {odds_csv_path}")

    # Merge with combined data
    logger.info("[cyan]Merging odds data with combined data...[/cyan]")
    final_df = merge_with_combined_data(odds_df)

    if final_df.empty:
        logger.error("[red]✗[/red] Failed to merge odds data with combined data")
        return pd.DataFrame()

    # Process final dataframe with lookup tables
    final_df = process_final_dataframe(final_df)

    # Save final results
    output_path = os.path.join(data_dir, 'final_combined_data.csv')
    final_df.to_csv(output_path, index=False)
    logger.info(f"[green]✓[/green] Saved final combined data to {output_path}")

    logger.info("=== OddsAPI ETL process completed successfully ===")
    return final_df

if __name__ == "__main__":
    logger.info("=== Starting OddsAPI script ===")

    try:
        # Run the ETL process
        result_df = run_oddsapi_etl()

        if not result_df.empty:
            output_file = os.path.join(data_dir, 'final_combined_data.csv')
            logger.info(f"[green]✓[/green] Final data shape: {result_df.shape}")
            logger.info(f"[green]✓[/green] Final data saved to: {output_file}")

            csv_path = 'CBB_Output.csv'

            # Preserve opening odds from previous run (don't overwrite first-seen values)
            result_df = preserve_opening_odds(result_df, csv_path)

            result_df.to_csv(csv_path, index=False)
            logger.info(f"[green]✓[/green] CSV output saved to: {csv_path}")

            # Create daily backup
            backup_daily_output(csv_path)

        else:
            logger.warning("[yellow]⚠[/yellow] No odds data available (games may have completed)")
            # Don't fail - just skip updating the output file

    except Exception as e:
        logger.error(f"[red]✗[/red] Error in OddsAPI script: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

    logger.info("=== OddsAPI script completed successfully ===")