# /// script
# dependencies = [
#   "pandas",
#   "pytz"
# ]
# ///
"""
Generate model record reports from graded bet results.

This script reads graded_results.csv and generates:
1. model_record.csv - Full season running record by edge tier
2. docs/model_record.md - Markdown report for GitHub Pages

Edge tiers: 0-1.9%, 2-3.9%, 4-5.9%, 6%+
"""

import pandas as pd
import os
import sys
from datetime import datetime
import pytz

# Project paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
graded_results_path = os.path.join(project_root, 'graded_results.csv')
model_record_csv_path = os.path.join(project_root, 'model_record.csv')
docs_dir = os.path.join(project_root, 'docs')
model_record_md_path = os.path.join(docs_dir, 'model_record.md')

# Edge tier definitions (in decimal, e.g., 0.02 = 2%)
EDGE_TIERS = [
    {'name': '0-1.9%', 'min': 0.00, 'max': 0.02},
    {'name': '2-3.9%', 'min': 0.02, 'max': 0.04},
    {'name': '4-5.9%', 'min': 0.04, 'max': 0.06},
    {'name': '6%+', 'min': 0.06, 'max': float('inf')},
]


def load_graded_results():
    """Load graded results from CSV."""
    if not os.path.exists(graded_results_path):
        print(f"Error: {graded_results_path} not found")
        return None

    try:
        df = pd.read_csv(graded_results_path)
        print(f"Loaded {len(df)} graded results")
        return df
    except Exception as e:
        print(f"Error loading graded results: {e}")
        return None


def get_edge_tier(edge_value):
    """Determine which edge tier a value belongs to."""
    if pd.isna(edge_value):
        return None

    for tier in EDGE_TIERS:
        if tier['min'] <= edge_value < tier['max']:
            return tier['name']

    return None


def calculate_record(df, edge_col, outcome_col, bet_type, consensus_col=None):
    """
    Calculate win/loss record by edge tier.

    Args:
        df: DataFrame with graded results
        edge_col: Column name for opening edge
        outcome_col: Column name for outcome (1=win, 0=loss)
        bet_type: Name of bet type for reporting
        consensus_col: Optional column name for consensus flag (1=consensus)

    Returns:
        List of dictionaries with tier records
    """
    # Filter by consensus if specified
    if consensus_col and consensus_col in df.columns:
        df = df[df[consensus_col] == 1]
    
    records = []

    for tier in EDGE_TIERS:
        # Filter to this tier
        tier_mask = (
            (df[edge_col] >= tier['min']) &
            (df[edge_col] < tier['max']) &
            (df[outcome_col].notna())
        )
        tier_df = df[tier_mask]

        if len(tier_df) == 0:
            records.append({
                'bet_type': bet_type,
                'edge_tier': tier['name'],
                'wins': 0,
                'losses': 0,
                'total': 0,
                'win_rate': None,
                'profit_units': 0
            })
            continue

        wins = (tier_df[outcome_col] == 1).sum()
        losses = (tier_df[outcome_col] == 0).sum()
        total = wins + losses
        win_rate = wins / total if total > 0 else None

        # Calculate profit assuming -110 standard juice
        # Win = +0.909 units, Loss = -1 unit
        profit_units = (wins * 0.909) - losses

        records.append({
            'bet_type': bet_type,
            'edge_tier': tier['name'],
            'wins': wins,
            'losses': losses,
            'total': total,
            'win_rate': win_rate,
            'profit_units': round(profit_units, 2)
        })

    return records


def calculate_individual_model_record(df, outcome_col, model_name):
    """
    Calculate overall record for an individual model (no edge tiers).
    
    Args:
        df: DataFrame with graded results
        outcome_col: Column name for outcome (1=win, 0=loss)
        model_name: Name of the model for reporting
        
    Returns:
        Dictionary with model record
    """
    # Filter out missing values
    valid_df = df[df[outcome_col].notna()]
    
    if len(valid_df) == 0:
        return {
            'model_name': model_name,
            'wins': 0,
            'losses': 0,
            'total': 0,
            'win_rate': None,
            'profit_units': 0
        }
    
    wins = (valid_df[outcome_col] == 1).sum()
    losses = (valid_df[outcome_col] == 0).sum()
    total = wins + losses
    win_rate = wins / total if total > 0 else None
    
    # Calculate profit assuming -110 standard juice
    profit_units = (wins * 0.909) - losses
    
    return {
        'model_name': model_name,
        'wins': wins,
        'losses': losses,
        'total': total,
        'win_rate': win_rate,
        'profit_units': round(profit_units, 2)
    }


