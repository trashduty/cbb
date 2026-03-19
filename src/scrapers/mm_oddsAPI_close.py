# /// script
# dependencies = [
#   "pandas",
#   "requests",
#   "numpy",
#   "rich",
#   "python-dotenv",
#   "pytz",
# ]
# ///

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import logging
from rich.logging import RichHandler
from dotenv import load_dotenv

# Configure logging before importing oddsAPI so our config wins
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("rich")

# Determine project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

load_dotenv()

# Import shared functions from oddsAPI.py (same directory)
sys.path.insert(0, script_dir)
from oddsAPI import (
    get_combined_odds,
    american_odds_to_implied_probability,
    calculate_spread_implied_prob_safe,
)

MM_INPUT_PATH = os.path.join(project_root, 'MM_output.csv')
MM_OUTPUT_PATH = os.path.join(project_root, 'MM_Output_Final_Close.csv')
CROSSWALK_PATH = os.path.join(project_root, 'CBBAPI_crosswalk.csv')
SPREADS_LOOKUP_PATH = os.path.join(project_root, 'spreads_lookup_combined.csv')
TOTALS_LOOKUP_PATH = os.path.join(project_root, 'totals_lookup_combined.csv')


def load_mm_predictions():
    """Load MM_output.csv. Returns None if the file doesn't exist."""
    if not os.path.exists(MM_INPUT_PATH):
        logger.info(f"[cyan]MM_output.csv not found at {MM_INPUT_PATH}, skipping[/cyan]")
        return None
    df = pd.read_csv(MM_INPUT_PATH)
    logger.info(f"[green]✓[/green] Loaded MM predictions: {len(df)} rows")
    return df


def build_id_to_api_map():
    """Build {{TEAMID: API_name}} dict from CBBAPI_crosswalk.csv."""
    if not os.path.exists(CROSSWALK_PATH):
        logger.error(f"[red]✗[/red] CBBAPI_crosswalk.csv not found at {CROSSWALK_PATH}")
        return {}
    xwalk = pd.read_csv(CROSSWALK_PATH)
    id_map = {}
    for _, row in xwalk.iterrows():
        tid = row.get('TEAMID')
        api_name = row.get('API')
        if pd.notna(tid) and pd.notna(api_name) and str(api_name).strip():
            try:
                id_map[int(float(tid))] = str(api_name).strip()
            except (ValueError, TypeError):
                pass
    logger.info(f"[green]✓[/green] Crosswalk built: {len(id_map)} team mappings")
    return id_map


def resolve_team_ids(mm_df, id_map):
    """Map numeric Team/Opp IDs → API team names using crosswalk."""
    mm_df = mm_df.copy()

    def lookup(x):
        try:
            return id_map.get(int(float(x)), str(x))
        except (ValueError, TypeError):
            return str(x)

    mm_df['Team'] = mm_df['Team'].apply(lookup)
    mm_df['Opp'] = mm_df['Opp'].apply(lookup)

    # Parse game_date (M/D/YY format from Seth's file)
    mm_df['game_date'] = pd.to_datetime(mm_df['game_date'], format='%m/%d/%y', errors='coerce')

    unresolved = mm_df['Team'].apply(lambda x: str(x).isdigit())
    if unresolved.any():
        logger.warning(f"[yellow]⚠[/yellow] {unresolved.sum()} Team IDs could not be resolved")
    return mm_df


def merge_with_odds(mm_df, odds_df):
    """
    Left-join MM predictions with OddsAPI output on Team name.
    Unmatched rows retain NaN for all market columns.
    """
    if odds_df.empty:
        logger.warning("[yellow]⚠[/yellow] Odds DataFrame is empty; market columns will be NaN")
        return mm_df

    merged = mm_df.merge(odds_df, on='Team', how='left')
    matched = merged['Moneyline'].notna().sum()
    logger.info(f"[cyan]OddsAPI match: {matched} / {len(merged)} rows[/cyan]")
    return merged


