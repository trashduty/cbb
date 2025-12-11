# /// script
# dependencies = [
#   "pandas",
#   "requests"
# ]
# ///
"""
Check for betting edges in CBB_Output.csv and send Discord notifications.

This script monitors CBB_Output.csv for games with positive betting edges and
sends Discord alerts when thresholds are met, with deduplication to avoid
repeated notifications for the same games. 
"""

import pandas as pd
import json
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

# Define paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
csv_file = os.path.join(project_root, 'CBB_Output.csv')
notified_file = os.path.join(project_root, 'notified_games.json')

# Edge thresholds
SPREAD_THRESHOLD = 0.04  # 4%
MONEYLINE_THRESHOLD = 0.04  # 4%
TOTAL_THRESHOLD = 0.01  # 1%

# Time threshold - only alert on games more than 6 hours away
HOURS_BEFORE_GAME = 6

# Discord webhook URL from environment
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

def load_notified_games():
    """Load the set of previously notified games."""
    if not os.path.exists(notified_file):
        return {}
    
    try:
        with open(notified_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load notified games:  {e}")
        return {}

def save_notified_games(notified_games):
    """Save the set of notified games."""
    try:
        with open(notified_file, 'w') as f:
            json.dump(notified_games, f, indent=2)
        print(f"Updated {notified_file}")
    except Exception as e:
        print(f"Error saving notified games: {e}")

def create_game_id(row, edge_type):
    """Create a unique identifier for a game + team + edge type combination."""
    return f"{row['Game']}|{row['Team']}|{edge_type}"

def create_total_game_id(row, edge_type):
    """Create a unique identifier for totals (game-level, not team-specific)."""
    return f"{row['Game']}|{edge_type}"

def parse_game_time(game_time_str):
    """Parse game time string to datetime object."""
    try:
        # Format: "Dec 10 07:00PM ET"
        # Parse without year, then add current year
        dt = datetime.strptime(game_time_str. replace(" ET", ""), "%b %d %I:%M%p")
        current_year = datetime.now().year
        dt = dt.replace(year=current_year)
        
        # Convert to UTC (ET is UTC-5, but accounting for DST would require more logic)
        # For simplicity, assuming EST (UTC-5)
        dt_utc = dt + timedelta(hours=5)
        
        return dt_utc
    except Exception as e:
        print(f"Warning: Could not parse game time '{game_time_str}': {e}")
        return None

def is_game_far_enough(game_time_str):
    """Check if game is more than 6 hours away."""
    game_time = parse_game_time(game_time_str)
    if game_time is None: 
        return False
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    time_until_game = game_time - now
    
    hours_until_game = time_until_game.total_seconds() / 3600
    
    if hours_until_game < HOURS_BEFORE_GAME:
        print(f"  ⏰ Skipping - game is only {hours_until_game:.1f} hours away (threshold: {HOURS_BEFORE_GAME})")
        return False
    
    return True

def count_non_null_spread_sources(row):
    """Count how many spread projection sources have values."""
    spread_columns = ['spread_barttorvik', 'spread_kenpom', 'spread_evanmiya', 'spread_hasla']
    count = sum(1 for col in spread_columns if pd.notna(row. get(col)))
    return count

def count_non_null_total_sources(row):
    """Count how many total projection sources have values."""
    total_columns = ['projected_total_barttorvik', 'projected_total_kenpom', 
                     'projected_total_evanmiya', 'projected_total_hasla']
    count = sum(1 for col in total_columns if pd.notna(row.get(col)))
    return count

def format_percentage(value):
    """Format a decimal value as a percentage."""
    if pd.isna(value):
        return "N/A"
    return f"{value * 100:.2f}%"

def format_decimal(value, decimals=2):
    """Format a decimal value."""
    if pd.isna(value):
        return "N/A"
    return f"{value:.{decimals}f}"

def send_discord_notification(embed_data):
    """Send a notification to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL: 
        print("Warning:  DISCORD_WEBHOOK_URL not set, skipping notification")
        return False
    
    try:
        payload = {
            "embeds":  [embed_data]
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print(f"✓ Sent Discord notification: {embed_data['title']}")
        return True
    except Exception as e:
        print(f"Error sending Discord notification: {e}")
        return False

def create_spread_embed(row):
    """Create Discord embed for spread edge alert."""
    edge_value = row['Edge For Covering Spread']
    
    embed = {
        "title": f"🎯 Spread Edge Alert: {row['Team']}",
        "description": f"**{row['Game']}**\n{row['Game Time']}",
        "color": 0x00FF00,  # Green
        "fields": [
            {
                "name": "Edge For Covering Spread",
                "value": format_percentage(edge_value),
                "inline": True
            },
            {
                "name":  "Predicted Outcome",
                "value": format_decimal(row['Predicted Outcome'], 1),
                "inline": True
            },
            {
                "name": "Spread Cover Probability",
                "value": format_percentage(row['Spread Cover Probability']),
                "inline":  True
            },
            {
                "name": "Opening Spread",
                "value":  format_decimal(row['Opening Spread'], 1),
                "inline": True
            },
            {
                "name": "Current Spread",
                "value": format_decimal(row['market_spread'], 1),
                "inline": True
            }
        ],
        "timestamp":  datetime.now(timezone.utc).isoformat()
    }
    
    return embed

def create_moneyline_embed(row):
    """Create Discord embed for moneyline edge alert."""
    edge_value = row['Moneyline Edge']
    
    embed = {
        "title": f"💰 Moneyline Edge Alert: {row['Team']}",
        "description": f"**{row['Game']}**\n{row['Game Time']}",
        "color": 0x00FF00,  # Green
        "fields": [
            {
                "name": "Moneyline Edge",
                "value": format_percentage(edge_value),
                "inline": True
            },
            {
                "name": "Moneyline Win Probability",
                "value":  format_percentage(row['Moneyline Win Probability']),
                "inline": True
            },
            {
                "name":  "Opening Moneyline",
                "value": format_decimal(row['Opening Moneyline'], 0),
                "inline": True
            }
        ],
        "timestamp": datetime.now(timezone. utc).isoformat()
    }
    
    return embed

def create_over_embed(row):
    """Create Discord embed for over total edge alert."""
    edge_value = row['Over Total Edge']
    
    embed = {
        "title": f"📈 Over Total Edge Alert",
        "description": f"**{row['Game']}**\n{row['Game Time']}",
        "color": 0x0099FF,  # Blue
        "fields": [
            {
                "name": "Over Total Edge",
                "value": format_percentage(edge_value),
                "inline": True
            },
            {
                "name": "Over Cover Probability",
                "value":  format_percentage(row['Over Cover Probability']),
                "inline": True
            },
            {
                "name": "Current Total",
                "value": format_decimal(row['market_total'], 1),
                "inline": True
            },
            {
                "name": "Opening Total",
                "value": format_decimal(row['Opening Total'], 1),
                "inline": True
            },
            {
                "name":  "Model Total",
                "value": format_decimal(row['model_total'], 2),
                "inline": True
            }
        ],
        "timestamp": datetime.now(timezone. utc).isoformat()
    }
    
    return embed

def create_under_embed(row):
    """Create Discord embed for under total edge alert."""
    edge_value = row['Under Total Edge']
    
    embed = {
        "title": f"📉 Under Total Edge Alert",
        "description": f"**{row['Game']}**\n{row['Game Time']}",
        "color": 0xFF9900,  # Orange
        "fields": [
            {
                "name": "Under Total Edge",
                "value": format_percentage(edge_value),
                "inline": True
            },
            {
                "name": "Under Cover Probability",
                "value": format_percentage(row['Under Cover Probability']),
                "inline": True
            },
            {
                "name": "Current Total",
                "value": format_decimal(row['market_total'], 1),
                "inline": True
            },
            {
                "name": "Opening Total",
                "value": format_decimal(row['Opening Total'], 1),
                "inline": True
            },
            {
                "name": "Model Total",
                "value": format_decimal(row['model_total'], 2),
                "inline":  True
            }
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return embed

def check_edges():
    """Main function to check for edges and send notifications."""
    print(f"Checking for betting edges in {csv_file}")
    
    # Check if CSV file exists
    if not os.path.exists(csv_file):
        print(f"ERROR: {csv_file} not found!")
        sys.exit(1)
    
    # Load CSV
    df = pd.read_csv(csv_file)
    print(f"Loaded {len(df)} rows from CSV")
    
    # Load previously notified games
    notified_games = load_notified_games()
    print(f"Previously notified:  {len(notified_games)} game opportunities")
    
    notifications_sent = 0
    new_notified = {}
    
    # Track which games have already sent total alerts to avoid duplicates
    total_alerts_sent = set()
    
    # Check each row for qualifying edges
    for idx, row in df.iterrows():
        # Check if game is far enough away
        if not is_game_far_enough(row['Game Time']):
            continue
        
        # Check Spread Edge
        if pd.notna(row. get('Edge For Covering Spread')) and row['Edge For Covering Spread'] >= SPREAD_THRESHOLD:
            # Check if at least 4 out of 4 spread sources have values
            spread_source_count = count_non_null_spread_sources(row)
            if spread_source_count >= 4:
                game_id = create_game_id(row, 'spread')
                if game_id not in notified_games:
                    print(f"\n🎯 Spread edge found:  {row['Team']} ({format_percentage(row['Edge For Covering Spread'])}) - {spread_source_count}/4 sources")
                    embed = create_spread_embed(row)
                    if send_discord_notification(embed):
                        new_notified[game_id] = {
                            "game": row['Game'],
                            "team": row['Team'],
                            "edge_type": "spread",
                            "edge_value": row['Edge For Covering Spread'],
                            "notified_at": datetime.now(timezone.utc).isoformat()
                        }
                        notifications_sent += 1
            else:
                print(f"  ⏭️ Skipping spread edge for {row['Team']} - only {spread_source_count}/4 sources")
        
        # Check Moneyline Edge
        if pd.notna(row.get('Moneyline Edge')) and row['Moneyline Edge'] >= MONEYLINE_THRESHOLD:
            game_id = create_game_id(row, 'moneyline')
            if game_id not in notified_games:
                print(f"\n💰 Moneyline edge found: {row['Team']} ({format_percentage(row['Moneyline Edge'])})")
                embed = create_moneyline_embed(row)
                if send_discord_notification(embed):
                    new_notified[game_id] = {
                        "game": row['Game'],
                        "team": row['Team'],
                        "edge_type": "moneyline",
                        "edge_value": row['Moneyline Edge'],
                        "notified_at": datetime.now(timezone.utc).isoformat()
                    }
                    notifications_sent += 1
        
        # Check Over Total Edge
        if pd.notna(row.get('Over Total Edge')) and row['Over Total Edge'] >= TOTAL_THRESHOLD:
            # Check if at least 4 out of 4 total sources have values
            total_source_count = count_non_null_total_sources(row)
            if total_source_count >= 4:
                # Use game-level ID instead of team-specific ID
                game_id = create_total_game_id(row, 'over')
                # Check both notified_games and current session
                if game_id not in notified_games and game_id not in total_alerts_sent:
                    print(f"\n📈 Over total edge found: {row['Game']} ({format_percentage(row['Over Total Edge'])}) - {total_source_count}/4 sources")
                    embed = create_over_embed(row)
                    if send_discord_notification(embed):
                        new_notified[game_id] = {
                            "game": row['Game'],
                            "team": "N/A",  # Not team-specific
                            "edge_type": "over",
                            "edge_value": row['Over Total Edge'],
                            "notified_at": datetime.now(timezone.utc).isoformat()
                        }
                        total_alerts_sent.add(game_id)
                        notifications_sent += 1
            else:
                print(f"  ⏭️ Skipping over total edge for {row['Game']} - only {total_source_count}/4 sources")
        
        # Check Under Total Edge
        if pd.notna(row.get('Under Total Edge')) and row['Under Total Edge'] >= TOTAL_THRESHOLD: 
            # Check if at least 3 out of 4 total sources have values
            total_source_count = count_non_null_total_sources(row)
            if total_source_count >= 3:
                # Use game-level ID instead of team-specific ID
                game_id = create_total_game_id(row, 'under')
                # Check both notified_games and current session
                if game_id not in notified_games and game_id not in total_alerts_sent:
                    print(f"\n📉 Under total edge found: {row['Game']} ({format_percentage(row['Under Total Edge'])}) - {total_source_count}/4 sources")
                    embed = create_under_embed(row)
                    if send_discord_notification(embed):
                        new_notified[game_id] = {
                            "game": row['Game'],
                            "team": "N/A",  # Not team-specific
                            "edge_type": "under",
                            "edge_value": row['Under Total Edge'],
                            "notified_at": datetime.now(timezone.utc).isoformat()
                        }
                        total_alerts_sent.add(game_id)
                        notifications_sent += 1
            else: 
                print(f"  ⏭️ Skipping under total edge for {row['Game']} - only {total_source_count}/4 sources")
    
    # Update notified games with new notifications
    if new_notified:
        notified_games.update(new_notified)
        save_notified_games(notified_games)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  - Total rows checked: {len(df)}")
    print(f"  - Notifications sent: {notifications_sent}")
    print(f"  - Total tracked games: {len(notified_games)}")
    print(f"{'='*60}")
    
    return notifications_sent

if __name__ == "__main__":
    try:
        notifications_sent = check_edges()
        sys.exit(0)
    except Exception as e: 
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
