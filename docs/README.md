# CBB Betting Analysis - GitHub Pages

This directory contains a static HTML page that displays real-time CBB (College Basketball Betting) data from the `CBB_Output.csv` file.

## Features

- **Real-time updates**: Fetches data directly from GitHub repository with cache-busting
- **Auto-refresh**: Page automatically refreshes every 60 seconds
- **Interactive table**: Sortable columns and search functionality via DataTables
- **Color-coded insights**: Visual indicators for probabilities and edges
  - Green: Favorable/High probability
  - Yellow: Neutral
  - Red: Unfavorable/Low probability
- **Responsive design**: Works on mobile and desktop devices
- **Consensus flags**: Shows Y/N for betting consensus indicators

## GitHub Pages Setup

To enable GitHub Pages for this site:

1. Go to your repository on GitHub: https://github.com/trashduty/cbb
2. Click on the **Settings** tab
3. In the left sidebar, click **Pages**
4. Under **Source**:
   - Select **Deploy from a branch**
   - Choose branch: **main** (or your default branch)
   - Choose folder: **/docs**
5. Click **Save**
6. Wait a few minutes for the site to build
7. Your site will be published at: **https://trashduty.github.io/cbb/**

## How It Works

1. The HTML page fetches `CBB_Output.csv` from the repository's main branch
2. Papa Parse library converts the CSV into structured data
3. DataTables renders an interactive, sortable table
4. Color gradients are applied to probability and edge columns
5. The page auto-refreshes every 60 seconds to show the latest data

## Advantages Over Shiny App

- **Instant updates**: No server-side delays
- **Always available**: Static hosting is more reliable
- **Free hosting**: GitHub Pages is free and fast
- **No maintenance**: No server to maintain or monitor
- **Fast loading**: Simple HTML loads much faster than Shiny apps

## Data Columns

The table displays 20 key columns for betting analysis:

1. Game
2. Team
3. Game Time
4. Predicted Outcome
5. Current Spread
6. Spread Cover Probability
7. Edge For Covering Spread
8. Spread Consensus
9. Current Moneyline
10. Moneyline Win Probability
11. Moneyline Edge
12. Moneyline Consensus
13. Predicted Total
14. Market Total
15. Over Cover Probability
16. Under Cover Probability
17. Over Total Edge
18. Under Total Edge
19. Over Consensus
20. Under Consensus

## Updating the Data

Simply push updates to `CBB_Output.csv` in the repository. The GitHub Pages site will display the new data within 60 seconds (or immediately upon manual refresh).

## Technical Details

- **Libraries Used**:
  - jQuery 3.7.0
  - DataTables 1.13.6
  - Papa Parse 5.4.1
- **CDN**: All libraries loaded from CDN for fast access
- **Caching**: Cache-busting ensures fresh data on every load
