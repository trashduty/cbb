# /// script
# dependencies = [
#   "pandas",
#   "numpy"
# ]
# ///
"""
Grade individual model predictions (Kenpom, Barttorvik, Evan Miya, Hasla).

This script:
1. Reads CBB_Output.csv (individual model predictions) and graded_results.csv (actual outcomes)
2. Matches predictions to outcomes on: game, team, and date
3. Grades each model individually for spreads, moneylines, and totals
4. Outputs:
   - individual_model_grades.csv (summary statistics per model)
   - individual_model_game_results.csv (game-by-game details)
   - model_performance_summary.md (human-readable report)
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

# Input files
cbb_output_path = os.path.join(project_root, 'CBB_Output.csv')
graded_results_path = os.path.join(project_root, 'graded_results.csv')

# Output files
individual_grades_path = os.path.join(project_root, 'individual_model_grades.csv')
game_results_path = os.path.join(project_root, 'individual_model_game_results.csv')
summary_report_path = os.path.join(project_root, 'model_performance_summary.md')

# Model definitions
MODELS = {
    'barttorvik': {
        'spread_col': 'spread_barttorvik',
        'win_prob_col': 'win_prob_barttorvik',
        'total_col': 'projected_total_barttorvik',
        'name': 'Barttorvik'
    },
    'kenpom': {
        'spread_col': 'spread_kenpom',
        'win_prob_col': 'win_prob_kenpom',
        'total_col': 'projected_total_kenpom',
        'name': 'Kenpom'
    },
    'evanmiya': {
        'spread_col': 'spread_evanmiya',
        'win_prob_col': 'win_prob_evanmiya',
        'total_col': 'projected_total_evanmiya',
        'name': 'Evan Miya'
    },
    'hasla': {
        'spread_col': 'spread_hasla',
        'win_prob_col': None,  # Hasla doesn't have win probability
        'total_col': 'projected_total_hasla',
        'name': 'Hasla'
    }
}


def parse_game_date(game_time_str):
    """
    Parse game date from 'Game Time' column format: "Dec 16 06:00PM ET"
    
    Args:
        game_time_str (str): Game time string
        
    Returns:
        str: Date in YYYY-MM-DD format or None if parsing fails
    """
    if pd.isna(game_time_str):
        return None
    
    try:
        # Extract date part (e.g., "Dec 16")
        parts = game_time_str.split()
        if len(parts) >= 2:
            month_str = parts[0]
            day_str = parts[1]
            
            # Use current year (2025 for this season)
            year = 2025
            date_str = f"{month_str} {day_str} {year}"
            dt = datetime.strptime(date_str, "%b %d %Y")
            return dt.strftime("%Y-%m-%d")
    except Exception as e:
        logger.warning(f"Failed to parse date from '{game_time_str}': {e}")
    
    return None


def load_data():
    """
    Load historical predictions and graded_results.csv.
    
    Returns:
        tuple: (predictions_df, outcomes_df) or (None, None) on error
    """
    try:
        # Load all historical prediction files
        historical_dir = os.path.join(project_root, 'historical_data')
        logger.info(f"Loading predictions from {historical_dir}")
        
        all_predictions = []
        for filename in sorted(os.listdir(historical_dir)):
            if filename.endswith('_output.csv'):
                filepath = os.path.join(historical_dir, filename)
                try:
                    df = pd.read_csv(filepath)
                    # Extract date from filename (format: YYYY-MM-DD_output.csv)
                    date_str = filename.replace('_output.csv', '')
                    df['file_date'] = date_str
                    all_predictions.append(df)
                    logger.debug(f"Loaded {len(df)} rows from {filename}")
                except Exception as e:
                    logger.warning(f"Failed to load {filename}: {e}")
                    continue
        
        if not all_predictions:
            logger.error("No historical prediction files found")
            return None, None
        
        predictions_df = pd.concat(all_predictions, ignore_index=True)
        logger.info(f"Loaded {len(predictions_df)} total prediction rows from {len(all_predictions)} files")
        
        logger.info(f"Loading outcomes from {graded_results_path}")
        outcomes_df = pd.read_csv(graded_results_path)
        # Filter for completed games only
        outcomes_df = outcomes_df[outcomes_df['game_completed'] == True].copy()
        logger.info(f"Loaded {len(outcomes_df)} completed game outcome rows")
        
        return predictions_df, outcomes_df
        
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return None, None


def parse_game_teams(game_str):
    """
    Parse game string to extract home and away teams.
    Format: "Away Team vs. Home Team"
    
    Args:
        game_str (str): Game string
        
    Returns:
        tuple: (home_team, away_team) or (None, None) if parsing fails
    """
    if pd.isna(game_str):
        return None, None
    
    parts = game_str.split(' vs. ')
    if len(parts) == 2:
        return parts[1], parts[0]  # home, away
    
    return None, None


def match_predictions_to_outcomes(predictions_df, outcomes_df):
    """
    Match predictions to outcomes on game, team, and date.
    
    Args:
        predictions_df (pd.DataFrame): Predictions data
        outcomes_df (pd.DataFrame): Outcomes data
        
    Returns:
        pd.DataFrame: Merged dataframe with predictions and outcomes
    """
    logger.info("Preparing predictions data...")
    
    # Normalize column names (historical files use capital letters)
    predictions_df = predictions_df.rename(columns={
        'Game': 'game',
        'Team': 'team',
        'Game Time': 'game_time'
    })
    
    # Use file_date as the date (this is when the prediction was made)
    predictions_df['date'] = predictions_df['file_date']
    
    # Parse home and away teams from game column if not already present
    if 'Home Team' not in predictions_df.columns:
        predictions_df[['home_team_pred', 'away_team_pred']] = predictions_df['game'].apply(
            lambda x: pd.Series(parse_game_teams(x))
        )
    
    logger.info(f"Predictions with valid dates: {predictions_df['date'].notna().sum()}")
    logger.info(f"Date range in predictions: {predictions_df['date'].min()} to {predictions_df['date'].max()}")
    logger.info(f"Date range in outcomes: {outcomes_df['date'].min()} to {outcomes_df['date'].max()}")
    
    # Merge on date, game, and team
    logger.info("Merging predictions with outcomes...")
    merged = predictions_df.merge(
        outcomes_df,
        on=['date', 'game', 'team'],
        how='inner',
        suffixes=('_pred', '_outcome')
    )
    
    logger.info(f"Successfully matched {len(merged)} prediction rows with outcomes")
    
    return merged


def grade_spread(predicted_spread, actual_spread):
    """
    Grade a spread prediction.
    
    Args:
        predicted_spread (float): Predicted spread from model
        actual_spread (float): Actual margin (from team's perspective)
        
    Returns:
        dict: {'spread_correct': bool, 'spread_error': float}
    """
    if pd.isna(predicted_spread) or pd.isna(actual_spread):
        return {'spread_correct': None, 'spread_error': None}
    
    # Spread is covered if: actual_margin + predicted_spread > 0
    # This means the team beat the spread
    spread_correct = (actual_spread + predicted_spread) > 0
    
    # Error is the difference between predicted and actual
    spread_error = abs(predicted_spread - actual_spread)
    
    return {
        'spread_correct': spread_correct,
        'spread_error': spread_error
    }


def grade_moneyline(win_probability, actual_win):
    """
    Grade a moneyline prediction.
    
    Args:
        win_probability (float): Predicted win probability (0-1)
        actual_win (bool): Whether team actually won
        
    Returns:
        dict: {'win_correct': bool, 'brier_score': float, 'log_loss': float}
    """
    if pd.isna(win_probability) or pd.isna(actual_win):
        return {'win_correct': None, 'brier_score': None, 'log_loss': None}
    
    # Predicted winner is team with win_prob > 0.5
    predicted_win = win_probability > 0.5
    win_correct = (predicted_win == actual_win)
    
    # Brier score: (predicted_prob - actual_outcome)^2
    actual_outcome = 1.0 if actual_win else 0.0
    brier_score = (win_probability - actual_outcome) ** 2
    
    # Log loss: -[actual * log(pred) + (1-actual) * log(1-pred)]
    # Add small epsilon to avoid log(0)
    epsilon = 1e-15
    win_prob_clipped = np.clip(win_probability, epsilon, 1 - epsilon)
    log_loss = -(actual_outcome * np.log(win_prob_clipped) + 
                 (1 - actual_outcome) * np.log(1 - win_prob_clipped))
    
    return {
        'win_correct': win_correct,
        'brier_score': brier_score,
        'log_loss': log_loss
    }


def grade_total(predicted_total, actual_total):
    """
    Grade a total prediction.
    
    Args:
        predicted_total (float): Predicted total points
        actual_total (int): Actual total points
        
    Returns:
        dict: {'over_under_correct': bool, 'total_error': float}
    """
    if pd.isna(predicted_total) or pd.isna(actual_total):
        return {'over_under_correct': None, 'total_error': None}
    
    # Determine if predicted over/under was correct
    # If predicted > actual, model predicted "over"
    # If predicted < actual, model predicted "under"
    predicted_over = predicted_total > actual_total
    
    # This is a bit tricky - we consider the prediction correct if it's on the right side
    # For simplicity, we'll just track if the prediction was above or below actual
    # A better metric is just the absolute error
    
    # Actually, let's grade it as: did the model correctly predict whether the actual
    # total would be over or under some market line?
    # Since we don't have a "market total" here for each model, we'll just compute error
    
    total_error = abs(predicted_total - actual_total)
    
    # For over/under correctness, we can't really determine without a market line
    # So we'll leave this as None for now and just focus on error metrics
    
    return {
        'over_under_correct': None,  # Can't determine without market line
        'total_error': total_error
    }


def calculate_actual_margin(row):
    """
    Calculate actual margin from team's perspective.
    
    Args:
        row (pd.Series): Row with home_score, away_score, team, home_team
        
    Returns:
        float: Actual margin from team's perspective
    """
    is_home = row['team'] == row['home_team']
    
    if is_home:
        return row['home_score'] - row['away_score']
    else:
        return row['away_score'] - row['home_score']


def calculate_actual_win(row):
    """
    Calculate if team won.
    
    Args:
        row (pd.Series): Row with home_score, away_score, team, home_team
        
    Returns:
        bool: True if team won
    """
    is_home = row['team'] == row['home_team']
    
    if is_home:
        return row['home_score'] > row['away_score']
    else:
        return row['away_score'] > row['home_score']


def grade_all_models(merged_df):
    """
    Grade all models for all prediction types.
    
    Args:
        merged_df (pd.DataFrame): Merged predictions and outcomes
        
    Returns:
        tuple: (game_results_list, model_summaries_dict)
    """
    logger.info("Calculating actual margins and wins...")
    
    # Calculate actual outcomes
    merged_df['actual_margin'] = merged_df.apply(calculate_actual_margin, axis=1)
    merged_df['actual_win'] = merged_df.apply(calculate_actual_win, axis=1)
    merged_df['actual_total'] = merged_df['home_score'] + merged_df['away_score']
    
    game_results = []
    
    logger.info("Grading individual model predictions...")
    
    for idx, row in merged_df.iterrows():
        for model_key, model_info in MODELS.items():
            # Grade spread
            predicted_spread = row.get(model_info['spread_col'])
            spread_results = grade_spread(predicted_spread, row['actual_margin'])
            
            # Grade moneyline (if model has win probability)
            if model_info['win_prob_col']:
                win_prob = row.get(model_info['win_prob_col'])
                moneyline_results = grade_moneyline(win_prob, row['actual_win'])
            else:
                moneyline_results = {'win_correct': None, 'brier_score': None, 'log_loss': None}
            
            # Grade total
            predicted_total = row.get(model_info['total_col'])
            total_results = grade_total(predicted_total, row['actual_total'])
            
            # Compile game result
            game_result = {
                'date': row['date'],
                'game': row['game'],
                'team': row['team'],
                'model_name': model_info['name'],
                'predicted_spread': predicted_spread,
                'actual_spread': row['actual_margin'],
                'spread_error': spread_results['spread_error'],
                'spread_correct': spread_results['spread_correct'],
                'predicted_win_prob': win_prob if model_info['win_prob_col'] else None,
                'actual_win': row['actual_win'],
                'win_correct': moneyline_results['win_correct'],
                'brier_score': moneyline_results['brier_score'],
                'log_loss': moneyline_results['log_loss'],
                'predicted_total': predicted_total,
                'actual_total': row['actual_total'],
                'total_error': total_results['total_error'],
                'over_under_correct': total_results['over_under_correct']
            }
            
            game_results.append(game_result)
    
    logger.info(f"Generated {len(game_results)} individual model game results")
    
    # Calculate summary statistics for each model
    game_results_df = pd.DataFrame(game_results)
    model_summaries = {}
    
    for model_key, model_info in MODELS.items():
        model_data = game_results_df[game_results_df['model_name'] == model_info['name']]
        
        # Spread statistics
        spread_data = model_data[model_data['spread_correct'].notna()]
        if len(spread_data) > 0:
            spread_accuracy = spread_data['spread_correct'].mean() * 100
            spread_mae = spread_data['spread_error'].mean()
            spread_rmse = np.sqrt((spread_data['spread_error'] ** 2).mean())
            spread_total_games = len(spread_data)
        else:
            spread_accuracy = spread_mae = spread_rmse = spread_total_games = 0
        
        # Moneyline statistics
        ml_data = model_data[model_data['win_correct'].notna()]
        if len(ml_data) > 0:
            ml_accuracy = ml_data['win_correct'].mean() * 100
            ml_brier = ml_data['brier_score'].mean()
            ml_log_loss = ml_data['log_loss'].mean()
            ml_total_games = len(ml_data)
        else:
            ml_accuracy = ml_brier = ml_log_loss = ml_total_games = 0
        
        # Total statistics
        total_data = model_data[model_data['total_error'].notna()]
        if len(total_data) > 0:
            total_mae = total_data['total_error'].mean()
            total_rmse = np.sqrt((total_data['total_error'] ** 2).mean())
            total_total_games = len(total_data)
            # We can't calculate over/under accuracy without market lines
            total_ou_accuracy = None
        else:
            total_mae = total_rmse = total_total_games = 0
            total_ou_accuracy = None
        
        model_summaries[model_info['name']] = {
            'model_name': model_info['name'],
            'spread_accuracy': round(spread_accuracy, 2),
            'spread_mean_absolute_error': round(spread_mae, 2),
            'spread_rmse': round(spread_rmse, 2),
            'spread_total_games': spread_total_games,
            'moneyline_accuracy': round(ml_accuracy, 2),
            'moneyline_brier_score': round(ml_brier, 4),
            'moneyline_log_loss': round(ml_log_loss, 4),
            'moneyline_total_games': ml_total_games,
            'total_over_under_accuracy': total_ou_accuracy,  # Not calculable
            'total_mean_absolute_error': round(total_mae, 2),
            'total_rmse': round(total_rmse, 2),
            'total_total_games': total_total_games
        }
    
    return game_results, model_summaries


def generate_outputs(game_results, model_summaries):
    """
    Generate output files.
    
    Args:
        game_results (list): List of game result dictionaries
        model_summaries (dict): Dictionary of model summary statistics
    """
    # 1. Generate individual_model_grades.csv
    logger.info(f"Writing summary grades to {individual_grades_path}")
    summary_df = pd.DataFrame(list(model_summaries.values()))
    summary_df.to_csv(individual_grades_path, index=False)
    logger.info(f"✓ Created {individual_grades_path}")
    
    # 2. Generate individual_model_game_results.csv
    logger.info(f"Writing game-by-game results to {game_results_path}")
    game_results_df = pd.DataFrame(game_results)
    game_results_df.to_csv(game_results_path, index=False)
    logger.info(f"✓ Created {game_results_path}")
    
    # 3. Generate model_performance_summary.md
    logger.info(f"Writing summary report to {summary_report_path}")
    generate_markdown_report(model_summaries, summary_report_path)
    logger.info(f"✓ Created {summary_report_path}")


def generate_markdown_report(model_summaries, output_path):
    """
    Generate a markdown summary report.
    
    Args:
        model_summaries (dict): Dictionary of model summary statistics
        output_path (str): Path to output markdown file
    """
    with open(output_path, 'w') as f:
        f.write("# Individual Model Performance Summary\n\n")
        f.write(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Spread Performance
        f.write("## Spread Predictions\n\n")
        f.write("| Model | Accuracy | MAE | RMSE | Games |\n")
        f.write("|-------|----------|-----|------|-------|\n")
        
        # Sort by accuracy descending
        spread_sorted = sorted(
            model_summaries.values(),
            key=lambda x: x['spread_accuracy'],
            reverse=True
        )
        
        for model in spread_sorted:
            f.write(f"| {model['model_name']} | "
                   f"{model['spread_accuracy']:.2f}% | "
                   f"{model['spread_mean_absolute_error']:.2f} | "
                   f"{model['spread_rmse']:.2f} | "
                   f"{model['spread_total_games']} |\n")
        
        f.write("\n")
        
        # Moneyline Performance
        f.write("## Moneyline (Win Probability) Predictions\n\n")
        f.write("| Model | Accuracy | Brier Score | Log Loss | Games |\n")
        f.write("|-------|----------|-------------|----------|-------|\n")
        
        # Sort by accuracy descending, filter out models without moneyline
        ml_sorted = sorted(
            [m for m in model_summaries.values() if m['moneyline_total_games'] > 0],
            key=lambda x: x['moneyline_accuracy'],
            reverse=True
        )
        
        for model in ml_sorted:
            f.write(f"| {model['model_name']} | "
                   f"{model['moneyline_accuracy']:.2f}% | "
                   f"{model['moneyline_brier_score']:.4f} | "
                   f"{model['moneyline_log_loss']:.4f} | "
                   f"{model['moneyline_total_games']} |\n")
        
        f.write("\n")
        
        # Total Performance
        f.write("## Total Points Predictions\n\n")
        f.write("| Model | MAE | RMSE | Games |\n")
        f.write("|-------|-----|------|-------|\n")
        
        # Sort by MAE ascending
        total_sorted = sorted(
            model_summaries.values(),
            key=lambda x: x['total_mean_absolute_error']
        )
        
        for model in total_sorted:
            f.write(f"| {model['model_name']} | "
                   f"{model['total_mean_absolute_error']:.2f} | "
                   f"{model['total_rmse']:.2f} | "
                   f"{model['total_total_games']} |\n")
        
        f.write("\n")
        
        # Key Insights
        f.write("## Key Insights\n\n")
        
        # Best spread predictor
        best_spread = max(model_summaries.values(), key=lambda x: x['spread_accuracy'])
        f.write(f"- **Best Spread Predictor:** {best_spread['model_name']} "
               f"({best_spread['spread_accuracy']:.2f}% accuracy)\n")
        
        # Best moneyline predictor
        ml_models = [m for m in model_summaries.values() if m['moneyline_total_games'] > 0]
        if ml_models:
            best_ml = max(ml_models, key=lambda x: x['moneyline_accuracy'])
            f.write(f"- **Best Moneyline Predictor:** {best_ml['model_name']} "
                   f"({best_ml['moneyline_accuracy']:.2f}% accuracy)\n")
        
        # Best total predictor
        best_total = min(model_summaries.values(), key=lambda x: x['total_mean_absolute_error'])
        f.write(f"- **Best Total Predictor:** {best_total['model_name']} "
               f"(MAE: {best_total['total_mean_absolute_error']:.2f} points)\n")
        
        f.write("\n")
        
        # Additional notes
        f.write("## Notes\n\n")
        f.write("- **Spread Accuracy:** Percentage of games where the model correctly predicted "
               "whether the team would cover the spread.\n")
        f.write("- **MAE (Mean Absolute Error):** Average absolute difference between predicted "
               "and actual values.\n")
        f.write("- **RMSE (Root Mean Square Error):** Square root of average squared differences. "
               "Penalizes larger errors more heavily.\n")
        f.write("- **Brier Score:** Measure of probabilistic prediction accuracy. Lower is better. "
               "Range: [0, 1]\n")
        f.write("- **Log Loss:** Logarithmic loss for probabilistic predictions. Lower is better.\n")
        f.write("- **Hasla** does not provide win probability predictions, so it's excluded from "
               "moneyline analysis.\n")


def main():
    """
    Main execution function.
    """
    logger.info("=== Individual Model Grading Script ===")
    
    # Load data
    predictions_df, outcomes_df = load_data()
    
    if predictions_df is None or outcomes_df is None:
        logger.error("Failed to load data. Exiting.")
        sys.exit(1)
    
    # Match predictions to outcomes
    merged_df = match_predictions_to_outcomes(predictions_df, outcomes_df)
    
    if len(merged_df) == 0:
        logger.error("No predictions could be matched to outcomes. Exiting.")
        sys.exit(1)
    
    # Grade all models
    game_results, model_summaries = grade_all_models(merged_df)
    
    # Generate outputs
    generate_outputs(game_results, model_summaries)
    
    logger.info("\n=== Grading Complete ===")
    logger.info(f"Summary grades: {individual_grades_path}")
    logger.info(f"Game-by-game results: {game_results_path}")
    logger.info(f"Summary report: {summary_report_path}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error in grading script: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
