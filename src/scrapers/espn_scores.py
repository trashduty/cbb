# /// script
# dependencies = [
#   "requests",
#   "python-dotenv",
#   "rich"
# ]
# ///
"""
Fetch completed game scores from ESPN API for college basketball.

ESPN has an unofficial API that provides game scores for completed games.
This is useful for grading historical predictions beyond OddsAPI's 3-day limit.
"""

import requests
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
import logging

console = Console()
logger = logging.getLogger(__name__)

def fetch_espn_scores(date_str):
    """
    Fetch completed game scores from ESPN for a specific date.

    Args:
        date_str (str): Date in format 'YYYY-MM-DD' or 'YYYYMMDD'

    Returns:
        list: List of game dictionaries with scores
    """
    # Format date for ESPN API (YYYYMMDD)
    if '-' in date_str:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    else:
        date_obj = datetime.strptime(date_str, '%Y%m%d')

    espn_date = date_obj.strftime('%Y%m%d')

    # ESPN scoreboard API endpoint
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

    params = {
        'dates': espn_date,
        'limit': 400  # Get all games for the day
    }

    try:
        console.print(f"[cyan]Fetching ESPN scores for {date_str}[/cyan]")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        games = []
        events = data.get('events', [])

        for event in events:
            # Only include completed games
            status = event.get('status', {})
            if status.get('type', {}).get('completed') != True:
                continue

            competitions = event.get('competitions', [])
            if not competitions:
                continue

            competition = competitions[0]
            competitors = competition.get('competitors', [])

            if len(competitors) != 2:
                continue

            # ESPN format: competitors[0] is usually home, competitors[1] is away
            # But we need to check the 'homeAway' field to be sure
            home_team = None
            away_team = None
            home_score = None
            away_score = None

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

            if home_team and away_team and home_score is not None and away_score is not None:
                game = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': int(home_score),
                    'away_score': int(away_score),
                    'completed': True,
                    'date': date_obj.strftime('%Y-%m-%d'),
                    'commence_time': event.get('date', ''),
                    'source': 'ESPN'
                }
                games.append(game)

        console.print(f"[green]✓[/green] Found {len(games)} completed games on {date_str}")
        return games

    except requests.exceptions.RequestException as e:
        console.print(f"[red]✗[/red] Error fetching ESPN scores: {e}")
        return []

def fetch_espn_scores_range(start_date, end_date):
    """
    Fetch ESPN scores for a range of dates.

    Args:
        start_date (str): Start date in format 'YYYY-MM-DD'
        end_date (str): End date in format 'YYYY-MM-DD'

    Returns:
        dict: Dictionary with date as key and list of games as value
    """
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')

    all_games = {}
    current = start

    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        games = fetch_espn_scores(date_str)

        if games:
            all_games[date_str] = games

        current += timedelta(days=1)

    return all_games

def display_espn_scores(games):
    """
    Display ESPN scores in a nice table format.

    Args:
        games (list): List of game dictionaries
    """
    if not games:
        console.print("[yellow]No games to display[/yellow]")
        return

    table = Table(title="ESPN Completed Games", show_header=True)
    table.add_column("Date", style="cyan")
    table.add_column("Matchup", style="green")
    table.add_column("Score", style="yellow")

    for game in games[:10]:  # Show first 10
        date_str = game['date']
        matchup = f"{game['away_team']} @ {game['home_team']}"
        score = f"{game['away_score']}-{game['home_score']}"
        table.add_row(date_str, matchup, score)

    console.print(table)

    if len(games) > 10:
        console.print(f"[dim]... and {len(games) - 10} more games[/dim]")

if __name__ == "__main__":
    # Test with a specific date
    import sys

    if len(sys.argv) > 1:
        date = sys.argv[1]
        games = fetch_espn_scores(date)
        display_espn_scores(games)
    else:
        # Default: fetch yesterday's scores
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        games = fetch_espn_scores(yesterday)
        display_espn_scores(games)
