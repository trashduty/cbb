# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pandas",
#     "numpy",
# ]
# ///
"""
Moneyline Edge Analysis: EM + BT Median Model

Analyzes moneyline betting opportunities using the median of Evanmiya and Barttorvik
win probabilities, compared against market odds to identify profitable betting opportunities.
"""

import pandas as pd
import numpy as np
from pathlib import Path


def moneyline_to_implied_prob(ml):
    """Convert American moneyline odds to implied probability."""
    if pd.isna(ml):
        return np.nan
    if ml > 0:
        return 100 / (ml + 100)
    else:
        return abs(ml) / (abs(ml) + 100)


def calculate_roi_metrics(row):
    """Calculate risk, profit, and ROI for a single bet based on American odds."""
    ml = row['opening_moneyline']
    won = row['moneyline_won']
    
    if pd.isna(ml):
        return pd.Series({'risk': np.nan, 'profit': np.nan})
    
    if ml < 0:
        # Favorite: risk |moneyline| to win $100
        risk = abs(ml)
        profit = 100 if won else -risk
    else:
        # Underdog: risk $100 to win moneyline
        risk = 100
        profit = ml if won else -risk
    
    return pd.Series({'risk': risk, 'profit': profit})


def get_prob_band(prob):
    """Assign win probability to a band."""
    if pd.isna(prob):
        return None
    if prob <= 0.10:
        return '0-10%'
    elif prob <= 0.20:
        return '11-20%'
    elif prob <= 0.30:
        return '21-30%'
    elif prob <= 0.40:
        return '31-40%'
    elif prob <= 0.50:
        return '41-50%'
    elif prob <= 0.60:
        return '51-60%'
    elif prob <= 0.70:
        return '61-70%'
    elif prob <= 0.80:
        return '71-80%'
    elif prob <= 0.90:
        return '81-90%'
    else:
        return '91-100%'


def analyze_edge_threshold(df, edge_threshold, edge_col='edge'):
    """Analyze performance for a specific edge threshold."""
    subset = df[df[edge_col] >= edge_threshold].copy()
    
    if len(subset) == 0:
        return None
    
    games = len(subset)
    wins = subset['moneyline_won'].sum()
    win_rate = wins / games * 100
    avg_pred_prob = subset['pred_win_prob'].mean() * 100  # Convert to percentage
    avg_market_prob = subset['moneyline_win_probability'].mean() * 100  # Convert to percentage
    avg_edge = subset[edge_col].mean() * 100  # Convert to percentage
    total_risk = subset['risk'].sum()
    total_profit = subset['profit'].sum()
    roi = (total_profit / total_risk * 100) if total_risk > 0 else 0
    
    return {
        'edge_threshold': f'{edge_threshold*100:.0f}%+',
        'games': games,
        'wins': int(wins),
        'win_rate': win_rate,
        'avg_pred_prob': avg_pred_prob,
        'avg_market_prob': avg_market_prob,
        'avg_edge': avg_edge,
        'total_risk': total_risk,
        'total_profit': total_profit,
        'roi': roi
    }


def analyze_by_prob_band(df, edge_threshold, edge_col='edge'):
    """Analyze performance by win probability band for a specific edge threshold."""
    subset = df[df[edge_col] >= edge_threshold].copy()
    
    if len(subset) == 0:
        return []
    
    # Define band order
    band_order = ['0-10%', '11-20%', '21-30%', '31-40%', '41-50%', 
                  '51-60%', '61-70%', '71-80%', '81-90%', '91-100%']
    
    results = []
    for band in band_order:
        band_df = subset[subset['prob_band'] == band]
        
        if len(band_df) == 0:
            continue
        
        games = len(band_df)
        wins = band_df['moneyline_won'].sum()
        win_rate = wins / games * 100
        avg_pred_prob = band_df['pred_win_prob'].mean() * 100  # Convert to percentage
        avg_edge = band_df[edge_col].mean() * 100  # Convert to percentage
        total_risk = band_df['risk'].sum()
        total_profit = band_df['profit'].sum()
        roi = (total_profit / total_risk * 100) if total_risk > 0 else 0
        
        # Determine verdict
        if games < 5:
            verdict = 'Small N'
        elif roi > 15:
            verdict = '✅ BET'
        elif roi > 0:
            verdict = 'Marginal'
        else:
            verdict = '❌ AVOID'
        
        results.append({
            'band': band,
            'games': games,
            'wins': int(wins),
            'win_rate': win_rate,
            'avg_pred_prob': avg_pred_prob,
            'avg_edge': avg_edge,
            'roi': roi,
            'verdict': verdict
        })
    
    return results