def preserve_opening_odds(new_df, csv_path):
    """
    Preserve opening odds and edge values from the previous MM_Output_Final_Close.csv.
    Keyed on (Game, Team). Mirrors the logic in oddsAPI.preserve_opening_odds().
    """
    if not os.path.exists(csv_path):
        logger.info("[cyan]No existing MM_Output_Final_Close.csv; all values are opening values[/cyan]")
        return new_df

    try:
        existing_df = pd.read_csv(csv_path)
        existing_lookup = {}
        for _, row in existing_df.iterrows():
            key = (row.get('Game'), row.get('Team'))
            existing_lookup[key] = {
                'Opening Spread': row.get('Opening Spread'),
                'Opening Moneyline': row.get('Opening Moneyline'),
                'Opening Total': row.get('Opening Total'),
                'Opening Odds Time': row.get('Opening Odds Time'),
                'Opening Spread Edge': row.get('Opening Spread Edge'),
                'Opening Moneyline Edge': row.get('Opening Moneyline Edge'),
                'Opening Over Edge': row.get('Opening Over Edge'),
                'Opening Under Edge': row.get('Opening Under Edge'),
            }

        preserved = 0
        for idx, row in new_df.iterrows():
            key = (row.get('Game'), row.get('Team'))
            if key not in existing_lookup:
                continue
            vals = existing_lookup[key]
            if pd.notna(vals.get('Opening Spread')):
                new_df.at[idx, 'Opening Spread'] = vals['Opening Spread']
            if pd.notna(vals.get('Opening Moneyline')):
                new_df.at[idx, 'Opening Moneyline'] = vals['Opening Moneyline']
            if pd.notna(vals.get('Opening Total')):
                new_df.at[idx, 'Opening Total'] = vals['Opening Total']
            if pd.notna(vals.get('Opening Odds Time')):
                new_df.at[idx, 'Opening Odds Time'] = vals['Opening Odds Time']
            if pd.notna(vals.get('Opening Spread Edge')):
                new_df.at[idx, 'Opening Spread Edge'] = vals['Opening Spread Edge']
            if pd.notna(vals.get('Opening Moneyline Edge')):
                new_df.at[idx, 'Opening Moneyline Edge'] = vals['Opening Moneyline Edge']
            if pd.notna(vals.get('Opening Over Edge')):
                new_df.at[idx, 'Opening Over Edge'] = vals['Opening Over Edge']
            if pd.notna(vals.get('Opening Under Edge')):
                new_df.at[idx, 'Opening Under Edge'] = vals['Opening Under Edge']
            preserved += 1

        if preserved:
            logger.info(f"[green]✓[/green] Preserved opening odds for {preserved} existing games")
        return new_df

    except Exception as e:
        logger.warning(f"[yellow]⚠[/yellow] Error preserving opening odds: {e}")
        return new_df


