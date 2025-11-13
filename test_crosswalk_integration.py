#!/usr/bin/env python3
"""
Test crosswalk integration for team name matching
"""

import sys
from game_tracker import load_team_name_crosswalk, map_team_name_to_kenpom, fuzzy_match_teams

def test_crosswalk_loading():
    """Test that crosswalk loads correctly"""
    print("=" * 80)
    print("TEST 1: Crosswalk Loading")
    print("=" * 80)
    
    crosswalk = load_team_name_crosswalk()
    
    if len(crosswalk) == 0:
        print("✗ FAIL: No mappings loaded")
        return False
    
    print(f"✓ PASS: Loaded {len(crosswalk)} team name mappings")
    
    # Check for expected teams
    expected_teams = [
        'Oklahoma St Cowboys',
        'North Florida Ospreys',
        'Prairie View Panthers'
    ]
    
    for team in expected_teams:
        if team in crosswalk:
            print(f"  ✓ Found: {team} → {crosswalk[team]}")
        else:
            print(f"  ✗ Missing: {team}")
            return False
    
    return True


def test_name_mapping():
    """Test name mapping function"""
    print("\n" + "=" * 80)
    print("TEST 2: Name Mapping")
    print("=" * 80)
    
    crosswalk = load_team_name_crosswalk()
    
    test_cases = [
        ('Oklahoma St Cowboys', 'Oklahoma St.'),
        ('North Florida Ospreys', 'North Florida'),
        ('Prairie View Panthers', 'Prairie View A&M'),
        ('Morehead St Eagles', 'Morehead St.'),
        ("Saint Joseph's Hawks", "Saint Joseph's"),
    ]
    
    passed = 0
    failed = 0
    
    for api_name, expected_kenpom in test_cases:
        result = map_team_name_to_kenpom(api_name, crosswalk)
        if result == expected_kenpom:
            print(f"✓ PASS: {api_name} → {result}")
            passed += 1
        else:
            print(f"✗ FAIL: {api_name} → {result} (expected {expected_kenpom})")
            failed += 1
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_crosswalk_matching():
    """Test that crosswalk improves matching accuracy"""
    print("\n" + "=" * 80)
    print("TEST 3: Crosswalk-Enhanced Matching")
    print("=" * 80)
    
    crosswalk = load_team_name_crosswalk()
    
    # Test cases where crosswalk should help
    test_cases = [
        ('Oklahoma St Cowboys', 'Oklahoma St.', True),
        ('Prairie View Panthers', 'Prairie View A&M', True),
        ('North Florida Ospreys', 'North Florida', True),
        ('Florida Gators', 'Florida Atlantic', False),  # Should NOT match
    ]
    
    passed = 0
    failed = 0
    
    for api_name, kenpom_name, should_match in test_cases:
        result = fuzzy_match_teams(api_name, kenpom_name, crosswalk=crosswalk)
        
        if result == should_match:
            status = "✓ PASS"
            passed += 1
        else:
            status = "✗ FAIL"
            failed += 1
        
        match_str = "matches" if should_match else "does NOT match"
        result_str = "matched" if result else "did NOT match"
        print(f"{status}: {api_name} {match_str} {kenpom_name} → {result_str}")
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def main():
    """Run all tests"""
    print("Crosswalk Integration Tests")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(test_crosswalk_loading())
    results.append(test_name_mapping())
    results.append(test_crosswalk_matching())
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("\nCrosswalk integration is working correctly!")
        return 0
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
