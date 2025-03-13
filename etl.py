import os
import requests
import pandas as pd
from scrapers import get_barttorvik_df,get_kenpom_df, get_hasla_df
import numpy as np
from statistics import median
from dotenv import load_dotenv
from logger_setup import setup_logger
from rich.table import Table
from rich.console import Console
from datetime import datetime, timedelta
from rich.box import MINIMAL
from pytz import timezone
import logging

load_dotenv()

logger = setup_logger('oddsapi')
console = Console()

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
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

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

        med_home_prob = median(home_probs)
        med_away_prob = median(away_probs)

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

def run_etl():
    # Get data from sources
    logger = logging.getLogger('etl')
    
    logger.info("[cyan]Starting ETL process[/cyan]")
    
    odds_df = get_combined_odds()
    logger.info(f"[cyan]Odds data shape:[/cyan] {odds_df.shape}")
    
    barttorvik = get_barttorvik_df(include_tomorrow=True)
    logger.info(f"[cyan]Barttorvik data shape:[/cyan] {barttorvik.shape}")
    
    kenpom = pd.read_csv('data/kp_mapped.csv')
    logger.info(f"[cyan]Kenpom data shape:[/cyan] {kenpom.shape}")
    
    evanmiya = pd.read_csv('data/em_mapped.csv')
    logger.info(f"[cyan]Evanmiya data shape:[/cyan] {evanmiya.shape}")
    
    hasla = get_hasla_df()
    logger.info(f"[cyan]Hasla data shape:[/cyan] {hasla.shape}")
    logger.info(f"[cyan]Hasla columns:[/cyan] {hasla.columns.tolist()}")
    logger.info(f"[cyan]Sample Hasla spreads:[/cyan] {hasla['spread_hasla'].head().tolist()}")

    # Merge data
    logger.info("[cyan]Starting data merges[/cyan]")
    
    # First merge with normal team order
    merge_normal = pd.merge(
        barttorvik,
        odds_df,
        on=['Home Team', 'Away Team', 'Team'],
        how='inner',
        indicator='merge_type'
    )
    
    # Create flipped version of odds_df
    odds_df_flipped = odds_df.copy()
    odds_df_flipped['Home Team_orig'] = odds_df_flipped['Home Team']
    odds_df_flipped['Away Team_orig'] = odds_df_flipped['Away Team']
    odds_df_flipped['Home Team'] = odds_df_flipped['Away Team']
    odds_df_flipped['Away Team'] = odds_df_flipped['Home Team_orig']
    odds_df_flipped.drop(['Home Team_orig', 'Away Team_orig'], axis=1, inplace=True)
    
    # Merge with flipped teams
    merge_flipped = pd.merge(
        barttorvik,
        odds_df_flipped,
        on=['Home Team', 'Away Team', 'Team'],
        how='inner',
        indicator='merge_type'
    )
    
    # Combine both merges, keeping only the matches
    final_df = pd.concat([
        merge_normal[merge_normal['merge_type'] == 'both'],
        merge_flipped[merge_flipped['merge_type'] == 'both']
    ]).drop('merge_type', axis=1)
    
    logger.info(f"[cyan]After odds merge shape:[/cyan] {final_df.shape}")
    
    # Log Duke games after merge
    duke_games = final_df[final_df['Home Team'].str.contains('Duke', na=False) | 
                         final_df['Away Team'].str.contains('Duke', na=False)]
    if not duke_games.empty:
        logger.info("\n[cyan]Duke games after merge:[/cyan]")
        for _, game in duke_games.iterrows():
            logger.info(f"- {game['Away Team']} vs {game['Home Team']}")
    
    # Kenpom merge
    final_df = pd.merge(
        final_df,
        kenpom,
        on=['Home Team', 'Away Team', 'Team'],
        how='left'
    )
    logger.info(f"[cyan]After Kenpom merge shape:[/cyan] {final_df.shape}")
    
    # Evanmiya merge
    final_df = pd.merge(
        final_df,
        evanmiya,
        on=['Home Team', 'Away Team', 'Team'],
        how='left',
    )
    logger.info(f"[cyan]After Evanmiya merge shape:[/cyan] {final_df.shape}")
    
    # Hasla merge
    logger.info("[cyan]Before Hasla merge columns:[/cyan] {final_df.columns.tolist()}")
    logger.info(f"[cyan]Before Hasla merge shape:[/cyan] {final_df.shape}")
    
    # Check for team name matches
    hasla_teams = set(hasla['Team'].unique())
    final_teams = set(final_df['Team'].unique())
    common_teams = hasla_teams.intersection(final_teams)
    logger.info(f"[cyan]Teams in Hasla:[/cyan] {len(hasla_teams)}")
    logger.info(f"[cyan]Teams in final_df:[/cyan] {len(final_teams)}")
    logger.info(f"[cyan]Common teams:[/cyan] {len(common_teams)}")
    
    # Log all teams from both datasets for comparison
    logger.info("\n[cyan]All teams from Hasla:[/cyan]")
    for team in sorted(list(hasla_teams)):
        logger.info(f"- {team}")
    logger.info("\n[cyan]All teams from final_df:[/cyan]")
    for team in sorted(list(final_teams)):
        logger.info(f"- {team}")
    
    # Do the merge
    final_df = pd.merge(
        final_df,
        hasla[['Home Team', 'Away Team', 'Team', 'spread_hasla', 'projected_total_hasla']],  # Only keep needed columns
        on=['Home Team', 'Away Team', 'Team'],
        how='left',
        indicator=True  # This will show which rows matched
    )
    
    # Log merge results
    merge_counts = final_df['_merge'].value_counts()
    logger.info("\n[cyan]Merge results:[/cyan]")
    logger.info(f"Rows from left only: {merge_counts.get('left_only', 0)}")
    logger.info(f"Rows from both: {merge_counts.get('both', 0)}")
    
    # Log some unmatched games
    unmatched = final_df[final_df['_merge'] == 'left_only']
    if not unmatched.empty:
        logger.info("\n[yellow]Sample unmatched games:[/yellow]")
        for _, row in unmatched.head().iterrows():
            logger.info(f"- {row['Away Team']} @ {row['Home Team']}")
    
    # Drop the indicator column
    final_df = final_df.drop('_merge', axis=1)
    
    logger.info(f"[cyan]After Hasla merge shape:[/cyan] {final_df.shape}")
    logger.info(f"[cyan]After Hasla merge columns:[/cyan] {final_df.columns.tolist()}")
    
    # Check if spread_hasla exists and has values
    if 'spread_hasla' in final_df.columns:
        non_null = final_df['spread_hasla'].count()
        logger.info(f"[cyan]spread_hasla non-null count:[/cyan] {non_null}")
        if non_null > 0:
            sample_spreads = final_df[final_df['spread_hasla'].notna()]['spread_hasla'].head()
            logger.info(f"[cyan]Sample spread_hasla values:[/cyan] {sample_spreads.tolist()}")
            
            # Log some matched games with spreads
            logger.info("\n[cyan]Sample matched games with spreads:[/cyan]")
            matched = final_df[final_df['spread_hasla'].notna()]
            for _, row in matched.head().iterrows():
                logger.info(f"- {row['Away Team']} @ {row['Home Team']}: spread={row['spread_hasla']}")
    else:
        logger.error("[red]✗[/red] spread_hasla column not found after merge!")

    # Rename columns FIRST
    final_df.rename(columns={
        'Spread': 'Opening Spread',
        'Spread Price': 'Spread Price',
        'Moneyline': 'Opening Moneyline',
        'Projected Total': 'theoddsapi_total'
    }, inplace=True)

    # Round theoddsapi_total and Opening Spread
    final_df['theoddsapi_total'] = pd.to_numeric(final_df['theoddsapi_total'], errors='coerce')
    final_df['theoddsapi_total'] = final_df['theoddsapi_total'].apply(
        lambda x: round(x * 2) / 2 if pd.notnull(x) else np.nan
    )
    
    final_df['Opening Spread'] = final_df['Opening Spread'].apply(
        lambda x: round(x * 2) / 2 if pd.notnull(x) else np.nan
    )

    # Calculate spread implied probability
    final_df['spread_implied_prob'] = final_df['Spread Price'].apply(american_odds_to_implied_probability)
    final_df['ml_implied_prob'] = final_df['Opening Moneyline'].apply(american_odds_to_implied_probability)

    # Calculate moneyline probabilities and edge using devigged probabilities
    win_prob_cols = ['win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya']
    final_df['Moneyline Win Probability'] = final_df[win_prob_cols].median(axis=1, skipna=True)
    final_df['Moneyline Win Probability'] = (0.5 * final_df['Moneyline Win Probability'] + 0.5 * final_df['Devigged Probability'])

    # Add win probability standard deviation here
    final_df['Moneyline Std. Dev.'] = final_df[win_prob_cols].std(axis=1, skipna=True).round(3)

    final_df['Moneyline Edge'] = final_df['Moneyline Win Probability'] - final_df['ml_implied_prob'] 
    # Calculate forecasted spread (average of non-NaN model predictions, including Hasla)
    spread_models = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    final_df['forecasted_spread'] = final_df[spread_models].median(axis=1, skipna=True)

    # Add debugging for spread values
    logger.info("[cyan]Checking spread values:[/cyan]")
    logger.info(f"Opening Spread sample: {final_df['Opening Spread'].head().tolist()}")
    logger.info(f"Barttorvik spread sample: {final_df['spread_barttorvik'].head().tolist()}")
    logger.info(f"Kenpom spread sample: {final_df['spread_kenpom'].head().tolist()}")
    logger.info(f"Evanmiya spread sample: {final_df['spread_evanmiya'].head().tolist()}")
    logger.info(f"Hasla spread sample: {final_df['spread_hasla'].head().tolist()}")
    logger.info(f"Forecasted spread sample: {final_df['forecasted_spread'].head().tolist()}")

    # Add debugging for spread data types
    logger.info("\n[cyan]Checking spread data types:[/cyan]")
    logger.info(f"Opening Spread dtype: {final_df['Opening Spread'].dtype}")
    logger.info(f"Forecasted spread dtype: {final_df['forecasted_spread'].dtype}")

    # Calculate Predicted Outcome
    final_df['Predicted Outcome'] = (0.7 * final_df['Opening Spread'] +
                                    0.3 * final_df['forecasted_spread'])

    # Add debugging for predicted outcome
    logger.info("\n[cyan]Checking predicted outcome:[/cyan]")
    logger.info(f"Predicted Outcome sample: {final_df['Predicted Outcome'].head().tolist()}")
    logger.info(f"Predicted Outcome dtype: {final_df['Predicted Outcome'].dtype}")

    # Load spreads lookup data
    try:
        lookup_df = pd.read_csv('spreads_lookup.csv')
        # Round predicted outcome for matching and handle NaN values
        final_df['Predicted Outcome'] = final_df['Predicted Outcome'].fillna(0).round()
        final_df['Predicted Outcome'] = final_df['Predicted Outcome'].astype(int)

        # Merge with lookup data
        final_df = final_df.merge(
            lookup_df,
            left_on=['Opening Spread', 'Predicted Outcome'],
            right_on=['spread', 'result'],
            how='left'
        )
        # Calculate cover probability and edge
        final_df['Spread Cover Probability'] = final_df['cover_prob']
        final_df['Edge For Covering Spread'] = (
            final_df['Spread Cover Probability'] -
            final_df['spread_implied_prob']
        )
    except FileNotFoundError:
        print("Warning: spreads_lookup.csv not found")
        final_df['Spread Cover Probability'] = np.nan
        final_df['Edge For Covering Spread'] = np.nan
    # Calculate totals projections
    projected_total_models = ['projected_total_barttorvik',
                            'projected_total_kenpom', 
                            'projected_total_evanmiya',
                            'projected_total_hasla']

    # Handle missing totals data
    final_df['theoddsapi_total'] = pd.to_numeric(final_df['theoddsapi_total'], errors='coerce')
    final_df['forecasted_total'] = final_df[projected_total_models].median(axis=1, skipna=True)

    # Add totals standard deviation here
    final_df['Totals Std. Dev.'] = final_df[projected_total_models].std(axis=1, skipna=True).round(1)

    # Fill missing averages with theoddsapi_total and round to integer
    final_df['average_total'] = (
        (0.55 * final_df['theoddsapi_total'].fillna(0) +
        0.45 * final_df['forecasted_total'].fillna(final_df['theoddsapi_total']))
    ).round().astype(pd.Int64Dtype())
    # Load and process totals lookup data
    try:
        totals_lookup_df = pd.read_csv('totals_lookup.csv')

        # Convert lookup table columns to correct types
        totals_lookup_df['Market Line'] = totals_lookup_df['Market Line'].astype(float)
        totals_lookup_df['True Line'] = totals_lookup_df['True Line'].astype(pd.Int64Dtype())

        # Drop any duplicate rows before merging
        final_df = final_df.drop_duplicates(subset=['Game', 'Team'], keep='first')

        # Use theoddsapi_total directly since it's already rounded to 0.5
        final_df = final_df.merge(
            totals_lookup_df,
            left_on=['theoddsapi_total', 'average_total'],
            right_on=['Market Line', 'True Line'],
            how='left'
        )
        final_df['Over Cover Probability'] = final_df['Over_Probability']
        final_df['Under Cover Probability'] = final_df['Under_Probability']
        final_df.drop(columns=['theoddsapi_total_rounded',
                            'Market Line', 'True Line', 'Over_Probability',
                            'Under_Probability', 'Push_Probability'], inplace=True, errors='ignore')
    except FileNotFoundError:
        print("Warning: totals_lookup.csv not found. Skipping Over/Under probabilities.")
        final_df['Over Cover Probability'] = np.nan
        final_df['Under Cover Probability'] = np.nan

    # Calculate totals implied probabilities and edges
    final_df['over_implied_prob'] = final_df['Over Price'].apply(american_odds_to_implied_probability)
    final_df['under_implied_prob'] = final_df['Under Price'].apply(american_odds_to_implied_probability)
    final_df['Over Total Edge'] = final_df['Over Cover Probability'] - final_df['over_implied_prob']
    final_df['Under Total Edge'] = final_df['Under Cover Probability'] - final_df['under_implied_prob']

    # Calculate spread standard deviation here
    spread_models = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    final_df['Spread Std. Dev.'] = final_df[spread_models].std(axis=1, skipna=True).round(1)

    # Keep rows with missing devigged probabilities, just fill with 0
    final_df['Devigged Probability'] = final_df['Devigged Probability'].fillna(0)
    final_df['Moneyline Edge'] = final_df['Moneyline Edge'].fillna(0)

    # Drop any remaining duplicates after all processing
    final_df = final_df.drop_duplicates(subset=['Game', 'Team'], keep='first')

    logger.info(f"[cyan]Final shape after handling missing devigged probabilities:[/cyan] {final_df.shape}")

    final_df = final_df.sort_values('Game Time', ascending=True)
    # Define final column order
    column_order = [
        'Game', 'Game Time', 'Team', 'Predicted Outcome', 'Spread Cover Probability',
        'Opening Spread', 'Edge For Covering Spread', 'Spread Std. Dev.', 'spread_barttorvik', 
        'spread_kenpom', 'spread_evanmiya', 'spread_hasla',
        'Moneyline Win Probability', 'Opening Moneyline', 'Devigged Probability', 'Moneyline Edge', 'Moneyline Std. Dev.',
        'win_prob_barttorvik', 'win_prob_kenpom', 'win_prob_evanmiya',
        'average_total', 'theoddsapi_total', 'Totals Std. Dev.', 'projected_total_barttorvik',
        'projected_total_kenpom', 'projected_total_evanmiya', 'projected_total_hasla',
        'Over Cover Probability', 'Under Cover Probability',
        'Over Total Edge', 'Under Total Edge']

    return final_df[column_order].reset_index(drop=True)

# Example usage to save combined odds
if __name__ == "__main__":
    run_etl().to_csv('CBB Output.csv')