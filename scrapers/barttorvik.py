import pandas as pd
import requests
from bs4 import BeautifulSoup
import numpy as np
from datetime import datetime, timedelta
from logger_setup import log_scraper_execution
import logging

@log_scraper_execution
def fetch_barttorvik(date=None):
    """
    Fetch Barttorvik data for a specific date
    """
    logger = logging.getLogger('barttorvik')
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    base_url = "https://www.barttorvik.com/schedule.php"
    
    # Build URL with date parameter if provided
    if date:
        url = f"{base_url}?date={date}&conlimit="
        logger.info(f"Fetching data for date: {date}")
    else:
        url = base_url
        logger.info("Fetching data for current date")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logger.info("Successfully retrieved webpage")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        games = []

        for row in soup.find_all('tr'):
            teams = row.find_all('a', href=lambda x: x and 'team.php' in x)
            if len(teams) != 2:
                continue

            line = row.find('a', href=lambda x: x and 'trank.php' in x)
            if not line:
                continue

            games.append({
                'Home Team': teams[1].text.strip(),
                'Away Team': teams[0].text.strip(),
                'T-Rank Line': line.text.strip(),
                'Game Date': date if date else datetime.now().strftime('%Y%m%d')
            })

        logger.info(f"Successfully parsed {len(games)} games")
        return pd.DataFrame(games)

    except requests.RequestException as e:
        logger.error(f"Failed to fetch data: {str(e)}")
        raise

def get_barttorvik_df(include_tomorrow=True):
    """
    Main function to get processed Barttorvik data for today and optionally tomorrow

    Args:
        include_tomorrow (bool): Whether to include tomorrow's games
    """
    # Get today's date and tomorrow's date
    today = datetime.now()
    tomorrow = today + timedelta(days=1)

    # Fetch today's games
    today_raw = fetch_barttorvik(today.strftime('%Y%m%d'))
    today_transformed = transform_barttorvik_data(today_raw)

    if include_tomorrow:
        # Fetch tomorrow's games
        tomorrow_raw = fetch_barttorvik(tomorrow.strftime('%Y%m%d'))
        tomorrow_transformed = transform_barttorvik_data(tomorrow_raw)

        # Combine the dataframes
        combined_df = pd.concat([today_transformed, tomorrow_transformed], ignore_index=True)
    else:
        combined_df = today_transformed

    # Map team names
    mapped_df = map_team_names(combined_df)
    return mapped_df.reset_index(drop=True)

