from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import numpy as np
import re
import time
from datetime import datetime, timedelta
from io import StringIO  # for read_html

def fetch_massey(date_str=None):
    """
    Fetches game data from masseyratings.com using Selenium with Chrome

    Args:
        date_str (str, optional): Date in YYYYMMDD format. If None, uses tomorrow's date.

    Returns:
        pandas.DataFrame: Raw data from Massey Ratings
    """
    # Handle date parameter
    if date_str is None:
        # Default to tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime('%Y%m%d')

    # Validate date format
    try:
        datetime.strptime(date_str, '%Y%m%d')
    except ValueError:
        print(f"Invalid date format: {date_str}. Please use YYYYMMDD format.")
        return pd.DataFrame()

    # Construct URL with date parameter
    url = f"https://masseyratings.com/games?dt={date_str}&id=308932#CB-D1"

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Modern headless mode

    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # Wait for table to load
        wait = WebDriverWait(driver, 10)
        table = wait.until(EC.presence_of_element_located((By.ID, "tableflex")))

        # Click CB-D1 button to ensure we're on basketball
        try:
            cb_button = driver.find_element(By.ID, "fbCB-D1")
            cb_button.click()
            time.sleep(2)  # Brief pause for table update
        except Exception as e:
            print(f"CB-D1 button click failed: {e}")

        # Get updated table and parse with pandas.
        # Wrap the HTML string in StringIO to avoid the FutureWarning.
        table_html = table.get_attribute('outerHTML')
        df = pd.read_html(StringIO(table_html))[0]

        # Validate expected columns
        required_cols = ['Team', 'Pred', 'Pwin', 'Margin']
        if not all(col in df.columns for col in required_cols):
            print("Note: Expected columns not found. Available columns:", df.columns.tolist())
            # If the table already has 'Home Team' and 'Away Team', assume it's already processed.
            if 'Home Team' in df.columns and 'Away Team' in df.columns:
                print("Data appears to be pre-processed.")
            else:
                # Otherwise, as a fallback, if the first column is not 'Team', rename it.
                first_col = df.columns[0]
                print(f"Renaming column '{first_col}' to 'Team'")
                df.rename(columns={first_col: 'Team'}, inplace=True)
                if not all(col in df.columns for col in required_cols):
                    missing = [col for col in required_cols if col not in df.columns]
                    print(f"Missing required columns after renaming: {missing}")
                    return pd.DataFrame()

        # Add date column
        df['Game Date'] = datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
        return df

    except Exception as e:
        print(f"Error fetching Massey data: {e}")
        return pd.DataFrame()

    finally:
        if 'driver' in locals():
            driver.quit()


def clean_massey(df):
    """
    Cleans and processes the raw Massey ratings data.
    If the DataFrame already contains processed columns (i.e. 'Home Team' and 'Away Team'),
    the cleaning step is skipped.

    Args:
        df (pandas.DataFrame): Raw dataframe from fetch_massey()

    Returns:
        pandas.DataFrame: Cleaned and processed data
    """
    if df.empty:
        return df

    print("Raw Massey columns:", df.columns.tolist())

    # If already processed (has both Home Team and Away Team), skip further cleaning.
    if 'Home Team' in df.columns and 'Away Team' in df.columns and 'Team' not in df.columns:
        print("DataFrame appears to be already processed. Skipping cleaning step.")
        return df

    # Otherwise, ensure the 'Team' column exists.
    if 'Team' not in df.columns:
        first_col = df.columns[0]
        print(f"'Team' column not found. Renaming '{first_col}' to 'Team'.")
        df = df.rename(columns={first_col: 'Team'})

    df_clean = df.copy()

    # Filter valid rows (must have exactly one '@' and reasonable length)
    df_clean = df_clean[
        (df_clean['Team'].str.count('@') == 1) &
        (df_clean['Team'].str.len() < 40)
    ].copy()

    # Split the 'Team' column into Away and Home teams
    teams = df_clean['Team'].str.split('@', n=1, expand=True)
    try:
        df_clean['Away Team'] = teams[0].str.strip()
        df_clean['Home Team'] = teams[1].str.strip()
    except Exception as e:
        print("Error splitting the Team column:", e)
        return pd.DataFrame()

    # Process win probabilities (format expected: "XX % YY %")
    prob_pattern = r'^(\d+)\s*%\s*(\d+)\s*%$'
    probs = df_clean['Pwin'].str.extract(prob_pattern)
    df_clean['Away Team Win Probability'] = pd.to_numeric(probs[0], errors='coerce')
    df_clean['Home Team Win Probability'] = pd.to_numeric(probs[1], errors='coerce')
    df_clean = df_clean.dropna(subset=['Away Team Win Probability', 'Home Team Win Probability'])

    # Process predicted scores from the 'Pred' column
    def parse_pred(pred):
        pred = str(pred)
        pred_len = len(pred)
        if pred_len == 4:
            away, home = pred[:2], pred[2:]
        elif pred_len == 5:
            if pred[2] == '1':
                away, home = pred[:2], pred[2:]
            else:
                away, home = pred[:3], pred[3:]
        elif pred_len == 6:
            away, home = pred[:3], pred[3:]
        else:
            return None, None
        try:
            away_score = int(away)
            home_score = int(home)
            if 0 <= away_score <= 200 and 0 <= home_score <= 200:
                return away_score, home_score
        except ValueError:
            pass
        return None, None

    scores = df_clean['Pred'].apply(parse_pred)
    df_clean['Away Score'] = scores.apply(lambda x: x[0])
    df_clean['Home Score'] = scores.apply(lambda x: x[1])
    df_clean = df_clean.dropna(subset=['Away Score', 'Home Score'])
    df_clean['Projected Total'] = df_clean['Away Score'] + df_clean['Home Score']

    # Extract the spread from the 'Margin' column
    def extract_spread(margin):
        numbers = re.findall(r'\d+\.?\d*', str(margin))
        return float(numbers[0]) if numbers else None

    df_clean['Spread'] = df_clean['Margin'].apply(extract_spread)
    df_clean = df_clean.dropna(subset=['Spread'])

    # Assign spreads based on predicted scores
    df_clean['Home Team Spread'] = np.where(
        df_clean['Home Score'] > df_clean['Away Score'],
        -df_clean['Spread'],
        df_clean['Spread']
    )
    df_clean['Away Team Spread'] = -df_clean['Home Team Spread']

    # Select final columns
    final_cols = [
        'Game Date',
        'Home Team',
        'Away Team',
        'Home Team Spread',
        'Away Team Spread',
        'Home Team Win Probability',
        'Away Team Win Probability',
        'Projected Total',
    ]
    return df_clean[final_cols]


