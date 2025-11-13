#!/usr/bin/env python3
"""
Test script for multi-date FanMatch scraping functionality
"""

import os
import sys
import pandas as pd
from scrape_fanmatch import extract_unique_game_dates, get_game_date_from_string

def test_date_parsing():
    """Test date parsing from game time strings"""
    print("=" * 80)
    print("TEST 1: Date Parsing")
    print("=" * 80)
    
    test_cases = [
        ('Nov 11 07:00PM ET', '2025-11-11'),
        ('Nov 12 08:00PM ET', '2025-11-12'),
        ('Dec 25 12:00PM ET', '2025-12-25'),
        ('Jan 1 06:00PM ET', '2025-01-01'),
    ]
    
    passed = 0
    failed = 0
    
    for game_time, expected in test_cases:
        result = get_game_date_from_string(game_time)
        if result == expected:
            print(f"✓ PASS: '{game_time}' -> '{result}'")
            passed += 1
        else:
            print(f"✗ FAIL: '{game_time}' -> '{result}' (expected '{expected}')")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_extract_unique_dates():
    """Test extracting unique dates from DataFrame"""
    print("\n" + "=" * 80)
    print("TEST 2: Extract Unique Dates")
    print("=" * 80)
    
    # Create test DataFrame
    df = pd.DataFrame({
        'Game Time': [
            'Nov 11 07:00PM ET',
            'Nov 12 08:00PM ET',
            'Nov 12 09:30PM ET',
            'Nov 11 10:00PM ET',
            'Nov 13 07:00PM ET'
        ]
    })
    
    expected_dates = {'2025-11-11', '2025-11-12', '2025-11-13'}
    result_dates = extract_unique_game_dates(df)
    
    if result_dates == expected_dates:
        print(f"✓ PASS: Extracted correct dates: {sorted(result_dates)}")
        return True
    else:
        print(f"✗ FAIL: Got {sorted(result_dates)}, expected {sorted(expected_dates)}")
        return False


def test_integration_with_real_data():
    """Test with real data from Excel file"""
    print("\n" + "=" * 80)
    print("TEST 3: Integration with Real Tracked Games")
    print("=" * 80)
    
    excel_file = 'master_game_tracking.xlsx'
    
    if not os.path.exists(excel_file):
        print("⚠ SKIP: Excel file not found")
        return True
    
    try:
        # Load spreads
        spread_df = pd.read_excel(excel_file, sheet_name='Spreads')
        print(f"Loaded {len(spread_df)} spread games")
        
        # Load totals
        total_df = pd.read_excel(excel_file, sheet_name='Totals')
        print(f"Loaded {len(total_df)} total games")
        
        # Extract dates from both
        spread_dates = extract_unique_game_dates(spread_df)
        total_dates = extract_unique_game_dates(total_df)
        
        all_dates = spread_dates.union(total_dates)
        
        print(f"\nUnique dates found in tracked games:")
        for date in sorted(all_dates):
            print(f"  - {date}")
        
        print(f"\n✓ PASS: Successfully extracted dates from real data")
        return True
        
    except Exception as e:
        print(f"✗ FAIL: Error processing real data: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("Multi-Date FanMatch Scraping Tests")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(test_date_parsing())
    results.append(test_extract_unique_dates())
    results.append(test_integration_with_real_data())
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
