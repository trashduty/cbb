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
    odds_url = f"{base_url}/v4/sports/{sport}/odds/?apiKey={key}&regions={region}&markets={markets}&oddsFormat=american"

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
            
            # Filter out live games using commence_time
            current_time = datetime.now(timezone('UTC'))
            data = [game for game in data if datetime.strptime(game['commence_time'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone('UTC')) > current_time]
            logger.info(f"[cyan]Filtered to {len(data)} upcoming games[/cyan]")
            
            # Create a rich table to display the data
            table = Table(
                title=f"OddsAPI Request ({len(data)} upcoming games)",
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
    Only includes games where both home and away prices are available for proper devigging.
    """
    # Dictionary to store all moneylines for each team in each game
    moneyline_dict = {}

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

        # Collect all moneylines from each sportsbook
        for bookmaker in game.get('bookmakers', []):
            sportsbook = bookmaker.get('title')
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'h2h':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        team_name = outcome.get('name')
                        price = outcome.get('price')

                        if team_name == home_team and price is not None:
                            moneyline_dict[(game_key, 'home')].append(price)
                        elif team_name == away_team and price is not None:
                            moneyline_dict[(game_key, 'away')].append(price)

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

        # Add home team record
        h2h_records.append({
            'Game Time': game_time,  # Keep ISO format
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': home_team,
            'Moneyline': med_home_price,
            'Devigged Probability': devigged_home_prob,
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
            'Sportsbook': 'CONSENSUS'
        })

    return pd.DataFrame(h2h_records)

def get_spread_odds(data):
    """
    Processes spread odds into a DataFrame with two rows per game (home and away teams),
    using the median of all available sportsbooks.
    """
    # Dictionary to store all spreads and prices for each team in each game
    spread_dict = {}

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

        # Collect spreads from each sportsbook
        for bookmaker in game.get('bookmakers', []):
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
                        elif team_name == away_team and point is not None and price is not None:
                            spread_dict[(game_key, 'away')]['points'].append(point)
                            spread_dict[(game_key, 'away')]['prices'].append(price)

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

        spreads_records.append({
            'Game Time': game_time,
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': team_name,
            'Spread': med_point,
            'Spread Price': med_price,
            'Sportsbook': 'CONSENSUS'  # Indicates this is a median across books
        })

    return pd.DataFrame(spreads_records)

def get_totals_odds(data):
    """
    Processes totals odds into a DataFrame with one row per game,
    using the median of all available sportsbooks for over/under lines and prices.
    """
    # Dictionary to store all totals data for each game
    totals_dict = {}

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

        # Collect totals from each sportsbook
        for bookmaker in game.get('bookmakers', []):
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'totals':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        if outcome.get('name') == 'Over':
                            if outcome.get('point') is not None:
                                totals_dict[game_key]['over_points'].append(outcome['point'])
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

        totals_records.append({
            'Game Time': game_time,
            'Home Team': home_team,
            'Away Team': away_team,
            'Projected Total': projected_total,
            'Over Point': med_over_point,
            'Over Price': med_over_price,
            'Under Point': med_under_point,
            'Under Price': med_under_price,
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
        columns={'Spread': 'Opening Spread'})
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
    swapped_odds_df['Opening Spread'] = -swapped_odds_df['Opening Spread']
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
    
    return result_df

def process_final_dataframe(final_df):
    """
    Process the final dataframe with spreads and totals lookup tables.
    Apply the requested calculations and return a formatted dataframe.
    """
    logger.info("[cyan]Processing final dataframe with lookup tables...[/cyan]")
    # Set theoddsapi_total for the lookups
    final_df['theoddsapi_total'] = final_df['Projected Total']

    # Calculate median of spreads across all models
    spread_models = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    final_df['forecasted_spread'] = final_df[spread_models].median(axis=1)

    # Rename columns for clarity
    final_df['market_spread'] = final_df['Opening Spread']
    final_df['model_spread'] = final_df['forecasted_spread']

    # Create total_category based on market total (for spread predictions)
    final_df['total_category'] = pd.cut(
        final_df['theoddsapi_total'],
        bins=[-float('inf'), 137.5, 145.5, float('inf')],
        labels=[1, 2, 3]
    ).astype('Int64')

    # Calculate Predicted Outcome using market_spread and model_spread
    final_df['Predicted Outcome'] = (0.6 * final_df['market_spread'] +
                                    0.4 * final_df['model_spread'])
        # Load spreads lookup data
    try:
        spreads_lookup_path = os.path.join(data_dir, 'spreads_lookup.csv')
        logger.info(f"[cyan]Loading spreads lookup data from {spreads_lookup_path}[/cyan]")
        lookup_df = pd.read_csv(spreads_lookup_path)
        
        # Round predicted outcome for matching and handle NaN values
        final_df['Predicted Outcome'] = final_df['Predicted Outcome'].fillna(0).round()
        final_df['Predicted Outcome'] = final_df['Predicted Outcome'].astype(int)

        # Round Opening Spread to nearest 0.5 for proper lookup matching
        if 'Opening Spread' in final_df.columns:
            # Round to nearest 0.5 by multiplying by 2, rounding, then dividing by 2
            final_df['Opening Spread_Rounded'] = (final_df['Opening Spread'] * 2).round() / 2
        else:
            final_df['Opening Spread_Rounded'] = 0

        # Calculate spread implied probability from Spread Price
        if 'Spread Price' in final_df.columns:
            final_df['spread_implied_prob'] = final_df['Spread Price'].apply(american_odds_to_implied_probability)
        else:
            # If Spread Price doesn't exist, initialize with 0.5 (50% probability)
            final_df['spread_implied_prob'] = 0.5

        # Merge with lookup data using the rounded spread
        final_df = final_df.merge(
            lookup_df,
            left_on=['Opening Spread_Rounded', 'Predicted Outcome'],
            right_on=['spread', 'result'],
            how='left'
        )
        # Calculate cover probability and edge
        final_df['Spread Cover Probability'] = final_df['cover_prob']
        final_df['Edge For Covering Spread'] = (
            final_df['Spread Cover Probability'] -
            final_df['spread_implied_prob']
        )
        logger.info(f"[green]✓[/green] Successfully applied spreads lookup")
    except FileNotFoundError:
        logger.warning("[yellow]⚠[/yellow] spreads_lookup.csv not found")
        final_df['Spread Cover Probability'] = np.nan
        final_df['Edge For Covering Spread'] = np.nan
        # Clean up temporary columns even if lookup failed
        final_df.drop(columns=['Opening Spread_Rounded'], inplace=True, errors='ignore')
    
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
    final_df['spread_category'] = pd.cut(
        final_df['market_spread'],
        bins=[-float('inf'), -10.0, -2.5, float('inf')],
        labels=[1, 2, 3]
    ).astype('Int64')

    # Add totals standard deviation here
    final_df['Totals Std. Dev.'] = final_df[projected_total_models].std(axis=1, skipna=True).round(1)

    # Fill missing averages with market_total and model_total, round to integer
    final_df['average_total'] = (
        (0.6 * final_df['market_total'].fillna(0) +
        0.4 * final_df['model_total'].fillna(final_df['market_total']))
    ).round().astype(pd.Int64Dtype())
    
    # Load and process totals lookup data
    try:
        totals_lookup_path = os.path.join(data_dir, 'totals_lookup.csv')
        logger.info(f"[cyan]Loading totals lookup data from {totals_lookup_path}[/cyan]")
        totals_lookup_df = pd.read_csv(totals_lookup_path)

        # Convert lookup table columns to correct types
        totals_lookup_df['Market Line'] = totals_lookup_df['Market Line'].astype(float)
        totals_lookup_df['True Line'] = totals_lookup_df['True Line'].astype(pd.Int64Dtype())

        # Drop any duplicate rows before merging
        final_df = final_df.drop_duplicates(subset=['Game', 'Team'], keep='first')

        # Use theoddsapi_total directly since it's already rounded to 0.5
        final_df = final_df.merge(
            totals_lookup_df,
            left_on=['theoddsapi_total_rounded', 'average_total'],
            right_on=['Market Line', 'True Line'],
            how='left'
        )
        final_df['Over Cover Probability'] = final_df['Over_Probability']
        final_df['Under Cover Probability'] = final_df['Under_Probability']
        final_df.drop(columns=['theoddsapi_total_rounded',
                            'Market Line', 'True Line', 'Over_Probability',
                            'Under_Probability', 'Push_Probability', 'Opening Spread_Rounded',
                            'spread', 'result'], inplace=True, errors='ignore')
        logger.info(f"[green]✓[/green] Successfully applied totals lookup")
    except FileNotFoundError:
        logger.warning("[yellow]⚠[/yellow] totals_lookup.csv not found. Skipping Over/Under probabilities.")
        final_df['Over Cover Probability'] = np.nan
        final_df['Under Cover Probability'] = np.nan
        # Clean up temporary columns even if lookup failed
        final_df.drop(columns=['theoddsapi_total_rounded'], inplace=True, errors='ignore')

    # Calculate totals implied probabilities and edges
    final_df['over_implied_prob'] = final_df['Over Price'].apply(american_odds_to_implied_probability)
    final_df['under_implied_prob'] = final_df['Under Price'].apply(american_odds_to_implied_probability)
    final_df['Over Total Edge'] = final_df['Over Cover Probability'] - final_df['over_implied_prob']
    final_df['Under Total Edge'] = final_df['Under Cover Probability'] - final_df['under_implied_prob']

    # Calculate spread standard deviation
    spread_models = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    final_df['Spread Std. Dev.'] = final_df[spread_models].std(axis=1, skipna=True).round(1)
    
    # Calculate totals standard deviation
    projected_total_models = ['projected_total_barttorvik', 'projected_total_kenpom', 
                             'projected_total_evanmiya', 'projected_total_hasla']
    final_df['Totals Std. Dev.'] = final_df[projected_total_models].std(axis=1, skipna=True).round(1)
    
    # Calculate moneyline standard deviation
    win_prob_models = ['win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya']
    final_df['Moneyline Std. Dev.'] = final_df[win_prob_models].std(axis=1, skipna=True).round(3)

    # Calculate moneyline probabilities and edge using devigged probabilities
    win_prob_cols = ['win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya']
    final_df['Moneyline Win Probability'] = final_df[win_prob_cols].median(axis=1, skipna=True)
    final_df['Moneyline Win Probability'] = (0.5*final_df['Moneyline Win Probability']+0.5*final_df['Devigged Probability'])
    final_df['ml_implied_prob'] = final_df['Moneyline'].apply(american_odds_to_implied_probability)
    final_df['Moneyline Edge'] = final_df['Moneyline Win Probability'] - final_df['ml_implied_prob']

    # Keep rows with missing devigged probabilities, just fill with 0
    final_df['Devigged Probability'] = final_df['Devigged Probability'].fillna(0)
    final_df['Moneyline Edge'] = final_df['Moneyline Edge'].fillna(0)

    # Rename 'Moneyline' column to 'Opening Moneyline' if it exists
    if 'Moneyline' in final_df.columns:
        # Round moneyline values to the nearest integer
        final_df['Opening Moneyline'] = final_df['Moneyline'].round().astype('Int64')
    else:
        logger.warning("[yellow]⚠[/yellow] 'Moneyline' column not found, creating empty 'Opening Moneyline' column")
        final_df['Opening Moneyline'] = np.nan

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
        'Game', 'Game Time', 'Team',
        # Spread framework columns
        'total_category', 'market_spread', 'model_spread', 'Predicted Outcome', 'Spread Cover Probability',
        'Opening Spread', 'Edge For Covering Spread', 'Spread Std. Dev.', 'spread_barttorvik',
        'spread_kenpom', 'spread_evanmiya', 'spread_hasla',
        # Moneyline columns
        'Moneyline Win Probability', 'Opening Moneyline', 'Devigged Probability', 'Moneyline Edge', 'Moneyline Std. Dev.',
        'win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya',
        # Totals framework columns
        'spread_category', 'market_total', 'model_total', 'average_total', 'theoddsapi_total', 'Totals Std. Dev.',
        'projected_total_barttorvik', 'projected_total_kenpom', 'projected_total_evanmiya', 'projected_total_hasla',
        'Over Cover Probability', 'Under Cover Probability',
        'Over Total Edge', 'Under Total Edge',
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
    Returns 1 if all models agree on covering the spread (same sign) and match Edge sign.
    Returns 0 otherwise or if any values are missing.
    """
    try:
        # Get required values
        market_spread = row.get('Opening Spread')
        edge = row.get('Edge For Covering Spread')

        # Model spreads
        spread_kenpom = row.get('spread_kenpom')
        spread_evanmiya = row.get('spread_evanmiya')
        spread_barttorvik = row.get('spread_barttorvik')
        spread_hasla = row.get('spread_hasla')

        # Check for missing values
        if pd.isna(market_spread) or pd.isna(edge):
            return 0
        if pd.isna(spread_kenpom) or pd.isna(spread_evanmiya) or pd.isna(spread_barttorvik) or pd.isna(spread_hasla):
            return 0

        # Calculate differences (model_spread - market_spread)
        diff_kenpom = spread_kenpom - market_spread
        diff_evanmiya = spread_evanmiya - market_spread
        diff_barttorvik = spread_barttorvik - market_spread
        diff_hasla = spread_hasla - market_spread

        # Get signs (using np.sign: -1 for negative, 0 for zero, 1 for positive)
        sign_kenpom = np.sign(diff_kenpom)
        sign_evanmiya = np.sign(diff_evanmiya)
        sign_barttorvik = np.sign(diff_barttorvik)
        sign_hasla = np.sign(diff_hasla)
        sign_edge = np.sign(edge)

        # Check if all models have same sign AND match edge sign
        if (sign_kenpom == sign_evanmiya == sign_barttorvik == sign_hasla == sign_edge):
            # Make sure the sign is not zero
            if sign_kenpom != 0:
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
            result_df.to_csv(csv_path, index=False)
            logger.info(f"[green]✓[/green] CSV output saved to: {csv_path}")
            
        else:
            logger.error("[red]✗[/red] Script execution failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"[red]✗[/red] Error in OddsAPI script: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
        
    logger.info("=== OddsAPI script completed successfully ===")