def generate_model_record(df):
    """Generate model record for all bet types by edge tier."""
    all_records = []

    # Determine which columns to use (prefer opening edge, fallback to current edge)
    spread_edge_col = 'opening_spread_edge' if 'opening_spread_edge' in df.columns else 'spread_edge'
    ml_edge_col = 'opening_moneyline_edge' if 'opening_moneyline_edge' in df.columns else 'moneyline_edge'
    over_edge_col = 'opening_over_edge' if 'opening_over_edge' in df.columns else 'over_edge'
    under_edge_col = 'opening_under_edge' if 'opening_under_edge' in df.columns else 'under_edge'

    # Log which columns we're using
    print(f"Using edge columns: spread={spread_edge_col}, ml={ml_edge_col}, over={over_edge_col}, under={under_edge_col}")

    # Spread bets
    spread_records = calculate_record(
        df, spread_edge_col, 'spread_covered', 'Spread'
    )
    all_records.extend(spread_records)

    # Moneyline bets
    ml_records = calculate_record(
        df, ml_edge_col, 'moneyline_won', 'Moneyline'
    )
    all_records.extend(ml_records)

    # Over bets
    over_records = calculate_record(
        df, over_edge_col, 'over_hit', 'Over'
    )
    all_records.extend(over_records)

    # Under bets
    under_records = calculate_record(
        df, under_edge_col, 'under_hit', 'Under'
    )
    all_records.extend(under_records)

    return pd.DataFrame(all_records)


def generate_markdown_report(record_df, graded_df):
    """Generate markdown report for GitHub Pages."""
    et = pytz.timezone('US/Eastern')
    now_et = datetime.now(et)

    # Get date range from graded results
    if len(graded_df) > 0:
        min_date = graded_df['date'].min()
        max_date = graded_df['date'].max()
        date_range = f"{min_date} to {max_date}"
    else:
        date_range = "No data"

    md = f"""# CBB Model Record

**Last Updated:** {now_et.strftime('%B %d, %Y at %I:%M %p ET')}

**Season Record Period:** {date_range}

**Total Games Graded:** {len(graded_df) // 2} games ({len(graded_df)} team-rows)

---

## Record by Opening Edge Tier

The opening edge is calculated when a game first appears in our system, comparing our model's predicted probability against the market's implied probability at that moment.

"""

    # Determine which columns to use
    spread_edge_col = 'opening_spread_edge' if 'opening_spread_edge' in graded_df.columns else 'spread_edge'
    ml_edge_col = 'opening_moneyline_edge' if 'opening_moneyline_edge' in graded_df.columns else 'moneyline_edge'
    over_edge_col = 'opening_over_edge' if 'opening_over_edge' in graded_df.columns else 'over_edge'
    under_edge_col = 'opening_under_edge' if 'opening_under_edge' in graded_df.columns else 'under_edge'

    # Generate tables for each bet type (All Bets and Consensus Only)
    bet_configs = [
        ('Spread', spread_edge_col, 'spread_covered', 'spread_consensus_flag'),
        ('Moneyline', ml_edge_col, 'moneyline_won', 'moneyline_consensus_flag'),
        ('Over', over_edge_col, 'over_hit', 'over_consensus_flag'),
        ('Under', under_edge_col, 'under_hit', 'under_consensus_flag'),
    ]
    
    for bet_type, edge_col, outcome_col, consensus_col in bet_configs:
        # All Bets section
        md += f"### {bet_type} Bets - All\n\n"
        all_records = calculate_record(graded_df, edge_col, outcome_col, bet_type)
        md += generate_bet_table(all_records)
        
        # Consensus Only section
        md += f"### {bet_type} Bets - Consensus Only\n\n"
        consensus_records = calculate_record(graded_df, edge_col, outcome_col, bet_type, consensus_col)
        md += generate_bet_table(consensus_records)

    # Individual Model Performance sections
    md += """---

## Individual Model Performance

Performance of each individual predictive model, calculated across all games regardless of edge.

"""

    # Spread models
    md += "### Individual Model Performance - Spread Bets\n\n"
    md += "| Model | Record | Win Rate | Profit (Units) |\n"
    md += "|-------|--------|----------|----------------|\n"
    
    spread_models = [
        ('KenPom', 'spread_covered_kenpom'),
        ('Bart Torvik', 'spread_covered_barttorvik'),
        ('Evan Miya', 'spread_covered_evanmiya'),
        ('Haslametrics', 'spread_covered_hasla'),
    ]
    
    for model_name, col in spread_models:
        if col in graded_df.columns:
            record = calculate_individual_model_record(graded_df, col, model_name)
            md += format_individual_model_row(record)
    
    md += "\n"
    
    # Moneyline models
    md += "### Individual Model Performance - Moneyline Bets\n\n"
    md += "| Model | Record | Win Rate | Profit (Units) |\n"
    md += "|-------|--------|----------|----------------|\n"
    
    ml_models = [
        ('KenPom', 'moneyline_won_kenpom'),
        ('Bart Torvik', 'moneyline_won_barttorvik'),
        ('Evan Miya', 'moneyline_won_evanmiya'),
    ]
    
    for model_name, col in ml_models:
        if col in graded_df.columns:
            record = calculate_individual_model_record(graded_df, col, model_name)
            md += format_individual_model_row(record)
    
    md += "\n"
    
    # Total models - Over
    md += "### Individual Model Performance - Over Bets\n\n"
    md += "| Model | Record | Win Rate | Profit (Units) |\n"
    md += "|-------|--------|----------|----------------|\n"
    
    over_models = [
        ('KenPom', 'over_hit_kenpom'),
        ('Bart Torvik', 'over_hit_barttorvik'),
        ('Evan Miya', 'over_hit_evanmiya'),
        ('Haslametrics', 'over_hit_hasla'),
    ]
    
    for model_name, col in over_models:
        if col in graded_df.columns:
            record = calculate_individual_model_record(graded_df, col, model_name)
            md += format_individual_model_row(record)
    
    md += "\n"
    
    # Total models - Under
    md += "### Individual Model Performance - Under Bets\n\n"
    md += "| Model | Record | Win Rate | Profit (Units) |\n"
    md += "|-------|--------|----------|----------------|\n"
    
    under_models = [
        ('KenPom', 'under_hit_kenpom'),
        ('Bart Torvik', 'under_hit_barttorvik'),
        ('Evan Miya', 'under_hit_evanmiya'),
        ('Haslametrics', 'under_hit_hasla'),
    ]
    
    for model_name, col in under_models:
        if col in graded_df.columns:
            record = calculate_individual_model_record(graded_df, col, model_name)
            md += format_individual_model_row(record)
    
    md += "\n"

    md += """---

## Methodology

- **Opening Edge**: The difference between our model's predicted probability and the market's implied probability when the game first appeared in our system
- **Consensus**: All individual models agree on the direction of the bet
- **Profit Calculation**: Assumes flat betting at -110 standard juice (+0.909 units per win, -1 unit per loss)
- **Edge Tiers**: Games are bucketed by their opening edge percentage
- **Individual Model Performance**: Each model's performance across all games, regardless of edge

## Notes

- This report updates automatically every 15 minutes
- Only completed games with valid opening edges are included
- Games without opening edge data (e.g., missing from initial scrape) are excluded from this report

"""

    return md


