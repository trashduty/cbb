# /// script
# dependencies = [
#   "pandas",
#   "logging"
# ]
# ///
import logging
import pandas as pd
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger('team_mapper')

def map_kp_names(df):
    """Map team names using crosswalk and alternate names as fallback"""
    
    # Get the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to crosswalk file, relative to this script
    crosswalk_path = os.path.join(script_dir, '../../data/crosswalk.csv')
    
    # Load crosswalk files
    try:
        crosswalk = pd.read_csv(crosswalk_path)
        logger.info(f"Loaded crosswalk from {crosswalk_path}")
    except FileNotFoundError:
        logger.error(f"Crosswalk file not found at {crosswalk_path}")
        sys.exit(1)
        
    name_map = crosswalk.set_index('kenpom')['API'].to_dict()
    alt_map = crosswalk.set_index('kenpom_alt')['API'].to_dict()

    # Create mapping report
    unmapped_teams = {}
    found_in_alt = {}
    
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])
            # Check if team exists in alt_map
            if team in alt_map:
                found_in_alt[team] = alt_map[team]
                # Add to name_map if found in alt_map
                name_map[team] = alt_map[team]

    if unmapped_teams:
        logger.warning("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            logger.warning(f"- {team}: {count} occurrences")
            if team in found_in_alt:
                logger.info(f"  Found in alt_map as: {found_in_alt[team]}")

    # Map using combined mappings
    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)

    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    if len(mapped_df) < original_count:
        logger.warning(f"\nDropped {original_count - len(mapped_df)} rows due to mapping issues")
        
        # Print which teams are still causing drops
        still_unmapped = mapped_df[mapped_df[['Home Team', 'Away Team', 'Team']].isna().any(axis=1)]
        if not still_unmapped.empty:
            logger.warning("\nTeams still causing mapping issues:")
            for col in ['Home Team', 'Away Team', 'Team']:
                problem_teams = still_unmapped[col][still_unmapped[col].isna()].unique()
                if len(problem_teams) > 0:
                    logger.warning(f"\n{col} unmapped values:")
                    for team in problem_teams:
                        logger.warning(f"- {team}")

    logger.info(f"Successfully mapped {len(mapped_df)} games")
    return mapped_df


def map_em_names(df):
    """Map team names using crosswalk"""
    # Get the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Path to crosswalk file, relative to this script
    crosswalk_path = os.path.join(script_dir, '../../data/crosswalk.csv')
    
    # Load crosswalk files
    try:
        crosswalk = pd.read_csv(crosswalk_path)
    except FileNotFoundError:
        logger.error(f"Crosswalk file not found at {crosswalk_path}")
        sys.exit(1)
        
    name_map = crosswalk.set_index('evanmiya')['API'].to_dict()

    # Create mapping report
    unmapped_teams = {}
    for team in df['Team'].unique():
        if team not in name_map:
            unmapped_teams[team] = len(df[df['Team'] == team])

    if unmapped_teams:
        logger.warning("\nUnmapped teams and their occurrence count:")
        for team, count in sorted(unmapped_teams.items(), key=lambda x: x[1], reverse=True):
            logger.warning(f"- {team}: {count} occurrences")

    # Create mapped dataframe
    mapped_df = df.copy()
    for col in ['Home Team', 'Away Team', 'Team']:
        mapped_df[col] = mapped_df[col].map(name_map)

    # Drop rows with missing mappings
    original_count = len(mapped_df)
    mapped_df = mapped_df.dropna(subset=['Home Team', 'Away Team', 'Team'])
    if len(mapped_df) < original_count:
        logger.warning(f"\nDropped {original_count - len(mapped_df)} rows due to mapping issues")

    return mapped_df


def main():
    logger.info("=== Starting team name mapping ===")
    
    # Get the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define data directory path relative to this script
    data_dir = os.path.join(script_dir, '../../data')
    
    # Process KenPom data
    kp_path = os.path.join(data_dir, 'kp.csv')
    logger.info(f"Processing KenPom data from {kp_path}")
    
    try:
        kp_df = pd.read_csv(kp_path)
        kp_mapped_df = map_kp_names(kp_df)
        
        # Save mapped data
        output_path = os.path.join(data_dir, 'kp_mapped.csv')
        kp_mapped_df.to_csv(output_path, index=False)
        logger.info(f"Saved mapped KenPom data to {output_path}")
    except Exception as e:
        logger.error(f"Error processing KenPom data: {str(e)}")
        
    # Process EvanMiya data
    em_path = os.path.join(data_dir, 'em.csv')
    logger.info(f"Processing EvanMiya data from {em_path}")
    
    try:
        em_df = pd.read_csv(em_path)
        em_mapped_df = map_em_names(em_df)
        
        # Save mapped data
        output_path = os.path.join(data_dir, 'em_mapped.csv')
        em_mapped_df.to_csv(output_path, index=False)
        logger.info(f"Saved mapped EvanMiya data to {output_path}")
    except Exception as e:
        logger.error(f"Error processing EvanMiya data: {str(e)}")
    
    logger.info("=== Team name mapping completed ===")


if __name__ == "__main__":
    main()

# ///