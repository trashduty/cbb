# College Basketball (CBB) Analytics Pipeline

## Project Overview

This repository is a data pipeline that aggregates college basketball predictions from multiple rating systems and combines them with real-time betting odds to generate actionable insights. The pipeline outputs a single file (`CBB_Output.csv`) that is consumed by a Shiny web application for visualization and analysis.

## Purpose

The pipeline enables sports analytics by:
- Aggregating predictions from 4+ rating systems (KenPom, EvanMiya, Barttorvik, Hasla)
- Fetching real-time betting odds from sportsbooks via The Odds API
- Calculating "edge" opportunities where model predictions differ from market prices
- Standardizing team names and data formats across all sources
- Updating every 5 minutes to capture rapid odds movements (e.g., injury news)

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ SCRAPERS (Raw Data Collection)                                  │
├─────────────────────────────────────────────────────────────────┤
│ 1. EvanMiya Scraper (Node.js + Playwright)                      │
│    → data/em.csv (5,200+ games)                                 │
│                                                                  │
│ 2. KenPom Scraper (Node.js + Playwright)                        │
│    → data/kp.csv (760+ games)                                   │
│                                                                  │
│ 3. Barttorvik Scraper (Python + BeautifulSoup)                  │
│    → data/bt_mapped.csv                                         │
│                                                                  │
│ 4. Hasla Scraper (Python + Selenium)                            │
│    → data/hasla_mapped.csv (140+ games)                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ TRANSFORMERS (Data Standardization)                             │
├─────────────────────────────────────────────────────────────────┤
│ 5. EvanMiya Transformer (Node.js)                               │
│    → Converts 1-row-per-game to 2-row-per-game format          │
│                                                                  │
│ 6. Team Name Mapper (Python)                                    │
│    → Standardizes team names using crosswalk.csv               │
│    → Creates kp_mapped.csv & em_mapped.csv                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ JOINER (Data Merging)                                           │
├─────────────────────────────────────────────────────────────────┤
│ 7. Dataset Joiner (Node.js)                                     │
│    → Left join: KP ← EM ← BT ← Hasla                           │
│    → data/combined_data.csv (1,000+ rows)                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ENRICHMENT (Odds & Probabilities)                               │
├─────────────────────────────────────────────────────────────────┤
│ 8. OddsAPI Processor (Python)                                   │
│    → Fetches real-time odds from The Odds API                  │
│    → Merges with combined_data.csv                             │
│    → Calculates:                                                │
│      • Forecasted spreads (median of 4 models)                 │
│      • Forecasted totals (median of 4 models)                  │
│      • Win probabilities (devigged moneyline)                  │
│      • Spread/Total coverage probabilities (lookup tables)     │
│      • Edge calculations (model prob - market implied prob)    │
│    → Filters to upcoming games only                            │
│    → CBB_Output.csv (FINAL OUTPUT)                             │
└─────────────────────────────────────────────────────────────────┘
```

## Output File: `CBB_Output.csv`

### Purpose
This is the **only file consumed by the Shiny app**. It contains all data needed for visualization and analysis.

### Structure
- **Format**: CSV with 37 columns, 2 rows per game (one for each team's perspective)
- **Game Times**: All standardized to Eastern Time (ET)
- **Update Frequency**: Every 5 minutes via GitHub Actions

### Key Columns

#### Game Information
- `Game`: Matchup in "Team A vs. Team B" format
- `Game Time`: "Nov 03 07:00PM ET" format (standardized to ET)
- `Team`: Which team this row represents

#### Spread Analysis
- `market_spread`: Opening spread from sportsbooks
- `model_spread`: Median of 4 model predictions
- `Predicted Outcome`: Weighted average (60% market + 40% model)
- `Spread Cover Probability`: Probability this team covers the spread
- `Edge For Covering Spread`: Model probability - market implied probability
- `Spread Std. Dev.`: Standard deviation across 4 models
- Individual model spreads: `spread_kenpom`, `spread_evanmiya`, `spread_barttorvik`, `spread_hasla`

#### Moneyline Analysis
- `Moneyline Win Probability`: Blended win probability (50% model + 50% devigged)
- `Opening Moneyline`: American odds format (-150, +200, etc.)
- `Devigged Probability`: Vig-removed probability from moneyline
- `Moneyline Edge`: Win probability - market implied probability
- `Moneyline Std. Dev.`: Standard deviation across models
- Individual model win probs: `win_prob_kenpom`, `win_prob_evanmiya`, `win_prob_barttorvik`

#### Totals (Over/Under) Analysis
- `market_total`: Over/Under line from sportsbooks
- `model_total`: Median of 4 model projections
- `average_total`: Weighted average (60% market + 40% model)
- `Totals Std. Dev.`: Standard deviation across models
- `Over Cover Probability`: Probability game goes over
- `Under Cover Probability`: Probability game goes under
- `Over Total Edge`: Over probability - market implied probability
- `Under Total Edge`: Under probability - market implied probability
- Individual model totals: `projected_total_kenpom`, `projected_total_evanmiya`, `projected_total_barttorvik`, `projected_total_hasla`

#### Categorization
- `total_category`: Game total category (1: <137.5, 2: 137.5-145.5, 3: >145.5)
- `spread_category`: Spread category (1: <-10, 2: -10 to -2.5, 3: >-2.5)

## Tech Stack

### Node.js Components
- **Playwright**: Browser automation for EvanMiya & KenPom scrapers
- **csv-parser**: CSV reading
- **csv-writer**: CSV writing
- **dotenv**: Environment variable management

### Python Components
- **UV**: Python package manager (PEP 723 inline script metadata)
- **Pandas**: Data manipulation
- **Requests**: HTTP requests
- **BeautifulSoup4**: HTML parsing (Barttorvik)
- **Selenium**: Browser automation (Hasla)
- **Rich**: Terminal formatting
- **PyTZ**: Timezone conversions
- **NumPy**: Numerical computations

### Deployment
- **GitHub Actions**: Automated scraping every 5 minutes
- **Ubuntu Latest**: CI/CD runner environment

## Running Locally

### Prerequisites
```bash
# Node.js 18+
node --version