def generate_bet_table(records):
    """Generate markdown table for bet records."""
    md = "| Edge Tier | Record | Win Rate | Profit (Units) |\n"
    md += "|-----------|--------|----------|----------------|\n"
    
    total_wins = 0
    total_losses = 0
    total_profit = 0
    
    for record in records:
        wins = int(record['wins'])
        losses = int(record['losses'])
        total = int(record['total'])
        win_rate = f"{record['win_rate']*100:.1f}%" if pd.notna(record['win_rate']) else "N/A"
        profit = record['profit_units']
        profit_str = f"+{profit:.2f}" if profit >= 0 else f"{profit:.2f}"
        
        total_wins += wins
        total_losses += losses
        total_profit += profit
        
        md += f"| {record['edge_tier']} | {wins}-{losses} | {win_rate} | {profit_str} |\n"
    
    # Add totals row
    total_games = total_wins + total_losses
    total_win_rate = f"{total_wins/total_games*100:.1f}%" if total_games > 0 else "N/A"
    total_profit_str = f"+{total_profit:.2f}" if total_profit >= 0 else f"{total_profit:.2f}"
    md += f"| **Total** | **{total_wins}-{total_losses}** | **{total_win_rate}** | **{total_profit_str}** |\n"
    md += "\n"
    
    return md


def format_individual_model_row(record):
    """Format a single row for individual model performance table."""
    wins = int(record['wins'])
    losses = int(record['losses'])
    win_rate = f"{record['win_rate']*100:.1f}%" if pd.notna(record['win_rate']) and record['win_rate'] is not None else "N/A"
    profit = record['profit_units']
    profit_str = f"+{profit:.2f}" if profit >= 0 else f"{profit:.2f}"
    
    return f"| {record['model_name']} | {wins}-{losses} | {win_rate} | {profit_str} |\n"


def main():
    """Main function to generate model record reports."""
    print("=== Generating Model Record Report ===")

    # Load graded results
    df = load_graded_results()
    if df is None:
        print("No graded results to process")
        sys.exit(0)

    # Generate model record
    record_df = generate_model_record(df)

    # Save CSV
    record_df.to_csv(model_record_csv_path, index=False)
    print(f"Saved model record to {model_record_csv_path}")

    # Create docs directory if it doesn't exist
    os.makedirs(docs_dir, exist_ok=True)

    # Generate and save markdown report
    md_content = generate_markdown_report(record_df, df)
    with open(model_record_md_path, 'w') as f:
        f.write(md_content)
    print(f"Saved markdown report to {model_record_md_path}")

    # Print summary
    print("\n=== Model Record Summary ===")
    for bet_type in ['Spread', 'Moneyline', 'Over', 'Under']:
        type_df = record_df[record_df['bet_type'] == bet_type]
        total_wins = type_df['wins'].sum()
        total_losses = type_df['losses'].sum()
        total_profit = type_df['profit_units'].sum()
        print(f"{bet_type}: {total_wins}-{total_losses} ({total_profit:+.2f} units)")

    print("\n=== Report Generation Complete ===")


if __name__ == "__main__":
    main()
