import os
import requests
import pandas as pd
from scrapers import get_barttorvik_df
import numpy as np 
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
    Processes moneyline odds into a DataFrame with two rows per game (home and away teams).
    """
    h2h_records = []
    for game in data:
        game_time = game.get('commence_time')
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        
        if not all([game_time, home_team, away_team]):
            continue
            
        for bookmaker in game.get('bookmakers', []):
            sportsbook = bookmaker.get('title')
            if sportsbook != 'FanDuel':
                continue  # Skip non-FanDuel bookmakers
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'h2h':
                    outcomes = market.get('outcomes', [])
                    home_ml = away_ml = None
                    for outcome in outcomes:
                        if outcome.get('name') == home_team:
                            home_ml = outcome.get('price')
                        elif outcome.get('name') == away_team:
                            away_ml = outcome.get('price')
                    
                    # Append rows for home and away teams
                    h2h_records.append({
                        'Game Time': game_time,
                        'Home Team': home_team,
                        'Away Team': away_team,
                        'Team': home_team,
                        'Moneyline': home_ml,
                        'Sportsbook': sportsbook
                    })
                    h2h_records.append({
                        'Game Time': game_time,
                        'Home Team': home_team,
                        'Away Team': away_team,
                        'Team': away_team,
                        'Moneyline': away_ml,
                        'Sportsbook': sportsbook
                    })
                    break  # Processed FanDuel, move to next game
            break  # Only process FanDuel
    
    return pd.DataFrame(h2h_records)

def get_spread_odds(data):
    """
    Processes spread odds into a DataFrame with two rows per game (home and away teams).
    """
    spreads_records = []
    for game in data:
        game_time = game.get('commence_time')
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        
        if not all([game_time, home_team, away_team]):
            continue
            
        for bookmaker in game.get('bookmakers', []):
            sportsbook = bookmaker.get('title')
            if sportsbook != 'FanDuel':
                continue  # Skip non-FanDuel bookmakers
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'spreads':
                    outcomes = market.get('outcomes', [])
                    home_spread = away_spread = home_price = away_price = None
                    for outcome in outcomes:
                        if outcome.get('name') == home_team:
                            home_spread = outcome.get('point')
                            home_price = outcome.get('price')
                        elif outcome.get('name') == away_team:
                            away_spread = outcome.get('point')
                            away_price = outcome.get('price')
                            
                    # Append rows for home and away teams
                    spreads_records.append({
                        'Game Time': game_time,
                        'Home Team': home_team,
                        'Away Team': away_team,
                        'Team': home_team,
                        'Spread': home_spread,
                        'Spread Price': home_price,
                        'Sportsbook': sportsbook
                    })
                    spreads_records.append({
                        'Game Time': game_time,
                        'Home Team': home_team,
                        'Away Team': away_team,
                        'Team': away_team,
                        'Spread': away_spread,
                        'Spread Price': away_price,
                        'Sportsbook': sportsbook
                    })
                    break  # Processed FanDuel, move to next game
            break  # Only process FanDuel
    
    return pd.DataFrame(spreads_records)

def get_totals_odds(data):
    """
    Processes totals odds into a DataFrame with one row per game.
    """
    totals_records = []
    for game in data:
        game_time = game.get('commence_time')
        home_team = game.get('home_team')
        away_team = game.get('away_team')
        
        if not all([game_time, home_team, away_team]):
            continue
            
        for bookmaker in game.get('bookmakers', []):
            sportsbook = bookmaker.get('title')
            if sportsbook != 'FanDuel':
                continue  # Skip non-FanDuel bookmakers
            for market in bookmaker.get('markets', []):
                if market.get('key') == 'totals':
                    outcomes = market.get('outcomes', [])
                    over = under = over_price = under_price = None
                    for outcome in outcomes:
                        if outcome.get('name') == 'Over':
                            over = outcome.get('point')
                            over_price = outcome.get('price')
                        elif outcome.get('name') == 'Under':
                            under = outcome.get('point')
                            under_price = outcome.get('price')
                            
                    projected_total = (over + under) / 2 if over and under else None
                    
                    totals_records.append({
                        'Game Time': game_time,
                        'Home Team': home_team,
                        'Away Team': away_team,
                        'Projected Total': projected_total,
                        'Over Point': over,
                        'Over Price': over_price,
                        'Under Point': under,
                        'Under Price': under_price,
                        'Sportsbook': sportsbook
                    })
                    break  # Processed FanDuel, move to next game
            break  # Only process FanDuel
    
    return pd.DataFrame(totals_records)
def get_combined_odds():
    data = get_odds_data()
    if not data:
        return pd.DataFrame()
    
    # Get DataFrames and process
    moneyline_df = get_moneyline_odds(data).drop(columns=['Sportsbook'])
    spreads_df = get_spread_odds(data).drop(columns=['Sportsbook']).rename(
        columns={'Spread': 'Opening Spread'})
    totals_df = get_totals_odds(data).drop(columns=['Sportsbook'])
    
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

    # Merge data
    final_df = pd.merge(
        barttorvik,
        odds_df,
        on=['Home Team', 'Away Team', 'Team'],
        how='inner'
    )
    
    # Calculate spread implied probability
    final_df['spread_implied_prob'] = final_df['Spread Price'].apply(american_odds_to_implied_probability)



    # Add stub columns for other prediction models
    # Spread predictions
    for model in ['drating', 'kenpom', 'evanmiya']:
        final_df[f'spread_{model}'] = np.nan
    
    # Win probabilities
    for model in ['drating', 'kenpom', 'evanmiya']:
        final_df[f'win_prob_{model}'] = np.nan

    # Add projected_total columns for other models
    for model in ['drating', 'kenpom', 'evanmiya']:
        final_df[f'projected_total_{model}'] = np.nan

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
    final_df['forecasted_spread'] = final_df[spread_models].mean(axis=1, skipna=True)

    # Calculate Predicted Outcome
    final_df['Predicted Outcome'] = (0.7 * final_df['Opening Spread'] + 
                                    0.3 * final_df['forecasted_spread'])

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
    final_df['forecasted_total'] = final_df[projected_total_models].mean(axis=1, skipna=True)

    # Fill missing averages with theoddsapi_total and round to integer
    final_df['average_total'] = (
        (0.7 * final_df['theoddsapi_total'].fillna(0) + 
        0.3 * final_df['forecasted_total'].fillna(final_df['theoddsapi_total']))
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