# Python 3.10+
python3 --version

# UV package manager
pip install uv
```

### Setup
```bash
# Install Node dependencies
npm install

# Install Playwright browsers
npx playwright install chromium

# Create .env file with credentials
echo "EMAIL=your_kenpom_email" > .env
echo "PASSWORD=your_kenpom_password" >> .env
echo "ODDS_API_KEY=your_odds_api_key" >> .env
```

### Run Full Pipeline
```bash
node src/index.js
```

This executes all 8 steps sequentially and produces `CBB_Output.csv`.

### Run Individual Components
```bash
# EvanMiya scraper
node src/scrapers/evanmiya-scraper.js

# KenPom scraper
node src/scrapers/kenpom-scraper.js

# Barttorvik scraper
uv run src/scrapers/barttorvik.py

# Hasla scraper
uv run src/scrapers/hasla.py

# OddsAPI processor
uv run src/scrapers/oddsAPI.py
```

## GitHub Actions Workflow

### Trigger
- **Schedule**: Every 5 minutes (`*/5 * * * *`)
- **Manual**: Via workflow_dispatch

### Why 5 Minutes?
Sports betting markets move rapidly in response to:
- Injury news
- Starting lineup changes
- Sharp bettor activity
- Weather conditions (for outdoor sports)

Frequent updates ensure the Shiny app displays near-real-time edge opportunities.

### Workflow Steps
1. Checkout code
2. Install Node.js 18 + dependencies
3. Install Playwright browsers
4. Install Python 3.10 + UV
5. Install Python dependencies (via UV or requirements.txt)
6. Configure credentials from GitHub Secrets
7. Run full pipeline (`node src/index.js`)
8. Commit & push `CBB_Output.csv` if changed

### Required GitHub Secrets
- `EMAIL`: KenPom login email
- `PASSWORD`: KenPom login password
- `ODDS_API_KEY`: The Odds API key ([get one free](https://the-odds-api.com/))

## Data Sources

### 1. KenPom (kenpom.com)
- **Access**: Subscription required (~$20/year)
- **Data**: FanMatch predictions (spreads, win probabilities, totals)
- **Method**: Playwright scrapes HTML tables
- **Coverage**: 760+ games

### 2. EvanMiya (evanmiya.com)
- **Access**: Free with account
- **Data**: Game predictions with spread, win probability, over/under
- **Method**: Playwright downloads CSV file
- **Coverage**: 5,200+ games (most comprehensive)

### 3. Barttorvik (barttorvik.com)
- **Access**: Free, no account needed
- **Data**: T-Rank lines and projections
- **Method**: BeautifulSoup scrapes public pages
- **Coverage**: Variable by date

### 4. Hasla Metrics (haslametrics.com)
- **Access**: Free, no account needed
- **Data**: Score projections, spreads
- **Method**: Selenium loads dynamic content
- **Coverage**: 140+ games

### 5. The Odds API (the-odds-api.com)
- **Access**: Free tier (500 requests/month) or paid
- **Data**: Real-time odds from 15+ sportsbooks
- **Method**: REST API
- **Coverage**: Major markets only (excludes D2/D3)

## Team Name Mapping

Different sources use different team name conventions:
- KenPom: "St. Mary's CA"
- EvanMiya: "Saint Mary's"
- Odds API: "Saint Mary's Gaels"

The `data/crosswalk.csv` file maps ~350 teams across all sources to a standardized "API" name format.

## Edge Calculation

**Edge** = Model Probability - Market Implied Probability

### Example
- Model says Team A has 55% chance to cover spread
- Market odds imply 50% chance (spread is -110 both sides)
- **Edge = +5%** → Positive edge on Team A covering

### Interpretation
- **Positive edge**: Model sees value in this bet
- **Negative edge**: Market is sharper than the model
- **Large edge (>10%)**: Potential inefficiency or model disagreement

## Lookup Tables

### `data/spreads_lookup.csv`
Maps spread values to historical coverage probabilities based on:
- Spread size
- Game total category (pace of game)

### `data/totals_lookup.csv`
Maps total values to historical over/under coverage probabilities based on:
- Total size
- Spread category (competitiveness)

These are empirically derived from historical CBB game data.

## Limitations

### Market Coverage
- Only games with betting markets available (excludes most D2/D3)
- Small conferences may have limited model coverage

### Model Recency
- Models scraped as-is from sources
- May not reflect last-minute changes (injuries within 5 min of scrape)

### Data Quality
- Team name mismatches can cause join failures
- Unmapped teams are dropped from final output

## Downstream Usage

The Shiny app (separate repository) reads `CBB_Output.csv` and provides:
- Interactive game browser
- Edge filtering and sorting
- Model comparison charts
- Historical edge tracking
- Customizable alerts for high-edge opportunities

## Maintenance

### Adding New Teams
Edit `data/crosswalk.csv` to add mappings for new teams entering D1.

### Updating Lookup Tables
Regenerate `spreads_lookup.csv` and `totals_lookup.csv` using historical game data (separate analysis script, not in this repo).

### Debugging Failed Joins
Check logs for:
- Unmapped team names
- Date format mismatches
- Missing odds data

Run individual scrapers to isolate issues.

## Contributing

This is a personal project for sports analytics research. Not accepting external contributions at this time.

## License

Proprietary - For personal use only. Data sources have their own terms of service.

---

**Last Updated**: November 2025
**Maintained By**: Personal project
**Questions**: See GitHub Issues (disabled for this private repo)
