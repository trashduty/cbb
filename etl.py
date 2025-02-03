import os
import requests
import pandas as pd
from scrapers import evanmiya, get_barttorvik_df,get_kenpom_df,get_dratings_df,get_evanmiya_df
import numpy as np
from datetime import datetime, timezone
from statistics import median
# from dotenv import load_dotenv

# load_dotenv()


def get_odds_data(sport="basketball_ncaab", region="us", markets="h2h,spreads,totals"):
    """
    Fetches odds data from the API for specified sport and markets.
    """
    key = os.getenv("ODDS_API_KEY")
    if not key:
        raise ValueError("ODDSAPI key not found in environment variables.")

    base_url = "https://api.the-odds-api.com"
    odds_url = f"{base_url}/v4/sports/{sport}/odds/?apiKey={key}&regions={region}&markets={markets}&oddsFormat=american"

    try:
        response = requests.get(odds_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Error occurred: {err}")
        return None

def get_moneyline_odds(data):
    """
    Processes moneyline odds into a DataFrame with two rows per game (home and away teams),
    using the median price across all available bookmakers.
    """
    # Dictionary to store all moneylines for each team in each game
    moneyline_dict = {}

    for game in data:
        game_time = game.get('commence_time')
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

    # Build final records with median prices
    h2h_records = []
    for (game_key, side), prices in moneyline_dict.items():
        if not prices:
            continue

        # Calculate median of all collected prices
        med_price = median(prices)

        # Parse game info from the key
        game_time, teams = game_key.split('_', 1)
        home_team, away_team = teams.split('_vs_')

        if side == 'home':
            team_name = home_team
        else:
            team_name = away_team

        h2h_records.append({
            'Game Time': game_time,
            'Home Team': home_team,
            'Away Team': away_team,
            'Team': team_name,
            'Moneyline': med_price,
            'Sportsbook': 'CONSENSUS'  # Indicates this is a median across books
        })

    return pd.DataFrame(h2h_records)

def get_spread_odds(data):
    """
    Processes spread odds into a DataFrame with two rows per game (home and away teams),
    using the median of all available sportsbooks.
    """
    # Dictionary to store all spreads and prices for each team in each game
    spread_dict = {}

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

    # Filter out live/ended games by checking commence_time < now
    now_utc = datetime.now(timezone.utc)
    filtered_data = []
    for game in data:
        # The Odds API returns commence_time in ISO8601 string format (e.g. "2025-02-05T01:30:00Z")
        # Remove trailing 'Z' if present, then parse it as UTC
        raw_time_str = game.get("commence_time")
        if not raw_time_str:
            # If for some reason it's missing commence_time, skip this game
            continue

        # Convert to a datetime with UTC tz
        # .replace() is used to handle trailing 'Z' by removing it before fromisoformat
        game_time_utc = datetime.fromisoformat(raw_time_str.replace("Z", "")).replace(tzinfo=timezone.utc)

        # Keep only if commence_time is still in the future
        if game_time_utc > now_utc:
            filtered_data.append(game)

    # If everything got filtered out, return empty DataFrame
    if not filtered_data:
        return pd.DataFrame()

    # Get DataFrames and process using filtered data
    moneyline_df = get_moneyline_odds(filtered_data).drop(columns=['Sportsbook'])
    spreads_df = get_spread_odds(filtered_data).drop(columns=['Sportsbook']).rename(
        columns={'Spread': 'Opening Spread'})
    totals_df = get_totals_odds(filtered_data).drop(columns=['Sportsbook'])

    # Merge data
    combined_df = pd.merge(
        moneyline_df,
        spreads_df,
        on=['Game Time', 'Home Team', 'Away Team', 'Team'],
        how='outer'
    )

    combined_df = pd.merge(
        combined_df,
        totals_df,
        on=['Game Time', 'Home Team', 'Away Team'],
        how='outer'
    )

    # Create game identifier
    combined_df.insert(0, 'Game',
        combined_df['Home Team'] + " vs. " + combined_df['Away Team'])

    return combined_df

def american_odds_to_implied_probability(odds):
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)