def format_table(data, columns):
    """Format data as a markdown table."""
    if not data:
        return "No data available\n"
    
    # Create header
    lines = []
    lines.append('| ' + ' | '.join(columns) + ' |')
    lines.append('|' + '|'.join(['-------' for _ in columns]) + '|')
    
    # Add rows
    for row in data:
        formatted_row = []
        for col in columns:
            key = col.lower().replace(' ', '_')
            value = row.get(key, '')
            
            # Format based on type
            if isinstance(value, float):
                if 'prob' in key or 'edge' in key or 'rate' in key:
                    # These are already in percentage form (0-100), just format
                    formatted_row.append(f'{value:.2f}%')
                elif 'roi' in key:
                    sign = '+' if value >= 0 else ''
                    formatted_row.append(f'{sign}{value:.1f}%')
                else:
                    formatted_row.append(f'{value:.2f}')
            elif isinstance(value, int):
                formatted_row.append(str(value))
            else:
                formatted_row.append(str(value))
        
        lines.append('| ' + ' | '.join(formatted_row) + ' |')
    
    return '\n'.join(lines) + '\n'


def generate_markdown_report(overall_results, band_results, output_path):
    """Generate comprehensive markdown report."""
    
    with open(output_path, 'w') as f:
        f.write('# Moneyline Edge Analysis: EM + BT Median Model\n\n')
        f.write('**Model Combination: Median of Evanmiya and Barttorvik Win Probabilities**\n\n')
        
        # TL;DR section with key thresholds
        f.write('## TL;DR\n\n')
        tldr_data = [r for r in overall_results if r['edge_threshold'] in ['2%+', '3%+', '4%+']]
        if tldr_data:
            tldr_table = format_table(
                tldr_data,
                ['Edge Threshold', 'ROI', 'Games']
            )
            f.write(tldr_table)
        
        f.write('\n---\n\n')
        
        # Overall performance section
        f.write('## Overall Performance by Edge Threshold\n\n')
        overall_table = format_table(
            overall_results,
            ['Edge Threshold', 'Games', 'Wins', 'Win Rate', 'Avg Pred Prob', 
             'Avg Market Prob', 'Avg Edge', 'Total Risk', 'Total Profit', 'ROI']
        )
        f.write(overall_table)
        
        f.write('\n---\n\n')
        
        # Performance by win probability band
        f.write('## Performance by Win Probability Band\n\n')
        
        for edge_threshold in [0.00, 0.01, 0.02, 0.03, 0.04]:
            edge_label = f'{edge_threshold*100:.0f}%+'
            f.write(f'### Edge >= {edge_threshold*100:.0f}%\n\n')
            
            bands = band_results.get(edge_threshold, [])
            if bands:
                band_table = format_table(
                    bands,
                    ['Band', 'Games', 'Wins', 'Win Rate', 'Avg Pred Prob', 'Avg Edge', 'ROI', 'Verdict']
                )
                f.write(band_table)
            else:
                f.write('No data available\n')
            
            f.write('\n')
        
        f.write('---\n\n')
        
        # Key Insights
        f.write('## Key Insights\n\n')
        
        # Find best ROI
        best_overall = max(overall_results, key=lambda x: x['roi'])
        f.write(f"- **Best Overall ROI**: {best_overall['roi']:+.1f}% at {best_overall['edge_threshold']} edge ({best_overall['games']} games)\n")
        
        # Find most profitable bands at 2%+ edge
        bands_2pct = band_results.get(0.02, [])
        if bands_2pct:
            profitable_bands = [b for b in bands_2pct if b['roi'] > 15 and b['games'] >= 5]
            if profitable_bands:
                best_band = max(profitable_bands, key=lambda x: x['roi'])
                f.write(f"- **Most Profitable Band (2%+ edge)**: {best_band['band']} (ROI: {best_band['roi']:+.1f}%, {best_band['games']} games)\n")
            
            avoid_bands = [b for b in bands_2pct if b['roi'] < 0 and b['games'] >= 5]
            if avoid_bands:
                f.write(f"- **Bands to Avoid (2%+ edge)**: {', '.join([b['band'] for b in avoid_bands])}\n")
        
        f.write('\n')
        
        # Recommended betting strategy
        f.write('## Recommended Betting Strategy\n\n')
        
        for edge_threshold in [0.02, 0.03, 0.04]:
            edge_label = f'{edge_threshold*100:.0f}%+'
            f.write(f'### For {edge_label} Edge:\n\n')
            
            bands = band_results.get(edge_threshold, [])
            bet_bands = [b for b in bands if b['roi'] > 0 and b['games'] >= 5]
            avoid_bands = [b for b in bands if b['roi'] < 0 and b['games'] >= 5]
            
            if bet_bands:
                f.write(f"- **✅ BET**: {', '.join([b['band'] for b in bet_bands])}\n")
            if avoid_bands:
                f.write(f"- **❌ AVOID**: {', '.join([b['band'] for b in avoid_bands])}\n")
            
            f.write('\n')
        
        f.write('---\n\n')
        
        # Comparison to KP+BT model
        f.write('## Comparison to KP+BT Model\n\n')
        f.write('To compare with the KP+BT model analysis, refer to `moneyline_analysis.md`.\n\n')
        f.write('**Key Differences:**\n')
        f.write('- This analysis uses the **median** of EM and BT win probabilities\n')
        f.write('- KP+BT analysis uses the **average** of KP and BT win probabilities\n')
        f.write('- Sample sizes and date ranges may differ\n\n')
        
        # Methodology
        f.write('---\n\n')
        f.write('## Methodology\n\n')
        f.write('- **Predicted Win Probability**: Median of Evanmiya and Barttorvik win probabilities\n')
        f.write('- **Market Win Probability**: Derived from opening moneyline odds\n')
        f.write('- **Edge**: pred_win_prob - market_win_prob\n')
        f.write('- **ROI Calculation**:\n')
        f.write('  - For favorites (negative odds): Risk = |moneyline|, Win = $100\n')
        f.write('  - For underdogs (positive odds): Risk = $100, Win = moneyline\n')
        f.write('  - ROI = Total Profit / Total Risk × 100%\n')
        f.write('- **Probability Bands**: 10% buckets from 0-10% to 91-100%\n')
        f.write('- **Data Source**: graded_results.csv (filtered to one row per game)\n')


