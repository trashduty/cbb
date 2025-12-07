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
from datetime import datetime, timezone

# Define paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
csv_file = os.path.join(project_root, 'CBB_Output.csv')
notified_file = os.path.join(project_root, 'notified_games.json')

# Edge thresholds
SPREAD_THRESHOLD = 0.04  # 4%
MONEYLINE_THRESHOLD = 0.04  # 4%
TOTAL_THRESHOLD = 0.01  # 1%

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
        print(f"Warning: Could not load notified games: {e}")
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
        print("Warning: DISCORD_WEBHOOK_URL not set, skipping notification")
        return False
    
    try:
        payload = {
            "embeds": [embed_data]
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
                "name": "Predicted Outcome",
                "value": format_decimal(row['Predicted Outcome'], 1),
                "inline": True
            },
            {
                "name": "Spread Cover Probability",
                "value": format_percentage(row['Spread Cover Probability']),
                "inline": True
            },
            {
                "name": "Opening Spread",
                "value": format_decimal(row['Opening Spread'], 1),
                "inline": True
            }
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
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
                "value": format_percentage(row['Moneyline Win Probability']),
                "inline": True
            },
            {
                "name": "Opening Moneyline",
                "value": format_decimal(row['Opening Moneyline'], 0),
                "inline": True
            }
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return embed

def create_over_embed(row):
    """Create Discord embed for over total edge alert."""
    edge_value = row['Over Total Edge']
    
    embed = {
        "title": f"📈 Over Total Edge Alert: {row['Team']}",
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
                "value": format_percentage(row['Over Cover Probability']),
                "inline": True
            },
            {
                "name": "Market Total",
                "value": format_decimal(row['market_total'], 1),
                "inline": True
            },
            {
                "name": "Model Total",
                "value": format_decimal(row['model_total'], 2),
                "inline": True
            }
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return embed

def create_under_embed(row):
    """Create Discord embed for under total edge alert."""
    edge_value = row['Under Total Edge']
    
    embed = {
        "title": f"📉 Under Total Edge Alert: {row['Team']}",
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
                "name": "Market Total",
                "value": format_decimal(row['market_total'], 1),
                "inline": True
            },
            {
                "name": "Model Total",
                "value": format_decimal(row['model_total'], 2),
                "inline": True
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
    print(f"Previously notified: {len(notified_games)} game opportunities")
    
    notifications_sent = 0
    new_notified = {}
    
    # Check each row for qualifying edges
    for idx, row in df.iterrows():
        # Check Spread Edge
        if pd.notna(row.get('Edge For Covering Spread')) and row['Edge For Covering Spread'] >= SPREAD_THRESHOLD:
            game_id = create_game_id(row, 'spread')
            if game_id not in notified_games:
                print(f"\n🎯 Spread edge found: {row['Team']} ({format_percentage(row['Edge For Covering Spread'])})")
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
            game_id = create_game_id(row, 'over')
            if game_id not in notified_games:
                print(f"\n📈 Over total edge found: {row['Team']} ({format_percentage(row['Over Total Edge'])})")
                embed = create_over_embed(row)
                if send_discord_notification(embed):
                    new_notified[game_id] = {
                        "game": row['Game'],
                        "team": row['Team'],
                        "edge_type": "over",
                        "edge_value": row['Over Total Edge'],
                        "notified_at": datetime.now(timezone.utc).isoformat()
                    }
                    notifications_sent += 1
        
        # Check Under Total Edge
        if pd.notna(row.get('Under Total Edge')) and row['Under Total Edge'] >= TOTAL_THRESHOLD:
            game_id = create_game_id(row, 'under')
            if game_id not in notified_games:
                print(f"\n📉 Under total edge found: {row['Team']} ({format_percentage(row['Under Total Edge'])})")
                embed = create_under_embed(row)
                if send_discord_notification(embed):
                    new_notified[game_id] = {
                        "game": row['Game'],
                        "team": row['Team'],
                        "edge_type": "under",
                        "edge_value": row['Under Total Edge'],
                        "notified_at": datetime.now(timezone.utc).isoformat()
                    }
                    notifications_sent += 1
    
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
