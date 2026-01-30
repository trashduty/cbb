# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///
"""
ROI Analysis for KP+BT+HA Totals Betting Model Ensemble.

Analyzes betting performance using the median prediction from three models:
- KenPom (KP)
- Bart Torvik (BT)
- Haslametrics (HA)

Stratifies results by edge thresholds, bet type (Over/Under), and consensus.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def calculate_median_and_consensus(df):
    """
    Calculate median prediction and consensus flag for each game.
    
    Args:
        df: DataFrame with model predictions and opening totals
    
    Returns:
        DataFrame with added columns:
        - median_total: median of KP, BT, HA projections
        - bet_direction: 'Over' or 'Under' (None if median == opening_total, no bet)
        - consensus: 'Yes' if all 3 models agree on direction, 'No' otherwise
    """
    # Model columns
    kp_col = 'projected_total_kenpom'
    bt_col = 'projected_total_barttorvik'
    ha_col = 'projected_total_hasla'
    
    # Calculate median
    df['median_total'] = df[[kp_col, bt_col, ha_col]].median(axis=1)
    
    # Determine bet direction
    df['bet_direction'] = None
    df.loc[df['median_total'] > df['opening_total'], 'bet_direction'] = 'Over'
    df.loc[df['median_total'] < df['opening_total'], 'bet_direction'] = 'Under'
    
    # Determine consensus
    # For Over bets: all 3 models > opening_total
    # For Under bets: all 3 models < opening_total
    df['consensus'] = 'No'
    
    # Over consensus
    over_mask = df['bet_direction'] == 'Over'
    all_over = (df[kp_col] > df['opening_total']) & \
               (df[bt_col] > df['opening_total']) & \
               (df[ha_col] > df['opening_total'])
    df.loc[over_mask & all_over, 'consensus'] = 'Yes'
    
    # Under consensus
    under_mask = df['bet_direction'] == 'Under'
    all_under = (df[kp_col] < df['opening_total']) & \
                (df[bt_col] < df['opening_total']) & \
                (df[ha_col] < df['opening_total'])
    df.loc[under_mask & all_under, 'consensus'] = 'Yes'
    
    return df


def calculate_roi_metrics(bets_df, edge_thresholds):
    """
    Calculate ROI metrics for different stratifications.
    
    Args:
        bets_df: DataFrame with bet data
        edge_thresholds: List of edge thresholds to analyze (as decimals, e.g., 0.02 for 2%)
    
    Returns:
        List of dicts with results for each combination
    """
    results = []
    
    # -110 odds: risk 1.1 to win 1.0
    WIN_PAYOUT = 1.0  # Net profit on a winning bet
    LOSS_AMOUNT = -1.1  # Net loss on a losing bet
    
    for bet_type in ['Over', 'Under']:
        for consensus in ['Yes', 'No']:
            for edge_threshold in edge_thresholds:
                # Filter to this bet type and consensus
                subset = bets_df[
                    (bets_df['bet_direction'] == bet_type) &
                    (bets_df['consensus'] == consensus)
                ].copy()
                
                if len(subset) == 0:
                    continue
                
                # Filter by edge threshold
                # Note: edges should be positive values representing favorable bets
                edge_col = 'opening_over_edge' if bet_type == 'Over' else 'opening_under_edge'
                subset = subset[subset[edge_col] >= edge_threshold]
                
                if len(subset) == 0:
                    continue
                
                # Determine wins and losses
                if bet_type == 'Over':
                    wins = subset['over_hit'].sum()
                else:
                    wins = subset['under_hit'].sum()
                
                num_bets = len(subset)
                losses = num_bets - wins
                win_rate = (wins / num_bets * 100) if num_bets > 0 else 0
                
                # Calculate profit/loss
                total_profit = (wins * WIN_PAYOUT) + (losses * LOSS_AMOUNT)
                total_wagered = num_bets * 1.1
                roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0
                
                results.append({
                    'bet_type': bet_type,
                    'consensus': consensus,
                    'edge_threshold': f'{edge_threshold * 100:.0f}%',
                    'num_bets': num_bets,
                    'wins': wins,
                    'losses': losses,
                    'win_rate': win_rate,
                    'total_profit': total_profit,
                    'total_wagered': total_wagered,
                    'roi': roi
                })
    
    return results


def main():
    # Determine base path relative to script location
    base_path = Path(__file__).parent.parent.parent
    
    # Load data
    print("Loading graded_results.csv...")
    df = pd.read_csv(base_path / 'graded_results.csv')
    
    # Calculate actual total
    df['actual_total'] = df['home_score'] + df['away_score']
    
    # Filter to completed games only
    df = df[df['game_completed'] == True].copy()
    print(f"Total completed games: {len(df)}")
    
    # Filter to one row per game (home team rows only) to avoid double counting
    df_home = df[df['team'] == df['home_team']].copy()
    print(f"Unique games (home team rows): {len(df_home)}")
    
    # Filter to games with all required data
    required_cols = [
        'projected_total_kenpom',
        'projected_total_barttorvik', 
        'projected_total_hasla',
        'opening_total',
        'opening_over_edge',
        'opening_under_edge',
        'over_hit',
        'under_hit'
    ]
    
    mask = df_home[required_cols].notna().all(axis=1)
    df_clean = df_home[mask].copy()
    print(f"Games with all required data (KP, BT, HA, opening_total, edges): {len(df_clean)}")
    
    # Calculate median and consensus
    print("\nCalculating median predictions and consensus flags...")
    df_clean = calculate_median_and_consensus(df_clean)
    
    # Filter to games where we have a bet (median != opening_total)
    df_bets = df_clean[df_clean['bet_direction'].notna()].copy()
    print(f"Games with bets (median != opening_total): {len(df_bets)}")
    
    # Summary stats
    print(f"\nBet distribution:")
    print(f"  Over bets: {(df_bets['bet_direction'] == 'Over').sum()}")
    print(f"  Under bets: {(df_bets['bet_direction'] == 'Under').sum()}")
    print(f"\nConsensus distribution:")
    print(f"  Consensus Yes: {(df_bets['consensus'] == 'Yes').sum()}")
    print(f"  Consensus No: {(df_bets['consensus'] == 'No').sum()}")
    
    # Define edge thresholds
    edge_thresholds = [0.00, 0.01, 0.02, 0.03, 0.04]
    
    # Calculate ROI metrics
    print("\nCalculating ROI metrics...")
    results = calculate_roi_metrics(df_bets, edge_thresholds)
    
    # Convert to DataFrame for easier display
    results_df = pd.DataFrame(results)
    
    # Display results
    print("\n" + "=" * 100)
    print("ROI ANALYSIS RESULTS")
    print("=" * 100)
    print(results_df.to_string(index=False))
    
    # Save CSV to root directory
    csv_file = base_path / 'roi_analysis_kp_bt_ha.csv'
    results_df.to_csv(csv_file, index=False)
    print(f"\n✓ Results saved to: {csv_file}")
    
    # Generate markdown report in root directory
    md_file = base_path / 'roi_analysis_report.md'
    with open(md_file, 'w') as f:
        f.write("# ROI Analysis: KP+BT+HA Totals Betting Model Ensemble\n\n")
        f.write("## Executive Summary\n\n")
        f.write(f"This analysis evaluates betting performance using the **median prediction** from three models:\n")
        f.write(f"- **KenPom (KP)**\n")
        f.write(f"- **Bart Torvik (BT)**\n")
        f.write(f"- **Haslametrics (HA)**\n\n")
        
        f.write(f"### Data Overview\n\n")
        f.write(f"- Total games analyzed: **{len(df_bets)}**\n")
        f.write(f"- Over bets: **{(df_bets['bet_direction'] == 'Over').sum()}**\n")
        f.write(f"- Under bets: **{(df_bets['bet_direction'] == 'Under').sum()}**\n")
        f.write(f"- Consensus bets (all 3 models agree): **{(df_bets['consensus'] == 'Yes').sum()}**\n")
        f.write(f"- Non-consensus bets: **{(df_bets['consensus'] == 'No').sum()}**\n\n")
        
        f.write("### Betting Assumptions\n\n")
        f.write("- **Odds**: -110 (American odds)\n")
        f.write("- **Breakeven win rate**: 52.38%\n")
        f.write("- **Win payout**: +1.0 units (risk 1.1 to win 1.0)\n")
        f.write("- **Loss**: -1.1 units\n\n")
        
        f.write("## Complete Results\n\n")
        f.write("Results stratified by bet type, consensus, and edge threshold:\n\n")
        
        # Format table
        f.write("| Bet Type | Consensus | Edge Threshold | # Bets | Wins | Losses | Win Rate | Total Profit | Total Wagered | ROI |\n")
        f.write("|----------|-----------|----------------|--------|------|--------|----------|--------------|---------------|-----|\n")
        
        for _, row in results_df.iterrows():
            f.write(f"| {row['bet_type']} | {row['consensus']} | {row['edge_threshold']} | "
                   f"{row['num_bets']} | {row['wins']} | {row['losses']} | "
                   f"{row['win_rate']:.2f}% | {row['total_profit']:.2f} | "
                   f"{row['total_wagered']:.2f} | {row['roi']:.2f}% |\n")
        
        f.write("\n## Key Insights\n\n")
        
        # Find best performing strategies
        best_roi = results_df.loc[results_df['roi'].idxmax()]
        worst_roi = results_df.loc[results_df['roi'].idxmin()]
        
        f.write(f"### Best Performing Strategy\n\n")
        f.write(f"- **Bet Type**: {best_roi['bet_type']}\n")
        f.write(f"- **Consensus**: {best_roi['consensus']}\n")
        f.write(f"- **Edge Threshold**: {best_roi['edge_threshold']}\n")
        f.write(f"- **ROI**: {best_roi['roi']:.2f}%\n")
        f.write(f"- **Win Rate**: {best_roi['win_rate']:.2f}%\n")
        f.write(f"- **Number of Bets**: {best_roi['num_bets']}\n\n")
        
        f.write(f"### Worst Performing Strategy\n\n")
        f.write(f"- **Bet Type**: {worst_roi['bet_type']}\n")
        f.write(f"- **Consensus**: {worst_roi['consensus']}\n")
        f.write(f"- **Edge Threshold**: {worst_roi['edge_threshold']}\n")
        f.write(f"- **ROI**: {worst_roi['roi']:.2f}%\n")
        f.write(f"- **Win Rate**: {worst_roi['win_rate']:.2f}%\n")
        f.write(f"- **Number of Bets**: {worst_roi['num_bets']}\n\n")
        
        # Analyze by edge threshold
        f.write("### Edge Threshold Impact\n\n")
        for edge in edge_thresholds:
            edge_str = f'{edge * 100:.0f}%'
            edge_data = results_df[results_df['edge_threshold'] == edge_str]
            if len(edge_data) > 0:
                avg_roi = edge_data['roi'].mean()
                total_bets = edge_data['num_bets'].sum()
                f.write(f"- **{edge_str} edge**: Avg ROI = {avg_roi:.2f}%, Total bets = {total_bets}\n")
        
        # Analyze consensus vs non-consensus
        f.write("\n### Consensus Impact\n\n")
        consensus_yes = results_df[results_df['consensus'] == 'Yes']
        consensus_no = results_df[results_df['consensus'] == 'No']
        
        if len(consensus_yes) > 0:
            f.write(f"- **Consensus bets**: Avg ROI = {consensus_yes['roi'].mean():.2f}%, "
                   f"Total bets = {consensus_yes['num_bets'].sum()}\n")
        if len(consensus_no) > 0:
            f.write(f"- **Non-consensus bets**: Avg ROI = {consensus_no['roi'].mean():.2f}%, "
                   f"Total bets = {consensus_no['num_bets'].sum()}\n")
        
        # Analyze Over vs Under
        f.write("\n### Over vs Under Performance\n\n")
        over_bets = results_df[results_df['bet_type'] == 'Over']
        under_bets = results_df[results_df['bet_type'] == 'Under']
        
        if len(over_bets) > 0:
            f.write(f"- **Over bets**: Avg ROI = {over_bets['roi'].mean():.2f}%, "
                   f"Total bets = {over_bets['num_bets'].sum()}\n")
        if len(under_bets) > 0:
            f.write(f"- **Under bets**: Avg ROI = {under_bets['roi'].mean():.2f}%, "
                   f"Total bets = {under_bets['num_bets'].sum()}\n")
        
        f.write("\n## Methodology\n\n")
        f.write("1. **Median Calculation**: For each game, calculate the median of KP, BT, and HA projections\n")
        f.write("2. **Bet Direction**: \n")
        f.write("   - Over bet: median > opening_total\n")
        f.write("   - Under bet: median < opening_total\n")
        f.write("3. **Consensus Flag**:\n")
        f.write("   - Yes: All three models agree on direction\n")
        f.write("   - No: Models disagree on direction\n")
        f.write("4. **Edge Thresholds**: Filter bets by minimum edge (0%, 1%, 2%, 3%, 4%)\n")
        f.write("5. **ROI Calculation**: (Total Profit / Total Wagered) × 100\n\n")
        
        f.write("## Data Quality Notes\n\n")
        f.write("- Only includes completed games\n")
        f.write("- Excludes games with missing model predictions or opening totals\n")
        f.write("- Uses `over_hit` and `under_hit` columns to grade bets\n")
        f.write("- Edges from `opening_over_edge` and `opening_under_edge` columns\n")
    
    print(f"✓ Markdown report saved to: {md_file}")
    
    print("\n" + "=" * 100)
    print("Analysis complete!")
    print("=" * 100)


if __name__ == '__main__':
    main()