def process_mm_dataframe(df):
    """
    Apply MM-specific spread / total / moneyline formulas and lookup table joins.

    Key differences from mm_oddsAPI.py (50/50):
      - Spread blend: 30% model / 70% market  (vs 50/50)
      - Total blend:  30% model / 70% market
      - Moneyline: raw ML_prob vs market implied (no blend with devigged prob)
      - No per-model columns, no consensus flags, no std-dev columns
    """
    df = df.copy()

    # ── Spread ──────────────────────────────────────────────────────────────
    df['model_spread'] = pd.to_numeric(df['Raw_Spread'], errors='coerce')
    df['market_spread'] = (pd.to_numeric(df.get('Consensus Spread'), errors='coerce') * 2).round() / 2

    # total_category for spread lookup (based on market total)
    df['theoddsapi_total'] = pd.to_numeric(df.get('Projected Total'), errors='coerce')
    df['total_category'] = pd.cut(
        df['theoddsapi_total'],
        bins=[-float('inf'), 137.5, 145.5, float('inf')],
        labels=[1, 2, 3]
    ).astype('Int64')

    # Predicted Outcome: 30% model / 70% market, rounded to 0.5
    df['Predicted Outcome'] = (
        (df['model_spread'] * 0.3 + df['market_spread'] * 0.7) * 2
    ).round() / 2

    # Spread implied probability from Spread Price
    if 'Spread Price' in df.columns:
        df['spread_implied_prob'] = df['Spread Price'].apply(calculate_spread_implied_prob_safe)
    else:
        df['spread_implied_prob'] = 0.5238095238095238

    # Spreads lookup
    try:
        spreads_lkp = pd.read_csv(SPREADS_LOOKUP_PATH)
        df['market_spread_rounded'] = (df['market_spread'] * 2).round() / 2
        df = df.merge(
            spreads_lkp,
            left_on=['total_category', 'market_spread_rounded', 'Predicted Outcome'],
            right_on=['total_category', 'market_spread', 'model_spread'],
            how='left',
            suffixes=('', '_lookup')
        )
        df['Spread Cover Probability'] = df['cover_prob']
        df['Edge For Covering Spread'] = df['Spread Cover Probability'] - df['spread_implied_prob']
        df.drop(columns=['market_spread_rounded', 'market_spread_lookup', 'model_spread_lookup',
                         'cover_prob', 'spread_implied_prob'],
                inplace=True, errors='ignore')
        logger.info("[green]✓[/green] Applied spreads lookup")
    except FileNotFoundError:
        logger.warning("[yellow]⚠[/yellow] spreads_lookup_combined.csv not found")
        df['Spread Cover Probability'] = np.nan
        df['Edge For Covering Spread'] = np.nan
        df.drop(columns=['spread_implied_prob'], inplace=True, errors='ignore')

    # ── Totals ───────────────────────────────────────────────────────────────
    df['market_total'] = pd.to_numeric(df.get('Projected Total'), errors='coerce')
    df['model_total'] = pd.to_numeric(df['Raw_Total'], errors='coerce')

    # spread_category for totals lookup (based on absolute spread, matching oddsAPI.py)
    # Category 1: 0-2.5, 2: 2.5-10, 3: >10 — use abs so both teams in same game get same category
    df['spread_category'] = pd.cut(
        df['market_spread'].abs(),
        bins=[0, 2.5, 10.0, float('inf')],
        labels=[1, 2, 3]
    ).astype('Int64')

    # average_total: 30% model / 70% market, rounded to 0.5
    df['average_total'] = (
        (0.3 * df['model_total'].fillna(0) +
         0.7 * df['market_total'].fillna(df['model_total'])) * 2
    ).round() / 2

    try:
        totals_lkp = pd.read_csv(TOTALS_LOOKUP_PATH)
        # Drop duplicates before totals merge (mirrors oddsAPI.py)
        if 'Game' in df.columns and 'Team' in df.columns:
            df = df.drop_duplicates(subset=['Game', 'Team'], keep='first')
        df['market_total_rounded'] = (df['market_total'] * 2).round() / 2
        df = df.merge(
            totals_lkp,
            left_on=['spread_category', 'market_total_rounded', 'average_total'],
            right_on=['spread_category', 'market_total', 'model_total'],
            how='left',
            suffixes=('', '_lookup')
        )
        df['Over Cover Probability'] = df['over_prob']
        df['Under Cover Probability'] = df['under_prob']
        df.drop(columns=['market_total_rounded', 'market_total_lookup', 'model_total_lookup',
                         'over_prob', 'under_prob'],
                inplace=True, errors='ignore')
        logger.info("[green]✓[/green] Applied totals lookup")
    except FileNotFoundError:
        logger.warning("[yellow]⚠[/yellow] totals_lookup_combined.csv not found")
        df['Over Cover Probability'] = np.nan
        df['Under Cover Probability'] = np.nan
        df.drop(columns=['market_total_rounded'], inplace=True, errors='ignore')

    # Totals edges
    df['over_implied_prob'] = df['Over Price'].apply(
        lambda x: american_odds_to_implied_probability(x) if pd.notna(x) else None
    ) if 'Over Price' in df.columns else np.nan
    df['under_implied_prob'] = df['Under Price'].apply(
        lambda x: american_odds_to_implied_probability(x) if pd.notna(x) else None
    ) if 'Under Price' in df.columns else np.nan
    df['Over Total Edge'] = df['Over Cover Probability'] - df['over_implied_prob']
    df['Under Total Edge'] = df['Under Cover Probability'] - df['under_implied_prob']
    df.drop(columns=['over_implied_prob', 'under_implied_prob'], inplace=True, errors='ignore')

    # ── Moneyline ────────────────────────────────────────────────────────────
    # Raw ML_prob vs market implied — no blend with devigged probability
    df['Moneyline Win Probability'] = pd.to_numeric(df['ML_prob'], errors='coerce')
    ml_implied = df['Moneyline'].apply(
        lambda x: american_odds_to_implied_probability(x) if pd.notna(x) else None
    ) if 'Moneyline' in df.columns else pd.Series(np.nan, index=df.index)
    df['Moneyline Edge'] = df['Moneyline Win Probability'] - ml_implied

    # Current Moneyline (consensus rounded)
    if 'Moneyline' in df.columns:
        df['Current Moneyline'] = pd.to_numeric(df['Moneyline'], errors='coerce').round().astype('Int64')
    else:
        df['Current Moneyline'] = np.nan

    # ── Game identifier ───────────────────────────────────────────────────────
    if 'Home Team' in df.columns and 'Away Team' in df.columns:
        matched_mask = df['Home Team'].notna() & df['Away Team'].notna()
        df['Game'] = np.where(
            matched_mask,
            df['Home Team'].fillna('') + ' vs. ' + df['Away Team'].fillna(''),
            np.nan
        )
    else:
        df['Game'] = np.nan

    # ── Opening columns (DraftKings first-seen values) ────────────────────────
    df['Opening Spread'] = df['DK_Spread'] if 'DK_Spread' in df.columns else np.nan
    if 'DK_Moneyline' in df.columns:
        dk_ml = pd.to_numeric(df['DK_Moneyline'], errors='coerce')
        df['Opening Moneyline'] = dk_ml.round().astype('Int64')
    else:
        df['Opening Moneyline'] = pd.NA
    df['Opening Total'] = df['DK_Total'] if 'DK_Total' in df.columns else np.nan

    has_dk_spread = df['Opening Spread'].notna()
    has_dk_ml = df['Opening Moneyline'].notna()
    has_dk_total = df['Opening Total'].notna()

    df['Opening Spread Edge'] = np.where(has_dk_spread, df['Edge For Covering Spread'], np.nan)
    df['Opening Moneyline Edge'] = np.where(has_dk_ml, df['Moneyline Edge'], np.nan)
    df['Opening Over Edge'] = np.where(has_dk_total, df['Over Total Edge'], np.nan)
    df['Opening Under Edge'] = np.where(has_dk_total, df['Under Total Edge'], np.nan)

    df['Opening Odds Time'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    # ── Final column order ────────────────────────────────────────────────────
    column_order = [
        'Game', 'Game Time', 'Opening Odds Time', 'Team',
        'total_category', 'market_spread', 'model_spread', 'Predicted Outcome',
        'Spread Cover Probability',
        'Opening Spread', 'Edge For Covering Spread', 'Opening Spread Edge',
        'Moneyline Win Probability', 'Opening Moneyline', 'Current Moneyline',
        'Devigged Probability', 'Moneyline Edge', 'Opening Moneyline Edge',
        'spread_category', 'market_total', 'model_total', 'average_total',
        'Opening Total', 'theoddsapi_total',
        'Over Cover Probability', 'Under Cover Probability',
        'Over Total Edge', 'Under Total Edge', 'Opening Over Edge', 'Opening Under Edge',
    ]
    available = [c for c in column_order if c in df.columns]
    return df[available].reset_index(drop=True)


def main():
    logger.info("=== Starting MM Close OddsAPI ETL ===")

    # Step 1: Load MM predictions
    mm_df = load_mm_predictions()
    if mm_df is None:
        return

    # Step 2: Resolve team IDs → API names
    id_map = build_id_to_api_map()
    mm_df = resolve_team_ids(mm_df, id_map)
    logger.info(f"[cyan]Sample resolved teams: {mm_df['Team'].head().tolist()}[/cyan]")

    # Step 3: Fetch market odds
    logger.info("[cyan]Fetching market odds from OddsAPI...[/cyan]")
    odds_df = get_combined_odds()

    # Step 4: Merge MM predictions with market odds
    merged_df = merge_with_odds(mm_df, odds_df)

    # Step 5: Apply formulas
    final_df = process_mm_dataframe(merged_df)

    # Step 6: Preserve opening odds from previous run
    final_df = preserve_opening_odds(final_df, MM_OUTPUT_PATH)

    # Step 7: Save
    final_df.to_csv(MM_OUTPUT_PATH, index=False)
    logger.info(f"[green]✓[/green] Saved MM_Output_Final_Close.csv ({len(final_df)} rows) → {MM_OUTPUT_PATH}")
    logger.info("=== MM Close OddsAPI ETL completed ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"[red]✗[/red] MM Close OddsAPI script failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
