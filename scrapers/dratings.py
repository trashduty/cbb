import pandas as pd
import requests
from bs4 import BeautifulSoup
import numpy as np
import re
from io import StringIO

def fetch_dratings():
    """
    Fetches game data from dratings.com using BeautifulSoup.
    """
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/91.0.4472.124 Safari/537.36')
    }
    url = "https://www.dratings.com/predictor/ncaa-basketball-predictions/"
    response = requests.get(url, headers=headers)
    response.encoding = 'utf-8'

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', class_='tablesaw')

    if not table:
        print("No table found on the page.")
        return pd.DataFrame()

    # Get all rows
    rows = table.find_all('tr')[1:]  # Skip header row
    vegas_spreads = []

    for row in rows:
        # Get all td cells with empty class
        spread_cells = row.find_all('td', class_='')
        if len(spread_cells) >= 2:  # Ensure we have enough cells
            # Get the second cell (spreads)
            spread_cell = spread_cells[1]
            vegas_div = spread_cell.find('div', class_='vegas-sportsbook')
            if vegas_div:
                # Split on <br> tags and get text
                spreads = [text for text in vegas_div.stripped_strings]
                vegas_spreads.append(spreads if spreads else [None, None])
            else:
                vegas_spreads.append([None, None])

    # Get the rest of the table data
    table_html = str(table)
    html_io = StringIO(table_html)

    try:
        tables = pd.read_html(html_io)
        if not tables:
            print("No data could be extracted from the table.")
            return pd.DataFrame()
        df = tables[0]
        # Add the vegas spreads as a new column
        df['vegas_spreads'] = vegas_spreads if vegas_spreads else None
        return df
    except Exception as e:
        print(f"Error parsing table: {str(e)}")
        return pd.DataFrame()

def clean_dratings(df):
    """
    Cleans the DataFrame by processing team names, vegas spreads, win probabilities,
    and the projected total.
    """
    if df.empty:
        return df

    df_clean = df.copy()

    # Standardize column names
    df_clean.columns = df_clean.columns.str.strip().str.replace(' ', '_').str.lower()

    # Extract team names
    team_pattern = (r'(?P<AwayTeam>.+?)\s*\((?P<AwayRecord>\d+-\d+)\)\s*'
                    r'(?P<HomeTeam>.+?)\s*\((?P<HomeRecord>\d+-\d+)\)')
    teams_extracted = df_clean['teams'].str.extract(team_pattern)

    df_clean['Away Team'] = teams_extracted['AwayTeam'].str.strip()
    df_clean['Home Team'] = teams_extracted['HomeTeam'].str.strip()

    # Extract win probabilities
    win_pattern = r'(?P<AwayWinPct>\d+\.?\d*)%\s*(?P<HomeWinPct>\d+\.?\d*)%'
    win_extracted = df_clean['win'].str.extract(win_pattern)
    df_clean['Away Team Win Probability'] = pd.to_numeric(win_extracted['AwayWinPct'], errors='coerce')
    df_clean['Home Team Win Probability'] = pd.to_numeric(win_extracted['HomeWinPct'], errors='coerce')

    def extract_vegas_spread(spreads):
        """
        Extracts the vegas spread values from the list of two spreads
        """
        if not isinstance(spreads, list) or len(spreads) != 2:
            return (np.nan, np.nan)

        away_spread = spreads[0]
        home_spread = spreads[1]

        if not away_spread or not home_spread:
            return (np.nan, np.nan)

        # Extract just the spread numbers
        away_pattern = r'([+-]\d+(?:½|\.\d+)?)'
        home_pattern = r'([+-]\d+(?:½|\.\d+)?)'

        away_match = re.search(away_pattern, away_spread)
        home_match = re.search(home_pattern, home_spread)

        if away_match and home_match:
            away = away_match.group(1).replace('½', '.5')
            home = home_match.group(1).replace('½', '.5')
            return (float(away), float(home))

        return (np.nan, np.nan)

    try:
        # Extract and convert spreads
        spreads_result = df_clean['vegas_spreads'].apply(extract_vegas_spread)
        df_clean['Away Team Spread'] = spreads_result.apply(lambda x: x[0])
        df_clean['Home Team Spread'] = spreads_result.apply(lambda x: x[1])

    except Exception as e:
        print(f"Error processing spreads: {str(e)}")
        df_clean['Away Team Spread'] = np.nan
        df_clean['Home Team Spread'] = np.nan

    # Process the projected total
    df_clean['Projected Total'] = pd.to_numeric(df_clean['total_points'], errors='coerce')

    # Order the final columns
    final_columns = [
        'Away Team',
        'Home Team',
        'Away Team Spread',
        'Home Team Spread',
        'Away Team Win Probability',
        'Home Team Win Probability',
        'Projected Total'
    ]
    return df_clean[final_columns]

def transform_dratings_format(df):
    """
    Transforms DRatings DataFrame from one row per game to two rows per game
    with team-specific stats
    """
    if df.empty:
        print("Empty DataFrame received in transform_dratings_format")
        return df

    # Create empty list to store transformed rows
    transformed_rows = []

    for _, row in df.iterrows():
        try:
            # Create home team row
            home_row = {
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Home Team'],
                # 'Game Date': row.get('Date', None),  # Use get() in case Date column doesn't exist
                'spread_drating': row['Home Team Spread'],
                'win_prob_drating': row['Home Team Win Probability'] / 100,  # Convert percentage to decimal
                'projected_total_drating': float(row['Projected Total'])
            }

            # Create away team row
            away_row = {
                'Home Team': row['Home Team'],
                'Away Team': row['Away Team'],
                'Team': row['Away Team'],
                # 'Game Date': row.get('Date', None),
                'spread_drating': row['Away Team Spread'],
                'win_prob_drating': row['Away Team Win Probability'] / 100,  # Convert percentage to decimal
                'projected_total_drating': float(row['Projected Total'])
            }

            transformed_rows.extend([home_row, away_row])

        except KeyError as e:
            print(f"KeyError while transforming row: {e}")
            print(f"Row contents: {row}")

    if not transformed_rows:
        print("No rows were transformed successfully")
        return pd.DataFrame()

    # Create new DataFrame from transformed rows
    new_df = pd.DataFrame(transformed_rows)

    # Ensure columns are in consistent order
    column_order = [
        'Home Team',
        'Away Team',
        'Team',
        # 'Game Date',
        'spread_drating',
        'win_prob_drating',
        'projected_total_drating'
    ]

    return new_df[column_order]

def map_team_names(df):
    """Map team names using crosswalk"""
    crosswalk = pd.read_csv('crosswalk.csv')
    name_map = crosswalk.set_index('drating')['API'].to_dict()

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
def get_dratings_df():
    df_raw = fetch_dratings()
    df_final = clean_dratings(df_raw)
    df_final = transform_dratings_format(df_final)
    df_final = map_team_names(df_final)
    return df_final

# Main execution
if __name__ == '__main__':
    df_raw = fetch_dratings()
    df_final = clean_dratings(df_raw)
    print("\nFinal processed data:")
    print(df_final)
    df_final.to_csv('test_dratings.csv')