def main():
    """Main execution function."""
    base_path = Path(__file__).parent.parent.parent
    
    print("Loading data...")
    df = pd.read_csv(base_path / 'graded_results.csv')
    
    print(f"Total rows in graded_results.csv: {len(df)}")
    
    # Filter to one row per game (home team only) to avoid double-counting
    df = df[df['team'] == df['home_team']].copy()
    print(f"Rows after filtering to home team only: {len(df)}")
    
    # Filter to games with required data
    required_cols = ['win_prob_barttorvik', 'win_prob_evanmiya', 'opening_moneyline', 'moneyline_won']
    df = df[df[required_cols].notna().all(axis=1)].copy()
    print(f"Rows with complete EM+BT+moneyline data: {len(df)}")
    
    # Calculate predicted win probability as median of EM and BT
    df['pred_win_prob'] = df[['win_prob_barttorvik', 'win_prob_evanmiya']].median(axis=1)
    
    # Calculate market win probability from opening moneyline
    df['moneyline_win_probability'] = df['opening_moneyline'].apply(moneyline_to_implied_prob)
    
    # Calculate edge
    df['edge'] = df['pred_win_prob'] - df['moneyline_win_probability']
    
    # Calculate risk and profit for each bet
    roi_metrics = df.apply(calculate_roi_metrics, axis=1)
    df['risk'] = roi_metrics['risk']
    df['profit'] = roi_metrics['profit']
    
    # Assign probability band
    df['prob_band'] = df['moneyline_win_probability'].apply(get_prob_band)
    
    print(f"\nCalculated metrics for {len(df)} games")
    print(f"Average edge: {df['edge'].mean():.4f}")
    print(f"Games with 2%+ edge: {(df['edge'] >= 0.02).sum()}")
    print(f"Games with 3%+ edge: {(df['edge'] >= 0.03).sum()}")
    print(f"Games with 4%+ edge: {(df['edge'] >= 0.04).sum()}")
    
    # Export detailed results
    output_cols = [
        'date', 'team', 'moneyline_win_probability', 'win_prob_barttorvik', 
        'win_prob_evanmiya', 'pred_win_prob', 'edge', 'opening_moneyline', 
        'moneyline_won', 'risk', 'profit', 'prob_band'
    ]
    
    data_output_path = base_path / 'analysis' / 'data' / 'em_bt_moneyline_results.csv'
    df[output_cols].to_csv(data_output_path, index=False)
    print(f"\n✓ Detailed results saved to: {data_output_path}")
    
    # Analyze overall performance by edge threshold
    print("\n" + "="*80)
    print("OVERALL PERFORMANCE BY EDGE THRESHOLD")
    print("="*80)
    
    edge_thresholds = [0.00, 0.01, 0.02, 0.03, 0.04]
    overall_results = []
    
    for threshold in edge_thresholds:
        result = analyze_edge_threshold(df, threshold)
        if result:
            overall_results.append(result)
            print(f"\nEdge >= {threshold*100:.0f}%:")
            print(f"  Games: {result['games']}")
            print(f"  Wins: {result['wins']} ({result['win_rate']:.1f}%)")
            print(f"  Avg Edge: {result['avg_edge']*100:.2f}%")
            print(f"  ROI: {result['roi']:+.1f}%")
    
    # Analyze by probability band for each threshold
    print("\n" + "="*80)
    print("PERFORMANCE BY WIN PROBABILITY BAND")
    print("="*80)
    
    band_results = {}
    for threshold in edge_thresholds:
        bands = analyze_by_prob_band(df, threshold)
        band_results[threshold] = bands
        
        if bands:
            print(f"\n--- Edge >= {threshold*100:.0f}% ---")
            for band in bands:
                print(f"  {band['band']:12s}: {band['games']:3d} games, "
                      f"{band['wins']:3d} wins ({band['win_rate']:5.1f}%), "
                      f"ROI: {band['roi']:+6.1f}% - {band['verdict']}")
    
    # Generate markdown report
    report_path = base_path / 'analysis' / 'reports' / 'em_bt_moneyline_analysis.md'
    generate_markdown_report(overall_results, band_results, report_path)
    print(f"\n✓ Markdown report saved to: {report_path}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
