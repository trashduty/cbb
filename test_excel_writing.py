#!/usr/bin/env python3
"""
Test script to validate Excel file writing and error handling
"""

import pandas as pd
import os
import sys
import tempfile
import shutil
from game_tracker import save_to_excel, save_to_csv_fallback

def test_excel_writing_with_data():
    """Test that Excel file is created when data is present"""
    print("=" * 80)
    print("TEST: Excel writing with data")
    print("=" * 80)
    
    # Create test data
    spread_data = pd.DataFrame({
        'Game Time': ['Nov 13 07:00PM ET', 'Nov 13 08:00PM ET'],
        'Team': ['Team A', 'Team B'],
        'market_spread': [-5.0, 3.0],
        'model_spread': [-4.5, 3.5],
        'Edge For Covering Spread': [0.04, 0.035],
        'spread_consensus_flag': [1, 1]
    })
    
    total_data = pd.DataFrame({
        'Game Time': ['Nov 13 07:00PM ET'],
        'Game': ['Team A vs. Team C'],
        'market_total': [150.5],
        'model_total': [155.0],
        'Over Total Edge': [0.04],
        'Under Total Edge': [0.01],
        'over_consensus_flag': [1]
    })
    
    # Test in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_excel = os.path.join(tmpdir, 'test_game_tracking.xlsx')
        
        # Temporarily override the global excel_output path and legacy CSV paths
        import game_tracker
        original_excel_output = game_tracker.excel_output
        original_legacy_spread_csv = game_tracker.legacy_spread_csv
        original_legacy_total_csv = game_tracker.legacy_total_csv
        
        game_tracker.excel_output = test_excel
        game_tracker.legacy_spread_csv = os.path.join(tmpdir, 'master_spread_games.csv')
        game_tracker.legacy_total_csv = os.path.join(tmpdir, 'master_total_games.csv')
        
        try:
            # Call save_to_excel
            spread_count, total_count = save_to_excel(spread_data, total_data)
            
            # Verify file was created
            if os.path.exists(test_excel):
                file_size = os.path.getsize(test_excel)
                print(f"✓ Excel file created: {test_excel}")
                print(f"  File size: {file_size} bytes")
                
                # Verify data was written correctly
                df_spreads = pd.read_excel(test_excel, sheet_name='Spreads')
                df_totals = pd.read_excel(test_excel, sheet_name='Totals')
                
                print(f"  Spreads sheet: {len(df_spreads)} rows")
                print(f"  Totals sheet: {len(df_totals)} rows")
                print(f"  New games added: {spread_count} spreads, {total_count} totals")
                
                # Check that we added the expected new games
                if spread_count == 2 and total_count == 1:
                    print("✓ Data written correctly")
                    return True
                else:
                    print(f"✗ Data mismatch: expected 2 new spreads and 1 new total, got {spread_count} spreads and {total_count} totals")
                    return False
            else:
                print(f"✗ Excel file was not created")
                return False
                
        finally:
            # Restore original paths
            game_tracker.excel_output = original_excel_output
            game_tracker.legacy_spread_csv = original_legacy_spread_csv
            game_tracker.legacy_total_csv = original_legacy_total_csv
    
    return False

def test_csv_fallback():
    """Test CSV fallback when Excel writing fails"""
    print("\n" + "=" * 80)
    print("TEST: CSV fallback functionality")
    print("=" * 80)
    
    # Create test data
    spread_data = pd.DataFrame({
        'Game Time': ['Nov 13 07:00PM ET'],
        'Team': ['Team A'],
        'market_spread': [-5.0]
    })
    
    total_data = pd.DataFrame({
        'Game Time': ['Nov 13 07:00PM ET'],
        'Game': ['Team A vs. Team B'],
        'market_total': [150.5]
    })
    
    # Test in a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        import game_tracker
        original_script_dir = game_tracker.script_dir
        game_tracker.script_dir = tmpdir
        
        try:
            # Call CSV fallback
            spread_count, total_count = save_to_csv_fallback(spread_data, total_data)
            
            csv_spread_file = os.path.join(tmpdir, 'master_spread_games.csv')
            csv_total_file = os.path.join(tmpdir, 'master_total_games.csv')
            
            # Verify files were created
            spread_exists = os.path.exists(csv_spread_file)
            total_exists = os.path.exists(csv_total_file)
            
            if spread_exists and total_exists:
                print(f"✓ CSV files created successfully")
                print(f"  Spread CSV: {csv_spread_file}")
                print(f"  Total CSV: {csv_total_file}")
                
                # Verify data
                df_spreads = pd.read_csv(csv_spread_file)
                df_totals = pd.read_csv(csv_total_file)
                
                print(f"  Spreads: {len(df_spreads)} rows")
                print(f"  Totals: {len(df_totals)} rows")
                
                if len(df_spreads) == 1 and len(df_totals) == 1:
                    print("✓ CSV fallback works correctly")
                    return True
                else:
                    print(f"✗ Data mismatch in CSV files")
                    return False
            else:
                print(f"✗ CSV files not created")
                return False
                
        finally:
            # Restore original path
            game_tracker.script_dir = original_script_dir
    
    return False

def test_empty_dataframe_handling():
    """Test that empty DataFrames are handled correctly"""
    print("\n" + "=" * 80)
    print("TEST: Empty DataFrame handling")
    print("=" * 80)
    
    # Create empty dataframes
    spread_data = pd.DataFrame()
    total_data = pd.DataFrame()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        test_excel = os.path.join(tmpdir, 'test_empty.xlsx')
        
        import game_tracker
        original_excel_output = game_tracker.excel_output
        original_legacy_spread_csv = game_tracker.legacy_spread_csv
        original_legacy_total_csv = game_tracker.legacy_total_csv
        
        game_tracker.excel_output = test_excel
        game_tracker.legacy_spread_csv = os.path.join(tmpdir, 'master_spread_games.csv')
        game_tracker.legacy_total_csv = os.path.join(tmpdir, 'master_total_games.csv')
        
        try:
            # Call save_to_excel with empty data
            spread_count, total_count = save_to_excel(spread_data, total_data)
            
            # With empty DataFrames and no existing data, we expect 0 new records
            if spread_count == 0 and total_count == 0:
                print("✓ Empty DataFrames handled correctly")
                print(f"  Returned counts: {spread_count} spreads, {total_count} totals")
                return True
            else:
                print(f"✗ Unexpected return values: {spread_count}, {total_count}")
                return False
                
        finally:
            game_tracker.excel_output = original_excel_output
            game_tracker.legacy_spread_csv = original_legacy_spread_csv
            game_tracker.legacy_total_csv = original_legacy_total_csv
    
    return False

def main():
    """Run all tests"""
    print("Testing Excel Writing and Error Handling\n")
    
    test1_ok = test_excel_writing_with_data()
    test2_ok = test_csv_fallback()
    test3_ok = test_empty_dataframe_handling()
    
    print("\n" + "=" * 80)
    print("OVERALL RESULTS")
    print("=" * 80)
    
    if test1_ok and test2_ok and test3_ok:
        print("✓ All Excel writing tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        if not test1_ok:
            print("  - Excel writing test failed")
        if not test2_ok:
            print("  - CSV fallback test failed")
        if not test3_ok:
            print("  - Empty DataFrame handling test failed")
        return 1

if __name__ == "__main__":
    exit(main())
