# /// script
# dependencies = [
#   "pandas",
#   "requests",
#   "beautifulsoup4",
#   "numpy",
#   "rich"
# ]
# ///

import pandas as pd
import requests
from bs4 import BeautifulSoup
import numpy as np
from datetime import datetime, timedelta, timezone
import re
from rich.console import Console
from rich.table import Table
import os
import sys

console = Console()

# Determine the project root directory to save files correctly
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
data_dir = os.path.join(project_root, 'data')

# Ensure data directory exists
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    print(f"Created data directory: {data_dir}")

def fetch_barttorvik(date=None):
    """
    Fetch Barttorvik data for a specific date
    
    Args:
        date (str): Date in format YYYYMMDD
        
    Returns:
        tuple: (DataFrame of games, next_date_url)
    """
    headers = {'User-Agent': 'Mozilla/5.0'}
    base_url = "https://www.barttorvik.com/schedule.php"
    
    # Build URL with date parameter if provided
    if date:
        url = f"{base_url}?date={date}&conlimit="
        print(f"Fetching data for date: {date}")
    else:
        url = base_url
        print("Fetching data for current date")

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print("Successfully retrieved webpage")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        games = []
        
        # Extract next day link
        next_day_link = None
        nav_links = soup.find_all('a', href=lambda x: x and 'schedule.php?date=' in x)
        for link in nav_links:
            if '➡️' in link.text or 'next day' in link.text.lower():
                next_day_link = 'https://www.barttorvik.com' + link['href'] if not link['href'].startswith('http') else link['href']
                break
        
        # Extract date from next_day_link if found
        next_date = None
        if next_day_link:
            match = re.search(r'date=(\d{8})', next_day_link)
            if match:
                next_date = match.group(1)
                print(f"Found next date: {next_date}")

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

        print(f"Successfully parsed {len(games)} games")
        return pd.DataFrame(games), next_date

    except requests.RequestException as e:
        print(f"Failed to fetch data: {str(e)}")
        raise

def fetch_multiple_days(start_date=None, num_days=5):
    """
    Fetch Barttorvik data for multiple consecutive days by following navigation links
    
    Args:
        start_date (str): Starting date in YYYYMMDD format, or None for current date
        num_days (int): Number of days to fetch (including start date)
        
    Returns:
        dict: Dictionary mapping dates to DataFrames of games
    """
    all_games = {}
    current_date = start_date
    days_fetched = 0
    
    while days_fetched < num_days:
        # Fetch data for current date
        df, next_date = fetch_barttorvik(current_date)
        
        if not df.empty:
            all_games[current_date if current_date else datetime.now().strftime('%Y%m%d')] = df
        
        days_fetched += 1
        
        # If we've reached the desired number of days or there's no next date, break
        if days_fetched >= num_days or not next_date:
            break
            
        # Move to next date
        current_date = next_date
        print(f"Moving to next date: {current_date}")
    
    print(f"Fetched data for {days_fetched} days")
    return all_games

