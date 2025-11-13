#!/usr/bin/env python3
"""
Test script to validate game grading logic

This script creates test data to verify that the grading logic works correctly
for both spread and total bets.
"""

import pandas as pd
from game_tracker import grade_spread_result, grade_total_result, fuzzy_match_teams, normalize_team_name

def test_spread_grading():
    """Test spread grading logic"""
    print("=" * 80)
    print("TESTING SPREAD GRADING LOGIC")
    print("=" * 80)
    
    test_cases = [
        # (market_spread, actual_margin, expected_result, description)
        (-5, 6, 1, "Favorite -5, wins by 6: WIN (covered)"),
        (-5, 5, 2, "Favorite -5, wins by 5: PUSH"),
        (-5, 4, 0, "Favorite -5, wins by 4: LOSS (didn't cover)"),
        (-5, -2, 0, "Favorite -5, loses by 2: LOSS"),
        (5, -4, 1, "Underdog +5, loses by 4: WIN (covered)"),
        (5, -5, 2, "Underdog +5, loses by 5: PUSH"),
        (5, -6, 0, "Underdog +5, loses by 6: LOSS"),
        (5, 3, 1, "Underdog +5, wins by 3: WIN"),
        (-10, 12, 1, "Favorite -10, wins by 12: WIN"),
        (-10, 10, 2, "Favorite -10, wins by 10: PUSH"),
        (-10, 8, 0, "Favorite -10, wins by 8: LOSS"),
    ]
    
    passed = 0
    failed = 0
    
    for market_spread, actual_margin, expected, description in test_cases:
        result = grade_spread_result(market_spread, actual_margin)
        result_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}[result]
        expected_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}[expected]
        
        if result == expected:
            print(f"✓ {description}")
            print(f"  market_spread={market_spread}, actual_margin={actual_margin} → {result_str}")
            passed += 1
        else:
            print(f"✗ {description}")
            print(f"  market_spread={market_spread}, actual_margin={actual_margin}")
            print(f"  Expected: {expected_str}, Got: {result_str}")
            failed += 1
    
    print(f"\nSpread Tests: {passed} passed, {failed} failed")
    return failed == 0

def test_total_grading():
    """Test total (over/under) grading logic"""
    print("\n" + "=" * 80)
    print("TESTING TOTAL GRADING LOGIC")
    print("=" * 80)
    
    test_cases = [
        # (bet_type, market_total, actual_total, expected_result, description)
        ('over', 150, 155, 1, "Over 150, actual 155: WIN"),
        ('over', 150, 150, 2, "Over 150, actual 150: PUSH"),
        ('over', 150, 145, 0, "Over 150, actual 145: LOSS"),
        ('under', 150, 145, 1, "Under 150, actual 145: WIN"),
        ('under', 150, 150, 2, "Under 150, actual 150: PUSH"),
        ('under', 150, 155, 0, "Under 150, actual 155: LOSS"),
        ('over', 160.5, 161, 1, "Over 160.5, actual 161: WIN"),
        ('over', 160.5, 160, 0, "Over 160.5, actual 160: LOSS"),
        ('under', 160.5, 160, 1, "Under 160.5, actual 160: WIN"),
        ('under', 160.5, 161, 0, "Under 160.5, actual 161: LOSS"),
    ]
    
    passed = 0
    failed = 0
    
    for bet_type, market_total, actual_total, expected, description in test_cases:
        result = grade_total_result(bet_type, market_total, actual_total)
        result_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}[result]
        expected_str = {0: "LOSS", 1: "WIN", 2: "PUSH"}[expected]
        
        if result == expected:
            print(f"✓ {description}")
            print(f"  {bet_type} {market_total}, actual={actual_total} → {result_str}")
            passed += 1
        else:
            print(f"✗ {description}")
            print(f"  {bet_type} {market_total}, actual={actual_total}")
            print(f"  Expected: {expected_str}, Got: {result_str}")
            failed += 1
    
    print(f"\nTotal Tests: {passed} passed, {failed} failed")
    return failed == 0

def test_fuzzy_matching():
    """Test fuzzy team name matching"""
    print("\n" + "=" * 80)
    print("TESTING FUZZY TEAM NAME MATCHING")
    print("=" * 80)
    
    test_cases = [
        # (team1, team2, should_match, description)
        ("Duke", "Duke", True, "Exact match"),
        ("Duke", "DUKE", True, "Case insensitive"),
        ("Duke Blue Devils", "Duke", True, "Partial match (full name vs short)"),
        ("Duke", "Duke Blue Devils", True, "Partial match (short vs full name)"),
        ("North Carolina", "North Carolina Tar Heels", True, "Partial match"),
        ("St. John's", "Saint John's", True, "Fuzzy match (St. vs Saint)"),
        ("St. Mary's", "Saint Mary's", True, "Fuzzy match (St. vs Saint)"),
        ("UNC", "North Carolina", False, "Abbreviation (should not match without mapping)"),
        ("Duke", "Kentucky", False, "Different teams"),
        ("Florida", "Florida Atlantic", False, "Different teams (one is substring)"),
        ("  Duke  ", "Duke", True, "Whitespace normalization"),
        ("Duke    Blue    Devils", "Duke Blue Devils", True, "Multiple spaces"),
    ]
    
    passed = 0
    failed = 0
    
    for team1, team2, should_match, description in test_cases:
        result = fuzzy_match_teams(team1, team2)
        
        if result == should_match:
            print(f"✓ {description}")
            print(f"  '{team1}' vs '{team2}' → {result}")
            passed += 1
        else:
            print(f"✗ {description}")
            print(f"  '{team1}' vs '{team2}'")
            print(f"  Expected: {should_match}, Got: {result}")
            # Show normalized versions for debugging
            norm1 = normalize_team_name(team1)
            norm2 = normalize_team_name(team2)
            print(f"  Normalized: '{norm1}' vs '{norm2}'")
            failed += 1
    
    print(f"\nFuzzy Matching Tests: {passed} passed, {failed} failed")
    return failed == 0

def main():
    """Run all tests"""
    print("Testing Game Grading Logic\n")
    
    spread_ok = test_spread_grading()
    total_ok = test_total_grading()
    fuzzy_ok = test_fuzzy_matching()
    
    print("\n" + "=" * 80)
    print("OVERALL RESULTS")
    print("=" * 80)
    
    if spread_ok and total_ok and fuzzy_ok:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        if not spread_ok:
            print("  - Spread grading tests failed")
        if not total_ok:
            print("  - Total grading tests failed")
        if not fuzzy_ok:
            print("  - Fuzzy matching tests failed")
        return 1

if __name__ == "__main__":
    exit(main())
