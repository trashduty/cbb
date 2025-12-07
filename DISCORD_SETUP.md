# Discord Notification System Setup

This document describes the automated Discord notification system that alerts when betting edges are detected in `CBB_Output.csv`.

## Overview

The system monitors `CBB_Output.csv` for games with positive betting edges and sends Discord alerts when any of the following thresholds are met:

- **Spread Edge**: ≥ 4% (0.04)
- **Moneyline Edge**: ≥ 4% (0.04)
- **Total Edge**: ≥ 1% (0.01) for Over or Under

## Features

- **Deduplication**: Tracks notified games in `notified_games.json` to prevent repeated alerts
- **Rich Notifications**: Uses Discord embeds with color coding (green for spread/moneyline, blue for over, orange for under)
- **Automated Execution**: Runs every 15 minutes via GitHub Actions during typical betting hours
- **Detailed Information**: Each alert includes relevant probabilities, spreads, and market data

## Setup Instructions

### 1. Create a Discord Webhook

1. Open your Discord server and navigate to the channel where you want to receive notifications
2. Click the gear icon (Edit Channel)
3. Go to **Integrations** → **Webhooks**
4. Click **New Webhook**
5. Give it a name (e.g., "CBB Edge Alerts")
6. Copy the **Webhook URL**

### 2. Add Discord Webhook to GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `DISCORD_WEBHOOK_URL`
5. Value: Paste the webhook URL you copied
6. Click **Add secret**

### 3. Verify Setup

The workflow will automatically run:
- Every 15 minutes during betting hours (9 AM - 2 AM ET)
- When `CBB_Output.csv` is updated
- Manually via the Actions tab

To test immediately:
1. Go to **Actions** tab in GitHub
2. Select **Check Betting Edges** workflow
3. Click **Run workflow**

## Files

- `src/utils/check_edges.py` - Python script that checks edges and sends notifications
- `.github/workflows/check-betting-edges.yml` - GitHub Actions workflow
- `notified_games.json` - Tracks games that have been notified to prevent duplicates

## Notification Format

### Spread Edge Alert
- Edge percentage
- Predicted outcome
- Spread cover probability
- Opening spread

### Moneyline Edge Alert
- Edge percentage
- Moneyline win probability
- Opening moneyline

### Over/Under Edge Alert
- Edge percentage
- Over/Under cover probability
- Market total
- Model total

## Maintenance

### Clearing Notification History

The `notified_games.json` file stores all notified games. To reset notifications (e.g., at the start of a new season):

1. Edit `notified_games.json` and replace contents with `{}`
2. Commit and push the change

### Adjusting Edge Thresholds

Edit the threshold constants in `src/utils/check_edges.py`:

```python
SPREAD_THRESHOLD = 0.04  # 4%
MONEYLINE_THRESHOLD = 0.04  # 4%
TOTAL_THRESHOLD = 0.01  # 1%
```

### Modifying Schedule

Edit the cron schedule in `.github/workflows/check-betting-edges.yml` to change when the workflow runs.

## Troubleshooting

### No notifications received

1. Check that `DISCORD_WEBHOOK_URL` secret is set correctly
2. Verify the webhook URL is valid by testing it manually
3. Check the Actions tab for workflow run logs
4. Ensure there are games with edges that meet the thresholds

### Duplicate notifications

- The system uses `notified_games.json` to track sent notifications
- Each game + team + edge type combination is only notified once
- If you're getting duplicates, check that the workflow is committing changes to `notified_games.json`

### Workflow not running

- Verify the workflow file is in `.github/workflows/`
- Check that the workflow is enabled in the Actions tab
- Confirm the cron schedule is in UTC time