def get_barttorvik_df(days_ahead=10):
    """
    Main function to get processed Barttorvik data for multiple days
    
    Args:
        days_ahead (int): Number of days to fetch (including today)
    """
    # Get today's date in Eastern time (for display purposes)
    today = datetime.now(timezone.utc)
    eastern = timezone(timedelta(hours=-5))  # EST is UTC-5
    today_eastern = today.astimezone(eastern)
    
    # Fetch games for multiple days by following navigation links
    print(f"Fetching games for up to {days_ahead} days starting from today")
    games_by_date = fetch_multiple_days(today_eastern.strftime('%Y%m%d'), days_ahead)
    
    # Transform each day's data
    transformed_dfs = []
    summary_table = Table(
        title=f"Barttorvik Request Summary",
        show_header=True,
        header_style="bold magenta",
        show_lines=False,
        title_style="bold cyan"
    )
    
    summary_table.add_column("Date", style="cyan")
    summary_table.add_column("Games Found", style="green")
    summary_table.add_column("Unmapped Teams", style="yellow")
    summary_table.add_column("Count", style="red")
    
    # Process each date's data
    total_games = 0
    for date, df in games_by_date.items():
        # Transform the data
        transformed = transform_barttorvik_data(df)
        transformed_dfs.append(transformed)
        
        # Add date to summary
        display_date = datetime.strptime(date, '%Y%m%d').strftime('%Y-%m-%d')
        date_games = len(df) if not df.empty else 0
        total_games += date_games
        print(f"Fetched {date_games} games for {display_date}")
    
    # Combine all transformed data
    if transformed_dfs:
        combined_df = pd.concat(transformed_dfs, ignore_index=True)
    else:
        print("No games found for any of the requested dates")
        combined_df = pd.DataFrame(columns=[
            'Home Team', 'Away Team', 'Team', 'Game Date', 
            'spread_barttorvik', 'win_prob_barttorvik', 'projected_total_barttorvik'
        ])
    
    # Map team names using crosswalk file from the data directory
    crosswalk_path = os.path.join(data_dir, 'crosswalk.csv')
    if os.path.exists(crosswalk_path):
        crosswalk = pd.read_csv(crosswalk_path)
        name_map = crosswalk.set_index('barttorvik')['API'].to_dict()
        
        # Create mapping report and get mapped dataframe
        mapped_df = map_team_names(combined_df, name_map)
        final_games = len(mapped_df) // 2  # Divide by 2 since we have 2 rows per game
        
        # Create summary for each date
        for date, df in games_by_date.items():
            date_df = combined_df[combined_df['Game Date'] == date]
            date_games = len(df) if not df.empty else 0
            
            # Find unmapped teams for this date
            unmapped = []
            for team in date_df['Team'].unique() if not date_df.empty else []:
                if team not in name_map:
                    unmapped.append(team)
            
            # Format unmapped teams string
            unmapped_count = len(unmapped)
            
            # Add row to summary table
            display_date = datetime.strptime(date, '%Y%m%d').strftime('%Y-%m-%d')
            summary_table.add_row(
                display_date,
                str(date_games),
                unmapped[0] if unmapped else "None",
                str(unmapped_count)
            )
            
            # Add additional rows for remaining unmapped teams
            for team in unmapped[1:]:
                summary_table.add_row("", "", team, "")
        
        # Add total row
        if len(games_by_date) > 1:
            summary_table.add_row("", "", "", "", style="dim")
            total_unmapped = len(set(team for team in combined_df['Team'].unique() if team not in name_map)) if not combined_df.empty else 0
            summary_table.add_row(
                "Total",
                str(total_games),
                f"{final_games} games after mapping",
                f"{total_unmapped} teams unmapped",
                style="bold"
            )
    else:
        print(f"Warning: Crosswalk file not found at {crosswalk_path}")
        print("Using unmapped data")
        mapped_df = combined_df
        final_games = len(mapped_df) // 2

    console.print(summary_table)

    # Create detailed games table
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
    games_table.add_column("Win Prob", style="cyan", width=10)
    games_table.add_column("Total", style="magenta", width=10)
    
    # Process each date's games
    current_date = None
    for _, row in mapped_df.iterrows():
        date = row['Game Date']
        if row['Team'] != row['Home Team']:
            continue  # Skip away team rows
            
        # Add separator row if date changes
        if current_date != date:
            formatted_date = datetime.strptime(str(date), '%Y%m%d').strftime('%m-%d')
            if current_date is not None:
                games_table.add_row("", "", "", "", "")
            games_table.add_row(formatted_date, "=" * 63, "", "", "", style="dim")  # Adjusted separator length
            current_date = date
        
        # Format the data
        spread = f"{row['spread_barttorvik']:+.1f}"
        win_prob = f"{row['win_prob_barttorvik']*100:.0f}%"
        total = f"{row['projected_total_barttorvik']:.1f}" if pd.notnull(row['projected_total_barttorvik']) else "N/A"
        
        # Create matchup string without truncation
        matchup = f"{row['Away Team']} @ {row['Home Team']}"
        
        # Add game row
        games_table.add_row(
            "",
            matchup,
            spread,
            win_prob,
            total
        )
    
    console.print(games_table)
    print(f"Successfully processed {final_games} games from Barttorvik")

    return mapped_df.reset_index(drop=True)

def transform_barttorvik_data(df):
    """Transform to two-row-per-game format with team-specific stats"""
    # Check if DataFrame is empty and return empty DataFrame with appropriate columns
    if df.empty:
        print("Empty DataFrame received, returning empty result with expected columns")
        return pd.DataFrame(columns=[
            'Home Team', 'Away Team', 'Team', 'Game Date', 
            'spread_barttorvik', 'win_prob_barttorvik', 'projected_total_barttorvik'
        ])
    
    pattern = r"^\s*(?P<TeamName>.+?)(?:\s+(?P<Spread>-?\d+\.?\d*))?(?:,\s*(?P<ProjectedScore>\d+-\d+))?\s*\((?P<WinProb>\d+)%\)\s*$"
    extracted = df['T-Rank Line'].str.extract(pattern)
    
    print("Extracting projected scores and win probabilities")
    
    try:
        extracted[['ProjectedHome', 'ProjectedAway']] = (
            extracted['ProjectedScore']
            .str.split('-', expand=True)
            .astype(float)
        )
        extracted['ProjectedTotal'] = extracted['ProjectedHome'] + extracted['ProjectedAway']
        print("Successfully processed projected scores")
    except (TypeError, ValueError):
        print("Could not process projected scores, setting to NaN")
        extracted['ProjectedTotal'] = np.nan

    base_df = df[['Home Team', 'Away Team', 'Game Date']].copy()
    home_rows = []
    away_rows = []
    failed_rows = []

    print("Processing individual game records")
    
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

            # Try both team orderings
            # First try original ordering
            is_home_favored = team_name == row['Home Team']
            is_away_favored = team_name == row['Away Team']

            if not (is_home_favored or is_away_favored):
                # Try swapped ordering
                is_home_favored = team_name == row['Away Team']
                is_away_favored = team_name == row['Home Team']
                if is_home_favored or is_away_favored:
                    # Swap teams and adjust spread/probability
                    row['Home Team'], row['Away Team'] = row['Away Team'], row['Home Team']
                    spread = -spread
                    win_prob = 100 - float(win_prob)
                else:
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

def map_team_names(df, name_map):
    """Map team names using crosswalk"""
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

if __name__ == "__main__":
    # Run the script to get data for the next 5 days
    df = get_barttorvik_df(days_ahead=10)
    
    # Save the output to a single CSV file
    output_file = os.path.join(data_dir, 'bt_mapped.csv')
    df.to_csv(output_file, index=False)
    print(f"Saved Barttorvik data to: {output_file}")
    
    print(f"Final dataframe shape: {df.shape}")