def run_etl():
    # Get data from sources
    odds_df = get_combined_odds()
    barttorvik = get_barttorvik_df(include_tomorrow=True)
    kenpom = get_kenpom_df()
    dratings = get_dratings_df()
    evanmiya = get_evanmiya_df()

    # Merge data
    final_df = pd.merge(
        barttorvik,
        odds_df,
        on=['Home Team', 'Away Team', 'Team'],
        how='inner'
    )
    final_df = pd.merge(
        final_df,
        kenpom,
        on=['Home Team', 'Away Team', 'Team'],
        how='left'
    )
    final_df = pd.merge(
        final_df,
        dratings,
        on=['Home Team', 'Away Team', 'Team'],
        how='left',
    )
    final_df = pd.merge(
        final_df,
        evanmiya,
        on=['Home Team', 'Away Team', 'Team'],
        how='left',
    )

    # Calculate spread implied probability
    final_df['spread_implied_prob'] = final_df['Spread Price'].apply(american_odds_to_implied_probability)



    # # Add stub columns for other prediction models
    # # Spread predictions
    # for model in ['drating', 'kenpom', 'evanmiya']:
    #     final_df[f'spread_{model}'] = np.nan

    # # Win probabilities
    # for model in ['drating', 'kenpom', 'evanmiya']:
    #     final_df[f'win_prob_{model}'] = np.nan

    # # Add projected_total columns for other models
    # for model in ['drating', 'kenpom', 'evanmiya']:
    #     final_df[f'projected_total_{model}'] = np.nan

        # Add stub columns for other prediction models
    # # Spread predictions
    # for model in ['drating', 'evanmiya']:
    #     final_df[f'spread_{model}'] = np.nan

    # # Win probabilities
    # for model in ['drating', 'evanmiya']:
    #     final_df[f'win_prob_{model}'] = np.nan

    # # Add projected_total columns for other models
    # for model in ['drating', 'evanmiya']:
    #     final_df[f'projected_total_{model}'] = np.nan

    # Rename columns to match requirements
    final_df.rename(columns={
        'Spread': 'Opening Spread',
        'Spread Price': 'Spread Price',
        'Moneyline': 'Opening Moneyline',
        'Projected Total': 'theoddsapi_total'  # Rename for clarity
    }, inplace=True)
    # Calculate moneyline probabilities and edge
    final_df['ml_implied_prob'] = final_df['Opening Moneyline'].apply(american_odds_to_implied_probability)
    win_prob_cols = ['win_prob_barttorvik', 'win_prob_drating', 'win_prob_kenpom', 'win_prob_evanmiya']
    final_df['Moneyline Win Probability'] = final_df[win_prob_cols].mean(axis=1, skipna=True)
    final_df['Moneyline Edge'] = final_df['Moneyline Win Probability'] - final_df['ml_implied_prob']
    final_df.drop(columns=['ml_implied_prob'], inplace=True)

    # Calculate forecasted spread (average of non-NaN model predictions)
    spread_models = ['spread_barttorvik', 'spread_drating', 'spread_kenpom', 'spread_evanmiya']
    final_df['forecasted_spread'] = final_df[spread_models].median(axis=1, skipna=True)

    # Calculate Predicted Outcome
    final_df['Predicted Outcome'] = (0.6 * final_df['Opening Spread'] +
                                    0.4 * final_df['forecasted_spread'])

    # Load spreads lookup data
    try:
        lookup_df = pd.read_csv('spreads_lookup.csv')
        # Round predicted outcome for matching
        final_df['Predicted Outcome'] = final_df['Predicted Outcome'].round().astype(int)

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
    projected_total_models = ['projected_total_barttorvik', 'projected_total_drating',
                            'projected_total_kenpom', 'projected_total_evanmiya']

    # Handle missing totals data
    final_df['theoddsapi_total'] = pd.to_numeric(final_df['theoddsapi_total'], errors='coerce')
    final_df['forecasted_total'] = final_df[projected_total_models].median(axis=1, skipna=True)

    # Fill missing averages with theoddsapi_total and round to integer
    final_df['average_total'] = (
        (0.6 * final_df['theoddsapi_total'].fillna(0) +
        0.4 * final_df['forecasted_total'].fillna(final_df['theoddsapi_total']))
    ).round().astype(pd.Int64Dtype())  # Round to integer here

    # Load and process totals lookup data
    try:
        totals_lookup_df = pd.read_csv('totals_lookup.csv')

        # Handle Market Line (theoddsapi_total) with 0.5 increments
        final_df['theoddsapi_total_rounded'] = (final_df['theoddsapi_total']
                                            .apply(lambda x: round(x * 2)/2 if pd.notnull(x) else np.nan))

        # Convert lookup table columns to correct types
        totals_lookup_df['Market Line'] = totals_lookup_df['Market Line'].astype(float)
        totals_lookup_df['True Line'] = totals_lookup_df['True Line'].astype(pd.Int64Dtype())

        # Merge using the already rounded average_total
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
    final_df['Game Time'] = pd.to_datetime(final_df['Game Time'])
    final_df = final_df.sort_values('Game Time', ascending=True)
    # Define final column order
    column_order = [
        'Game', 'Team', 'Predicted Outcome', 'Spread Cover Probability',
        'Opening Spread', 'Edge For Covering Spread', 'spread_barttorvik',
        'spread_drating', 'spread_kenpom', 'spread_evanmiya',
        'Moneyline Win Probability', 'Opening Moneyline', 'Moneyline Edge',
        'win_prob_barttorvik', 'win_prob_drating', 'win_prob_kenpom', 'win_prob_evanmiya',
        'average_total', 'theoddsapi_total', 'projected_total_barttorvik',
        'projected_total_drating', 'projected_total_kenpom', 'projected_total_evanmiya',
        'Over Cover Probability', 'Under Cover Probability',
        'Over Total Edge', 'Under Total Edge'
    ]

    return final_df[column_order].reset_index(drop=True)
# Example usage to save combined odds
if __name__ == "__main__":

    run_etl().to_csv('CBB Output.csv')