@log_scraper_execution
def transform_barttorvik_data(df):
    """Transform to two-row-per-game format with team-specific stats"""
    logger = logging.getLogger('barttorvik')
    
    pattern = r"^\s*(?P<TeamName>.+?)(?:\s+(?P<Spread>-?\d+\.?\d*))?(?:,\s*(?P<ProjectedScore>\d+-\d+))?\s*\((?P<WinProb>\d+)%\)\s*$"
    extracted = df['T-Rank Line'].str.extract(pattern)
    
    logger.info("Extracting projected scores and win probabilities")
    
    try:
        extracted[['ProjectedHome', 'ProjectedAway']] = (
            extracted['ProjectedScore']
            .str.split('-', expand=True)
            .astype(float)
        )
        extracted['ProjectedTotal'] = extracted['ProjectedHome'] + extracted['ProjectedAway']
        logger.info("Successfully processed projected scores")
    except (TypeError, ValueError):
        logger.warning("Could not process projected scores, setting to NaN")
        extracted['ProjectedTotal'] = np.nan

    base_df = df[['Home Team', 'Away Team', 'Game Date']].copy()
    home_rows = []
    away_rows = []
    failed_rows = []

    logger.info("Processing individual game records")
    
    for idx, row in base_df.iterrows():
        line_data = df.at[idx, 'T-Rank Line']
        
        try:
            team_name = extracted.at[idx, 'TeamName'].strip() if not pd.isna(extracted.at[idx, 'TeamName']) else None
            spread = extracted.at[idx, 'Spread']
            win_prob = extracted.at[idx, 'WinProb']
            projected_total = extracted.at[idx, 'ProjectedTotal']

            # Handle missing spread and win probability
            if any(pd.isna([team_name, win_prob])):
                failed_rows.append(f"Row {idx}: '{line_data}' - Failed to parse required fields")
                continue

            # Set spread to 0 if missing
            spread = 0 if pd.isna(spread) else float(spread)

            # Determine favored team
            is_home_favored = team_name == row['Home Team']
            is_away_favored = team_name == row['Away Team']

            if not (is_home_favored or is_away_favored):
                failed_rows.append(f"Row {idx}: '{line_data}' - Could not match team name '{team_name}' to either home or away team")
                continue

            # Home team record
            home_rows.append({
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Home Team'],
                'Game Date': row['Game Date'],
                'spread_barttorvik': float(spread) if is_home_favored else -float(spread),
                'win_prob_barttorvik': float(win_prob)/100 if is_home_favored else (100 - float(win_prob))/100,
                'projected_total_barttorvik': projected_total if not pd.isna(projected_total) else np.nan
            })

            # Away team record
            away_rows.append({
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Away Team'],
                'Game Date': row['Game Date'],
                'spread_barttorvik': -float(spread) if is_home_favored else float(spread),
                'win_prob_barttorvik': (100 - float(win_prob))/100 if is_home_favored else float(win_prob)/100,
                'projected_total_barttorvik': projected_total if not pd.isna(projected_total) else np.nan
            })

        except Exception as e:
            failed_rows.append(f"Row {idx}: '{line_data}' - Error: {str(e)}")
            continue

    # Print all failed rows at once
    if failed_rows:
        print("\nFailed to process the following rows:")
        for row in failed_rows:
            print(row)

    # Combine home and away records
    return pd.DataFrame(home_rows + away_rows)

def map_team_names(df):
    """Map team names using crosswalk"""
    crosswalk = pd.read_csv('crosswalk.csv')
    name_map = crosswalk.set_index('barttorvik')['API'].to_dict()

    # Create mapping report
    unmapped_teams = {}
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])

    if unmapped_teams:
        print("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            print(f"- {team}: {count} occurrences")

    # Create mapped dataframe
    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)

    # Drop rows with missing mappings
    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    if len(mapped_df) < original_count:
        print(f"\nDropped {original_count - len(mapped_df)} rows due to mapping issues")

    return mapped_df
# # Updated main workflow
# if __name__ == "__main__":
#     # Load and transform both datasets
#     odds_df = pd.read_csv('combined_odds.csv')
#     barttorvik_raw = fetch_barttorvik()
#     barttorvik_clean = transform_barttorvik_data(barttorvik_raw)
#     barttorvik_mapped = map_team_names(barttorvik_clean)

#     # Merge datasets and print unmatched games
#     merged_df = pd.merge(
#         odds_df,
#         barttorvik_mapped,
#         on=['Home Team', 'Away Team', 'Team'],
#         how='left'
#     )

#     # Print games that didn't match
#     unmatched = merged_df[merged_df['spread_barttorvik'].isna()]
#     if not unmatched.empty:
#         print("\nUnmatched games:")
#         for _, row in unmatched.iterrows():
#             print(f"- {row['Away Team']} @ {row['Home Team']}")

#     # Drop unmatched rows
#     rows_before = len(merged_df)
#     merged_df = merged_df.dropna(subset=['spread_barttorvik', 'win_prob_barttorvik'])
#     rows_dropped = rows_before - len(merged_df)
#     if rows_dropped > 0:
#         print(f"\nDropped {rows_dropped} rows due to missing Barttorvik data")

#     # Add calculated fields
#     merged_df['edge'] = merged_df['win_prob_barttorvik'] - merged_df['implied_prob']
#     merged_df['value_bet'] = merged_df['edge'].apply(lambda x: 'Yes' if x > 0.05 else 'No')

#     merged_df.to_csv('value_bets.csv', index=False)
