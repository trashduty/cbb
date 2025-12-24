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
Rebuild graded_results.csv from historical_data backups.

IMPORTANT: historical_data/*.csv files are MORNING snapshots, not true first-seen
opening odds. This script uses them as an approximation for historical grading.

Going forward, game_snapshots.csv captures true opening AND closing data at tip-off.

This script:
1. Deletes existing graded_results.csv
2. For each file in historical_data/:
   - Load predictions with Opening* columns (approximation)
   - Fetch completed game scores from ESPN
   - Grade against opening lines
   - Add individual model grading
   - Append to new graded_results.csv
"""

import os
import sys
import pandas as pd
import requests
from datetime import datetime, timedelta
import pytz
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
import logging

# Add parent directory to path to import from grade_bets
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scrapers.grade_bets import (
    fetch_scores_espn,
    match_games,
    grade_matched_game,
    normalize_team_name,
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
console = Console()

# Project paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
historical_dir = os.path.join(project_root, 'historical_data')
graded_results_path = os.path.join(project_root, 'graded_results.csv')


def load_historical_predictions(date_str):
    """
    Load historical predictions for a specific date from backup file.

    Args:
        date_str (str): Date string in format 'YYYY-MM-DD'

    Returns:
        pd.DataFrame or None: Predictions with columns mapped appropriately
    """
    filename = f"{date_str}_output.csv"
    filepath = os.path.join(historical_dir, filename)

    if not os.path.exists(filepath):
        return None

    try:
        df = pd.read_csv(filepath)

        # Parse Home Team and Away Team from Game column
        if 'Home Team' not in df.columns or 'Away Team' not in df.columns:
            def parse_game(game_str):
                if pd.isna(game_str):
                    return None, None
                parts = game_str.split(' vs. ')
                if len(parts) == 2:
                    return parts[1], parts[0]  # home, away (format is "Away vs. Home")
                return None, None

            df[['Home Team', 'Away Team']] = df['Game'].apply(
                lambda x: pd.Series(parse_game(x))
            )

        # Mark data source
        df['data_source'] = 'historical_backup'

        return df
    except Exception as e:
        logger.warning(f"Error reading {filename}: {e}")
        return None


def get_historical_dates():
    """
    Get list of dates with historical data files.

    Returns:
        list: Sorted list of date strings
    """
    dates = []
    if not os.path.exists(historical_dir):
        return dates

    for filename in os.listdir(historical_dir):
        if filename.endswith('_output.csv'):
            date_str = filename.replace('_output.csv', '')
            try:
                # Validate date format
                datetime.strptime(date_str, '%Y-%m-%d')
                dates.append(date_str)
            except ValueError:
                continue

    return sorted(dates)


def main():
    """
    Main rebuild function.
    """
    console.print("\n[bold cyan]=== Rebuilding graded_results.csv ===[/bold cyan]\n")

    # Warning about data quality
    console.print("[yellow]⚠ WARNING: historical_data/*.csv are MORNING snapshots,[/yellow]")
    console.print("[yellow]  not true first-seen opening odds. Using as approximation.[/yellow]\n")

    # Get historical dates
    dates = get_historical_dates()
    if not dates:
        console.print("[red]No historical data files found in historical_data/[/red]")
        return

    console.print(f"[cyan]Found {len(dates)} historical data files[/cyan]")
    console.print(f"[cyan]Date range: {dates[0]} to {dates[-1]}[/cyan]\n")

    # Delete existing graded_results.csv
    if os.path.exists(graded_results_path):
        os.remove(graded_results_path)
        console.print("[green]✓[/green] Deleted existing graded_results.csv")

    all_graded_results = []
    dates_with_data = 0
    games_graded = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Processing dates...", total=len(dates))

        for date_str in dates:
            progress.update(task, description=f"Processing {date_str}...")

            # Load predictions for this date
            predictions_df = load_historical_predictions(date_str)
            if predictions_df is None or predictions_df.empty:
                progress.advance(task)
                continue

            # Fetch scores from ESPN for this date
            scores = fetch_scores_espn(date_str)
            if not scores:
                progress.advance(task)
                continue

            dates_with_data += 1

            # Match games
            matched, unmatched_scores, unmatched_predictions = match_games(scores, predictions_df)

            # Grade each matched game
            for matched_game in matched:
                try:
                    graded_result = grade_matched_game(matched_game)
                    if graded_result:
                        all_graded_results.append(graded_result)
                        games_graded += 1
                except Exception as e:
                    logger.debug(f"Error grading game: {e}")
                    continue

            progress.advance(task)

    # Save results
    if all_graded_results:
        df = pd.DataFrame(all_graded_results)
        df.to_csv(graded_results_path, index=False)

        console.print(f"\n[green]✓[/green] Saved {len(df)} rows to graded_results.csv")
        console.print(f"[cyan]  - Dates with data: {dates_with_data}[/cyan]")
        console.print(f"[cyan]  - Games graded: {games_graded // 2} (2 rows per game)[/cyan]")

        # Show summary stats
        console.print(f"\n[bold green]Grading Summary:[/bold green]")

        # Spread stats
        spread_bets = df[df['spread_covered'].notna()]
        if len(spread_bets) > 0:
            spread_wins = (spread_bets['spread_covered'] == 1).sum()
            spread_rate = spread_wins / len(spread_bets) * 100
            console.print(f"  Spread: {spread_wins}/{len(spread_bets)} covered ({spread_rate:.1f}%)")

        # Total stats
        over_bets = df[df['over_hit'].notna()]
        if len(over_bets) > 0:
            over_wins = (over_bets['over_hit'] == 1).sum()
            over_rate = over_wins / len(over_bets) * 100
            console.print(f"  Over: {over_wins}/{len(over_bets)} hit ({over_rate:.1f}%)")

        # Moneyline stats
        ml_bets = df[df['moneyline_won'].notna()]
        if len(ml_bets) > 0:
            ml_wins = (ml_bets['moneyline_won'] == 1).sum()
            ml_rate = ml_wins / len(ml_bets) * 100
            console.print(f"  Moneyline: {ml_wins}/{len(ml_bets)} won ({ml_rate:.1f}%)")

        # Individual model stats
        console.print(f"\n[bold green]Individual Model Performance (Spreads):[/bold green]")
        for model in ['kenpom', 'barttorvik', 'evanmiya', 'hasla']:
            col = f'spread_covered_{model}'
            if col in df.columns:
                model_bets = df[df[col].notna()]
                if len(model_bets) > 0:
                    model_wins = (model_bets[col] == 1).sum()
                    model_rate = model_wins / len(model_bets) * 100
                    console.print(f"  {model.capitalize()}: {model_wins}/{len(model_bets)} ({model_rate:.1f}%)")

    else:
        console.print("\n[yellow]No games were graded[/yellow]")

    console.print("\n[bold cyan]=== Rebuild Complete ===[/bold cyan]\n")


if __name__ == "__main__":
    main()