def fetch_multiple_dates(dates=None):
    """
    Fetches and combines data for multiple dates.

    Args:
        dates (list, optional): List of dates in YYYYMMDD format.
                                If None, fetches today and tomorrow.

    Returns:
        pandas.DataFrame: Combined cleaned data for all dates
    """
    if dates is None:
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        dates = [today.strftime('%Y%m%d'), tomorrow.strftime('%Y%m%d')]

    all_data = []
    for date in dates:
        print(f"Fetching data for {date}...")
        raw_df = fetch_massey(date)
        if not raw_df.empty:
            cleaned_df = clean_massey(raw_df)
            all_data.append(cleaned_df)

    if not all_data:
        return pd.DataFrame()

    combined_df = pd.concat(all_data, ignore_index=True)
    duplicate_mask = (
        combined_df.groupby(["Game Date", "Home Team", "Away Team"])["Game Date"]
        .transform("count") > 1
    )
    combined_df = combined_df[~duplicate_mask]
    combined_df = combined_df.sort_values(["Game Date", "Home Team", "Away Team"])
    return combined_df


def transform_massey_format(df):
    """
    Transforms the cleaned Massey DataFrame from one row per game to two rows per game,
    matching the final KenPom output format but with the suffix "_massey".

    Each game row is split into two rows (one for each team) with these columns:
      - 'Home Team'
      - 'Away Team'
      - 'Team' (the team specific to the row)
      - 'Game Date'
      - 'spread_massey'
      - 'win_prob_massey'
      - 'projected_total_massey'
    """
    if df.empty:
        print("Empty DataFrame received in transform_massey_format")
        return df

    transformed_rows = []
    for _, row in df.iterrows():
        home_row = {
            'Home Team': row['Home Team'],
            'Away Team': row['Away Team'],
            'Team': row['Home Team'],
            'Game Date': row['Game Date'],
            'spread_massey': row['Home Team Spread'],
            'win_prob_massey': row['Home Team Win Probability'],
            'projected_total_massey': row['Projected Total']
        }
        away_row = {
            'Home Team': row['Home Team'],
            'Away Team': row['Away Team'],
            'Team': row['Away Team'],
            'Game Date': row['Game Date'],
            'spread_massey': row['Away Team Spread'],
            'win_prob_massey': row['Away Team Win Probability'],
            'projected_total_massey': row['Projected Total']
        }
        transformed_rows.extend([home_row, away_row])

    new_df = pd.DataFrame(transformed_rows)
    column_order = [
        'Home Team',
        'Away Team',
        'Team',
        'Game Date',
        'spread_massey',
        'win_prob_massey',
        'projected_total_massey'
    ]
    return new_df[column_order]


def map_team_names_massey(df):
    """
    Maps team names for Massey data using a crosswalk.

    Expects a CSV file named 'crosswalk.csv' containing at least two columns:
      - 'massey' (the Massey team name as pulled from the website)
      - 'API' (the standardized team name used in your system)

    The function applies the mapping to the columns:
      - 'Home Team', 'Away Team', and 'Team'
    """
    crosswalk = pd.read_csv('crosswalk.csv')
    if 'massey' not in crosswalk.columns:
        print("Error: 'massey' column not found in crosswalk.csv")
        return df
    name_map = crosswalk.set_index('massey')['API'].to_dict()

    unmapped_teams = {}
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])

    if unmapped_teams:
        print("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            print(f"- {team}: {count} occurrences")

    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)

    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    if len(mapped_df) < original_count:
        print(f"\nDropped {original_count - len(mapped_df)} rows due to mapping issues")
    return mapped_df


def get_massey_df(dates=None):
    """
    Fetches, cleans, transforms, and maps team names for Massey data,
    returning a DataFrame in the final output format (with columns suffixed by _massey).

    This output format is analogous to your final KenPom format but uses the Massey data:
      - Two rows per game (one for each team)
      - Columns: 'Home Team', 'Away Team', 'Team', 'Game Date', 
                 'spread_massey', 'win_prob_massey', 'projected_total_massey'
    """
    raw_df = fetch_multiple_dates(dates)
    if raw_df.empty:
        print("No Massey data fetched.")
        return raw_df
    cleaned_df = clean_massey(raw_df)
    transformed_df = transform_massey_format(cleaned_df)
    final_df = map_team_names_massey(transformed_df)
    return final_df
