# /// script
# dependencies = [
#   "pandas",
#   "requests",
#   "python-dotenv",
#   "rich",
#   "pytz"
# ]
# ///
"""
Grade historical bet predictions against actual game results from OddsAPI.

This script:
1. Fetches completed game scores from OddsAPI (last 3 days)
2. Loads historical predictions from historical_data/ folder
3. Matches games and grades spread, total, and moneyline bets
4. Outputs cumulative results to graded_results.csv
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from rich.console import Console
from rich.table import Table
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

# Load environment variables
load_dotenv()

# Project paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
historical_dir = os.path.join(project_root, 'historical_data')
graded_results_path = os.path.join(project_root, 'graded_results.csv')
unmatched_games_path = os.path.join(project_root, 'unmatched_games.csv')

def fetch_scores_espn(date_str):
    """
    Fetch completed game scores from ESPN API for a specific date.

    Args:
        date_str (str): Date in format 'YYYY-MM-DD'

    Returns:
        list: List of game dictionaries with scores (ESPN format)
    """
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    espn_date = date_obj.strftime('%Y%m%d')

    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
    params = {'dates': espn_date, 'limit': 400}

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        games = []
        for event in data.get('events', []):
            status = event.get('status', {})
            if status.get('type', {}).get('completed') != True:
                continue

            competitions = event.get('competitions', [])
            if not competitions:
                continue

            competitors = competitions[0].get('competitors', [])
            if len(competitors) != 2:
                continue

            home_team = away_team = home_score = away_score = None

            for competitor in competitors:
                team_name = competitor.get('team', {}).get('displayName', '')
                score = competitor.get('score')
                home_away = competitor.get('homeAway')

                if home_away == 'home':
                    home_team = team_name
                    home_score = score
                elif home_away == 'away':
                    away_team = team_name
                    away_score = score

            if all([home_team, away_team, home_score is not None, away_score is not None]):
                # Convert to OddsAPI-like format
                games.append({
                    'home_team': home_team,
                    'away_team': away_team,
                    'completed': True,
                    'commence_time': date_obj.isoformat() + 'Z',
                    'scores': [
                        {'name': home_team, 'score': str(home_score)},
                        {'name': away_team, 'score': str(away_score)}
                    ]
                })

        return games

    except Exception as e:
        logger.warning(f"[yellow]⚠[/yellow] Error fetching ESPN scores for {date_str}: {e}")
        return []

def fetch_scores(days_from=3, use_espn=False, specific_dates=None):
    """
    Fetch completed game scores from OddsAPI or ESPN.

    Args:
        days_from (int): Number of days back to fetch scores (max 3 for OddsAPI)
        use_espn (bool): Use ESPN API instead of OddsAPI
        specific_dates (list): List of specific dates to fetch (YYYY-MM-DD format) for ESPN

    Returns:
        list: List of game dictionaries with scores
    """
    if use_espn and specific_dates:
        logger.info(f"[cyan]Fetching scores from ESPN for {len(specific_dates)} dates[/cyan]")
        all_games = []

        for date_str in specific_dates:
            games = fetch_scores_espn(date_str)
            all_games.extend(games)
            logger.info(f"[green]✓[/green] Fetched {len(games)} games for {date_str}")

        logger.info(f"[green]✓[/green] Total: {len(all_games)} completed games from ESPN")

        # Display sample
        if all_games:
            table = Table(title="Sample Completed Games (ESPN)", show_header=True)
            table.add_column("Date", style="cyan")
            table.add_column("Matchup", style="green")
            table.add_column("Score", style="yellow")

            for game in all_games[:10]:
                date = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                date_str = date.strftime('%Y-%m-%d')
                matchup = f"{game['away_team']} @ {game['home_team']}"

                scores = game.get('scores', [])
                home_score = next((s['score'] for s in scores if s['name'] == game['home_team']), 'N/A')
                away_score = next((s['score'] for s in scores if s['name'] == game['away_team']), 'N/A')
                score_str = f"{away_score}-{home_score}"

                table.add_row(date_str, matchup, score_str)

            console.print(table)

        return all_games

    # Default: Use OddsAPI
    api_key = os.getenv("ODDS_API_KEY")
    if not api_key:
        logger.error("[red]✗[/red] ODDS_API_KEY not found in environment variables")
        raise ValueError("ODDS_API_KEY not found")

    sport = "basketball_ncaab"
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores/"

    params = {
        'apiKey': api_key,
        'daysFrom': days_from,
        'dateFormat': 'iso'
    }

    try:
        logger.info(f"[cyan]Fetching scores from OddsAPI (last {days_from} days)[/cyan]")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        # Filter for completed games only
        completed_games = [game for game in data if game.get('completed', False)]

        logger.info(f"[green]✓[/green] Fetched {len(completed_games)} completed games")

        # Display sample
        if completed_games:
            table = Table(title="Sample Completed Games", show_header=True)
            table.add_column("Date", style="cyan")
            table.add_column("Matchup", style="green")
            table.add_column("Score", style="yellow")

            for game in completed_games[:5]:
                date = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
                date_str = date.strftime('%Y-%m-%d')
                matchup = f"{game['away_team']} @ {game['home_team']}"

                scores = game.get('scores', [])
                home_score = next((s['score'] for s in scores if s['name'] == game['home_team']), 'N/A')
                away_score = next((s['score'] for s in scores if s['name'] == game['away_team']), 'N/A')
                score_str = f"{away_score}-{home_score}"

                table.add_row(date_str, matchup, score_str)

            console.print(table)

        return completed_games

    except requests.exceptions.RequestException as e:
        logger.error(f"[red]✗[/red] Error fetching scores: {e}")
        return []

def load_historical_predictions(date_str):
    """
    Load historical predictions for a specific date.

    Args:
        date_str (str): Date string in format 'YYYY-MM-DD'

    Returns:
        pd.DataFrame or None: Historical predictions or None if file not found
    """
    filename = f"{date_str}_output.csv"
    filepath = os.path.join(historical_dir, filename)

    if not os.path.exists(filepath):
        logger.warning(f"[yellow]⚠[/yellow] Historical file not found: {filename}")
        return None

    try:
        df = pd.read_csv(filepath)

        # Parse Home Team and Away Team from Game column if not present
        # Game format is "Away Team vs. Home Team"
        if 'Home Team' not in df.columns or 'Away Team' not in df.columns:
            def parse_game(game_str):
                if pd.isna(game_str):
                    return None, None
                parts = game_str.split(' vs. ')
                if len(parts) == 2:
                    return parts[1], parts[0]  # home, away
                return None, None

            df[['Home Team', 'Away Team']] = df['Game'].apply(
                lambda x: pd.Series(parse_game(x))
            )

        logger.info(f"[green]✓[/green] Loaded {len(df)} predictions from {filename}")
        return df
    except Exception as e:
        logger.error(f"[red]✗[/red] Error reading {filename}: {e}")
        return None

def normalize_team_name(name):
    """
    Normalize team names to handle variations between data sources.

    Args:
        name (str): Team name

    Returns:
        str: Normalized team name
    """
    if not name:
        return name

    # Common abbreviation expansions
    replacements = {
        ' St ': ' State ',
        ' St.': ' State',
        'St ': 'State ',
        'St.': 'State',
        'St ': 'State ',
        ' Int\'l': ' International',
        'Int\'l ': 'International ',
        'UNC ': 'North Carolina ',
        'UNLV': 'Nevada Las Vegas',
        'USC ': 'Southern California ',
        'UCLA': 'California Los Angeles',
        'TCU': 'Texas Christian',
        'SMU': 'Southern Methodist',
        'LSU': 'Louisiana State',
        'BYU': 'Brigham Young',
        'UCF': 'Central Florida',
        'VCU': 'Virginia Commonwealth',
        'UConn': 'Connecticut',
        'IUPUI': 'Indiana-Purdue Indianapolis',
        'SIU ': 'Southern Illinois ',
        'San José': 'San Jose',
        'San Jose St': 'San Jose State',
    }

    normalized = name
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)

    # Remove extra spaces and normalize case
    normalized = ' '.join(normalized.split())

    return normalized

def match_games(scores, predictions_df):
    """
    Match completed games with historical predictions.

    Args:
        scores (list): List of completed game dictionaries from OddsAPI
        predictions_df (pd.DataFrame): Historical predictions

    Returns:
        tuple: (matched_games list, unmatched_scores list, unmatched_predictions list)
    """
    matched = []
    unmatched_scores = []
    matched_prediction_indices = set()

    for score_game in scores:
        home_team = score_game['home_team']
        away_team = score_game['away_team']

        # Normalize team names for comparison
        home_norm = normalize_team_name(home_team)
        away_norm = normalize_team_name(away_team)

        # Create normalized columns for matching if not already present
        if 'Home Team Normalized' not in predictions_df.columns:
            predictions_df['Home Team Normalized'] = predictions_df['Home Team'].apply(normalize_team_name)
            predictions_df['Away Team Normalized'] = predictions_df['Away Team'].apply(normalize_team_name)

        # Try to find matching game in predictions
        # First try exact home/away match (with normalization)
        mask = (
            (predictions_df['Home Team Normalized'] == home_norm) &
            (predictions_df['Away Team Normalized'] == away_norm)
        )

        matches = predictions_df[mask]

        # If no match, try swapped home/away (ESPN might have different designation)
        if len(matches) == 0:
            mask_swapped = (
                (predictions_df['Home Team Normalized'] == away_norm) &
                (predictions_df['Away Team Normalized'] == home_norm)
            )
            matches = predictions_df[mask_swapped]

            # If we found a match with swapped teams, we need to swap the scores too
            if len(matches) > 0:
                # Swap home/away scores in the score_game data
                score_game = score_game.copy()
                score_game['home_team'], score_game['away_team'] = away_team, home_team
                scores_list = score_game.get('scores', [])
                if len(scores_list) == 2:
                    # Swap the scores to match the swapped teams
                    score_game['scores'] = [
                        {'name': score_game['away_team'], 'score': scores_list[0]['score'] if scores_list[0]['name'] == home_team else scores_list[1]['score']},
                        {'name': score_game['home_team'], 'score': scores_list[0]['score'] if scores_list[0]['name'] == away_team else scores_list[1]['score']}
                    ]

        if len(matches) > 0:
            # Found match - store all team rows for this game
            for idx, prediction_row in matches.iterrows():
                matched.append({
                    'score_data': score_game,
                    'prediction_data': prediction_row
                })
                matched_prediction_indices.add(idx)
        else:
            unmatched_scores.append(score_game)
            logger.warning(f"[yellow]⚠[/yellow] No prediction found for: {away_team} @ {home_team}")

    # Find predictions without scores
    unmatched_predictions = predictions_df[~predictions_df.index.isin(matched_prediction_indices)]

    logger.info(f"[cyan]Matched: {len(matched)} rows, Unmatched scores: {len(unmatched_scores)}, "
                f"Unmatched predictions: {len(unmatched_predictions)} rows[/cyan]")

    return matched, unmatched_scores, unmatched_predictions

def grade_spread_bet(prediction_row, home_score, away_score):
    """
    Grade a spread bet.

    Args:
        prediction_row (pd.Series): Row from predictions with spread data
        home_score (int): Actual home team score
        away_score (int): Actual away team score

    Returns:
        dict: Grading results
    """
    team = prediction_row['Team']
    home_team = prediction_row['Home Team']
    away_team = prediction_row['Away Team']
    opening_spread = prediction_row.get('Opening Spread')

    # Determine if this row is for home or away team
    is_home = (team == home_team)

    if pd.isna(opening_spread):
        return {
            'spread_covered': None,
            'spread_edge_realized': None
        }

    # Calculate actual margin from this team's perspective
    if is_home:
        actual_margin = home_score - away_score
    else:
        actual_margin = away_score - home_score

    # Check if spread covered: (actual_margin + spread) > 0
    # Example: Team has -5.5 spread and wins by 7: (7 + -5.5) = 1.5 > 0 = COVERED
    spread_covered = (actual_margin + opening_spread) > 0

    # Push if exactly 0 (very rare)
    if (actual_margin + opening_spread) == 0:
        spread_covered = None  # Push

    # Calculate edge realized
    spread_cover_prob = prediction_row.get('Spread Cover Probability')
    edge_for_covering = prediction_row.get('Edge For Covering Spread')

    if pd.notna(spread_cover_prob) and spread_covered is not None:
        # Edge realized = actual outcome (1 or 0) - predicted probability
        edge_realized = (1 if spread_covered else 0) - spread_cover_prob
    else:
        edge_realized = None

    return {
        'spread_covered': 1 if spread_covered else (0 if spread_covered is False else None),
        'spread_edge_realized': edge_realized
    }

def grade_total_bet(prediction_row, home_score, away_score):
    """
    Grade over/under total bets.

    Args:
        prediction_row (pd.Series): Row from predictions with total data
        home_score (int): Actual home team score
        away_score (int): Actual away team score

    Returns:
        dict: Grading results
    """
    market_total = prediction_row.get('market_total')

    if pd.isna(market_total):
        return {
            'actual_total': home_score + away_score,
            'over_hit': None,
            'under_hit': None,
            'over_edge_realized': None,
            'under_edge_realized': None
        }

    actual_total = home_score + away_score

    # Determine over/under outcome
    if actual_total > market_total:
        over_hit = 1
        under_hit = 0
    elif actual_total < market_total:
        over_hit = 0
        under_hit = 1
    else:
        # Push
        over_hit = None
        under_hit = None

    # Calculate edge realized
    over_prob = prediction_row.get('Over Cover Probability')
    under_prob = prediction_row.get('Under Cover Probability')

    over_edge_realized = None
    under_edge_realized = None

    if pd.notna(over_prob) and over_hit is not None:
        over_edge_realized = over_hit - over_prob

    if pd.notna(under_prob) and under_hit is not None:
        under_edge_realized = under_hit - under_prob

    return {
        'actual_total': actual_total,
        'over_hit': over_hit,
        'under_hit': under_hit,
        'over_edge_realized': over_edge_realized,
        'under_edge_realized': under_edge_realized
    }

def grade_moneyline_bet(prediction_row, home_score, away_score):
    """
    Grade a moneyline bet.

    Args:
        prediction_row (pd.Series): Row from predictions with moneyline data
        home_score (int): Actual home team score
        away_score (int): Actual away team score

    Returns:
        dict: Grading results
    """
    team = prediction_row['Team']
    home_team = prediction_row['Home Team']
    is_home = (team == home_team)

    # Determine if team won
    if is_home:
        team_won = home_score > away_score
    else:
        team_won = away_score > home_score

    # Handle ties (very rare in basketball)
    if home_score == away_score:
        team_won = None  # Push

    # Calculate edge realized
    ml_win_prob = prediction_row.get('Moneyline Win Probability')

    if pd.notna(ml_win_prob) and team_won is not None:
        edge_realized = (1 if team_won else 0) - ml_win_prob
    else:
        edge_realized = None

    return {
        'moneyline_won': 1 if team_won else (0 if team_won is False else None),
        'moneyline_edge_realized': edge_realized
    }

def grade_matched_game(matched_game):
    """
    Grade all bets for a matched game.

    Args:
        matched_game (dict): Dictionary with 'score_data' and 'prediction_data'

    Returns:
        dict: Complete grading results
    """
    score_data = matched_game['score_data']
    prediction_row = matched_game['prediction_data']

    # Extract scores
    scores = score_data.get('scores', [])
    home_team = score_data['home_team']
    away_team = score_data['away_team']

    home_score = next((s['score'] for s in scores if s['name'] == home_team), None)
    away_score = next((s['score'] for s in scores if s['name'] == away_team), None)

    if home_score is None or away_score is None:
        logger.warning(f"[yellow]⚠[/yellow] Missing scores for {away_team} @ {home_team}")
        return None

    # Convert to int
    home_score = int(home_score)
    away_score = int(away_score)

    # Get game date
    game_date = datetime.fromisoformat(score_data['commence_time'].replace('Z', '+00:00'))
    game_date_str = game_date.strftime('%Y-%m-%d')

    # Grade each bet type
    spread_results = grade_spread_bet(prediction_row, home_score, away_score)
    total_results = grade_total_bet(prediction_row, home_score, away_score)
    moneyline_results = grade_moneyline_bet(prediction_row, home_score, away_score)

    # Compile results
    graded = {
        'date': game_date_str,
        'game': prediction_row['Game'],
        'team': prediction_row['Team'],
        'home_team': home_team,
        'away_team': away_team,
        'home_score': home_score,
        'away_score': away_score,
        'game_completed': True,

        # Spread data
        'opening_spread': prediction_row.get('Opening Spread'),
        'predicted_outcome': prediction_row.get('Predicted Outcome'),
        'spread_cover_probability': prediction_row.get('Spread Cover Probability'),
        'spread_covered': spread_results['spread_covered'],
        'spread_edge': prediction_row.get('Edge For Covering Spread'),
        'spread_edge_realized': spread_results['spread_edge_realized'],

        # Total data
        'market_total': prediction_row.get('market_total'),
        'actual_total': total_results['actual_total'],
        'over_cover_probability': prediction_row.get('Over Cover Probability'),
        'under_cover_probability': prediction_row.get('Under Cover Probability'),
        'over_hit': total_results['over_hit'],
        'under_hit': total_results['under_hit'],
        'over_edge': prediction_row.get('Over Total Edge'),
        'under_edge': prediction_row.get('Under Total Edge'),
        'over_edge_realized': total_results['over_edge_realized'],
        'under_edge_realized': total_results['under_edge_realized'],

        # Moneyline data
        'opening_moneyline': prediction_row.get('Opening Moneyline'),
        'moneyline_win_probability': prediction_row.get('Moneyline Win Probability'),
        'moneyline_won': moneyline_results['moneyline_won'],
        'moneyline_edge': prediction_row.get('Moneyline Edge'),
        'moneyline_edge_realized': moneyline_results['moneyline_edge_realized'],

        # Consensus flags
        'spread_consensus_flag': prediction_row.get('spread_consensus_flag'),
        'moneyline_consensus_flag': prediction_row.get('moneyline_consensus_flag'),
        'over_consensus_flag': prediction_row.get('over_consensus_flag'),
        'under_consensus_flag': prediction_row.get('under_consensus_flag')
    }

    return graded

def load_existing_graded_results():
    """
    Load existing graded results to avoid duplicate grading.

    Returns:
        pd.DataFrame: Existing graded results or empty DataFrame
    """
    if os.path.exists(graded_results_path):
        try:
            df = pd.read_csv(graded_results_path)
            logger.info(f"[green]✓[/green] Loaded {len(df)} existing graded results")
            return df
        except Exception as e:
            logger.warning(f"[yellow]⚠[/yellow] Error loading existing results: {e}")
            return pd.DataFrame()
    else:
        logger.info("[cyan]No existing graded results found, starting fresh[/cyan]")
        return pd.DataFrame()

def check_already_graded(existing_df, date, game, team):
    """
    Check if a specific game/team has already been graded.

    Args:
        existing_df (pd.DataFrame): Existing graded results
        date (str): Game date
        game (str): Game name
        team (str): Team name

    Returns:
        bool: True if already graded
    """
    if existing_df.empty:
        return False

    mask = (
        (existing_df['date'] == date) &
        (existing_df['game'] == game) &
        (existing_df['team'] == team)
    )

    return len(existing_df[mask]) > 0

def append_to_results(new_results):
    """
    Append new graded results to cumulative file.

    Args:
        new_results (list): List of graded result dictionaries
    """
    if not new_results:
        logger.info("[cyan]No new results to append[/cyan]")
        return

    new_df = pd.DataFrame(new_results)

    # Load existing results
    if os.path.exists(graded_results_path):
        existing_df = pd.read_csv(graded_results_path)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined_df = new_df

    # Save
    combined_df.to_csv(graded_results_path, index=False)
    logger.info(f"[green]✓[/green] Saved {len(new_results)} new results to graded_results.csv")
    logger.info(f"[cyan]Total graded results: {len(combined_df)}[/cyan]")

def log_unmatched_games(unmatched_scores, unmatched_predictions, date_str):
    """
    Log unmatched games for review.

    Args:
        unmatched_scores (list): Games with scores but no predictions
        unmatched_predictions (pd.DataFrame): Predictions with no scores
        date_str (str): Date being processed
    """
    unmatched_data = []

    # Log scores without predictions
    for game in unmatched_scores:
        unmatched_data.append({
            'date': date_str,
            'type': 'score_no_prediction',
            'home_team': game['home_team'],
            'away_team': game['away_team'],
            'reason': 'Game completed but not in predictions'
        })

    # Log predictions without scores (unique games only)
    if not unmatched_predictions.empty:
        unique_games = unmatched_predictions.drop_duplicates(subset=['Game'])
        for _, row in unique_games.iterrows():
            unmatched_data.append({
                'date': date_str,
                'type': 'prediction_no_score',
                'home_team': row.get('Home Team', 'N/A'),
                'away_team': row.get('Away Team', 'N/A'),
                'reason': 'Prediction exists but game not completed (postponed?)'
            })

    if unmatched_data:
        # Append to unmatched log
        unmatched_df = pd.DataFrame(unmatched_data)

        if os.path.exists(unmatched_games_path):
            existing_unmatched = pd.read_csv(unmatched_games_path)
            combined_unmatched = pd.concat([existing_unmatched, unmatched_df], ignore_index=True)
        else:
            combined_unmatched = unmatched_df

        combined_unmatched.to_csv(unmatched_games_path, index=False)
        logger.info(f"[yellow]⚠[/yellow] Logged {len(unmatched_data)} unmatched games to unmatched_games.csv")

def main(use_espn=False, espn_dates=None):
    """
    Main execution function.

    Args:
        use_espn (bool): Use ESPN API instead of OddsAPI
        espn_dates (list): Specific dates to fetch from ESPN (YYYY-MM-DD format)
    """
    logger.info("=== Starting Bet Grading Process ===")

    # Fetch completed game scores
    if use_espn and espn_dates:
        scores = fetch_scores(use_espn=True, specific_dates=espn_dates)
    else:
        scores = fetch_scores(days_from=3)

    if not scores:
        logger.warning("[yellow]⚠[/yellow] No completed games found")
        return

    # Organize scores by date
    scores_by_date = {}
    for game in scores:
        game_date = datetime.fromisoformat(game['commence_time'].replace('Z', '+00:00'))
        date_str = game_date.strftime('%Y-%m-%d')

        if date_str not in scores_by_date:
            scores_by_date[date_str] = []
        scores_by_date[date_str].append(game)

    logger.info(f"[cyan]Processing {len(scores_by_date)} unique dates[/cyan]")

    # Load existing graded results to avoid duplicates
    existing_graded = load_existing_graded_results()

    all_new_results = []

    # Process each date
    for date_str in sorted(scores_by_date.keys()):
        logger.info(f"\n[bold cyan]Processing date: {date_str}[/bold cyan]")

        # Load historical predictions for this date
        predictions_df = load_historical_predictions(date_str)

        if predictions_df is None:
            logger.warning(f"[yellow]⚠[/yellow] Skipping {date_str} - no predictions file found")
            continue

        # Match games
        date_scores = scores_by_date[date_str]
        matched, unmatched_scores, unmatched_predictions = match_games(date_scores, predictions_df)

        # Grade matched games
        for matched_game in matched:
            prediction_row = matched_game['prediction_data']

            # Check if already graded
            if check_already_graded(
                existing_graded,
                date_str,
                prediction_row['Game'],
                prediction_row['Team']
            ):
                logger.debug(f"[dim]Skipping already graded: {prediction_row['Game']} - {prediction_row['Team']}[/dim]")
                continue

            # Grade the game
            graded_result = grade_matched_game(matched_game)

            if graded_result:
                all_new_results.append(graded_result)

        # Log unmatched games
        log_unmatched_games(unmatched_scores, unmatched_predictions, date_str)

    # Append all new results
    if all_new_results:
        append_to_results(all_new_results)

        # Display summary
        logger.info("\n[bold green]Grading Summary:[/bold green]")

        new_df = pd.DataFrame(all_new_results)

        # Spread stats
        spread_bets = new_df[new_df['spread_covered'].notna()]
        if len(spread_bets) > 0:
            spread_wins = (spread_bets['spread_covered'] == 1).sum()
            spread_rate = spread_wins / len(spread_bets) * 100
            logger.info(f"  Spread: {spread_wins}/{len(spread_bets)} covered ({spread_rate:.1f}%)")

        # Total stats
        over_bets = new_df[new_df['over_hit'].notna()]
        if len(over_bets) > 0:
            over_wins = (over_bets['over_hit'] == 1).sum()
            over_rate = over_wins / len(over_bets) * 100
            logger.info(f"  Over: {over_wins}/{len(over_bets)} hit ({over_rate:.1f}%)")

        under_bets = new_df[new_df['under_hit'].notna()]
        if len(under_bets) > 0:
            under_wins = (under_bets['under_hit'] == 1).sum()
            under_rate = under_wins / len(under_bets) * 100
            logger.info(f"  Under: {under_wins}/{len(under_bets)} hit ({under_rate:.1f}%)")

        # Moneyline stats
        ml_bets = new_df[new_df['moneyline_won'].notna()]
        if len(ml_bets) > 0:
            ml_wins = (ml_bets['moneyline_won'] == 1).sum()
            ml_rate = ml_wins / len(ml_bets) * 100
            logger.info(f"  Moneyline: {ml_wins}/{len(ml_bets)} won ({ml_rate:.1f}%)")
    else:
        logger.info("[cyan]No new games to grade (all already processed)[/cyan]")

    logger.info("\n=== Bet Grading Complete ===")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Grade historical bet predictions')
    parser.add_argument('--espn', action='store_true', help='Use ESPN API instead of OddsAPI')
    parser.add_argument('--dates', nargs='+', help='Specific dates to fetch (YYYY-MM-DD format)')
    args = parser.parse_args()

    try:
        main(use_espn=args.espn, espn_dates=args.dates)
    except Exception as e:
        logger.error(f"[red]✗[/red] Error in grading script: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
