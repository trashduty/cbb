#!/usr/bin/env python3
"""
Integration test for multi-date game result grading system

This script tests the complete workflow:
1. Loading tracked games from Excel
2. Loading FanMatch HTML files  
3. Matching games using fuzzy team name matching
4. Grading spread and total bets
5. Verifying result columns are populated
"""

import os
import sys
import pandas as pd
from game_tracker import (
    load_fanmatch_results,
    add_game_results_to_spreads,
    add_game_results_to_totals
)

def test_fanmatch_html_loading():
    """Test that FanMatch HTML files are loaded correctly"""
    print("=" * 80)
    print("TEST 1: FanMatch HTML Loading")
    print("=" * 80)
    
    fanmatch_results = load_fanmatch_results()
    
    if len(fanmatch_results) == 0:
        print("✗ FAIL: No FanMatch results loaded")
        return False
    
    print(f"✓ PASS: Loaded {len(fanmatch_results)} games from FanMatch HTML")
    
    # Check for specific dates
    dates_found = set()
    for (home, away, date), data in fanmatch_results.items():
        dates_found.add(date)
    
    print(f"  Dates found: {sorted(dates_found)}")
    
    expected_dates = {'2025-11-03', '2025-11-11', '2025-11-12'}
    if expected_dates.issubset(dates_found):
        print(f"  ✓ All expected dates present: {sorted(expected_dates)}")
        return True
    else:
        missing = expected_dates - dates_found
        print(f"  ✗ Missing dates: {sorted(missing)}")
        return False


def test_spread_game_matching():
    """Test that spread games are matched and graded correctly"""
    print("\n" + "=" * 80)
    print("TEST 2: Spread Game Matching and Grading")
    print("=" * 80)
    
    excel_file = 'master_game_tracking.xlsx'
    if not os.path.exists(excel_file):
        print("✗ FAIL: Excel file not found")
        return False
    
    # Load data
    df_spreads = pd.read_excel(excel_file, sheet_name='Spreads')
    fanmatch_results = load_fanmatch_results()
    
    # Filter to Nov 11-12 games
    nov_11_12_spreads = df_spreads[
        df_spreads['Game Time'].str.contains('Nov 1[12]', na=False)
    ].copy()
    
    if len(nov_11_12_spreads) == 0:
        print("⚠ SKIP: No Nov 11-12 spread games found")
        return True
    
    print(f"Testing {len(nov_11_12_spreads)} spread games from Nov 11-12")
    
    # Grade games
    nov_11_12_spreads = add_game_results_to_spreads(
        nov_11_12_spreads, 
        fanmatch_results
    )
    
    # Check results
    populated = nov_11_12_spreads['spread_result'].notna().sum()
    total = len(nov_11_12_spreads)
    match_rate = populated / total if total > 0 else 0
    
    print(f"  Matched: {populated}/{total} games ({match_rate:.1%})")
    
    if populated == 0:
        print("✗ FAIL: No spread games matched")
        return False
    
    # Verify result columns are populated
    result_cols = [
        'actual_score_team', 
        'actual_score_opponent', 
        'actual_total',
        'actual_margin', 
        'spread_result'
    ]
    
    all_populated = True
    for col in result_cols:
        col_populated = nov_11_12_spreads[col].notna().sum()
        if col_populated != populated:
            print(f"  ✗ Column '{col}' only has {col_populated} values")
            all_populated = False
    
    if not all_populated:
        print("✗ FAIL: Not all result columns populated")
        return False
    
    # Check result values are valid (0, 1, or 2)
    valid_results = nov_11_12_spreads['spread_result'].dropna().isin([0, 1, 2])
    if not valid_results.all():
        print("✗ FAIL: Invalid spread_result values found")
        return False
    
    # Show sample results
    print(f"\n  Sample graded games:")
    graded = nov_11_12_spreads[nov_11_12_spreads['spread_result'].notna()]
    for idx, row in graded.head(3).iterrows():
        result_str = {0: 'LOSS', 1: 'WIN', 2: 'PUSH'}.get(row['spread_result'], '?')
        print(f"    {row['Team']}: {row['actual_score_team']}-{row['actual_score_opponent']} = {result_str}")
    
    print(f"\n✓ PASS: All spread games matched and graded correctly")
    return True


def test_total_game_matching():
    """Test that total games are matched and graded correctly"""
    print("\n" + "=" * 80)
    print("TEST 3: Total Game Matching and Grading")
    print("=" * 80)
    
    excel_file = 'master_game_tracking.xlsx'
    if not os.path.exists(excel_file):
        print("✗ FAIL: Excel file not found")
        return False
    
    # Load data
    df_totals = pd.read_excel(excel_file, sheet_name='Totals')
    fanmatch_results = load_fanmatch_results()
    
    # Filter to Nov 11-12 games
    nov_11_12_totals = df_totals[
        df_totals['Game Time'].str.contains('Nov 1[12]', na=False)
    ].copy()
    
    if len(nov_11_12_totals) == 0:
        print("⚠ SKIP: No Nov 11-12 total games found")
        return True
    
    print(f"Testing {len(nov_11_12_totals)} total games from Nov 11-12")
    
    # Grade games
    nov_11_12_totals = add_game_results_to_totals(
        nov_11_12_totals,
        fanmatch_results
    )
    
    # Check results
    populated = nov_11_12_totals['over_result'].notna().sum()
    total = len(nov_11_12_totals)
    match_rate = populated / total if total > 0 else 0
    
    print(f"  Matched: {populated}/{total} games ({match_rate:.1%})")
    
    if populated == 0:
        print("✗ FAIL: No total games matched")
        return False
    
    # Verify result columns are populated
    result_cols = [
        'actual_score_team1',
        'actual_score_team2',
        'actual_total',
        'over_result',
        'under_result'
    ]
    
    all_populated = True
    for col in result_cols:
        col_populated = nov_11_12_totals[col].notna().sum()
        if col_populated != populated:
            print(f"  ✗ Column '{col}' only has {col_populated} values")
            all_populated = False
    
    if not all_populated:
        print("✗ FAIL: Not all result columns populated")
        return False
    
    # Check result values are valid (0, 1, or 2)
    valid_over = nov_11_12_totals['over_result'].dropna().isin([0, 1, 2])
    valid_under = nov_11_12_totals['under_result'].dropna().isin([0, 1, 2])
    
    if not (valid_over.all() and valid_under.all()):
        print("✗ FAIL: Invalid over/under result values found")
        return False
    
    # Show sample results
    print(f"\n  Sample graded games:")
    graded = nov_11_12_totals[nov_11_12_totals['over_result'].notna()]
    for idx, row in graded.head(3).iterrows():
        over_str = {0: 'LOSS', 1: 'WIN', 2: 'PUSH'}.get(row['over_result'], '?')
        under_str = {0: 'LOSS', 1: 'WIN', 2: 'PUSH'}.get(row['under_result'], '?')
        print(f"    {row['Game']}: Total {row['actual_total']} (Over={over_str}, Under={under_str})")
    
    print(f"\n✓ PASS: All total games matched and graded correctly")
    return True


def main():
    """Run all integration tests"""
    print("Multi-Date Game Result Grading - Integration Tests")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(test_fanmatch_html_loading())
    results.append(test_spread_game_matching())
    results.append(test_total_game_matching())
    
    # Summary
    print("\n" + "=" * 80)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("\nThe multi-date game result grading system is working correctly!")
        print("Games from Nov 11-12 have been matched and graded successfully.")
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
