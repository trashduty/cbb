import importlib.util
import json
import csv
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

FILE = Path(__file__).resolve().parents[1] / 'src/utils/track_opening_results.py'
spec = importlib.util.spec_from_file_location('tracker', FILE)
tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker)


class OpeningResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'data').mkdir()
        self.now = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)
        self.start = self.now + timedelta(days=1)
        self.time = self.start.astimezone(tracker.ET).strftime('%b %d %I:%M%p ET')
        self.model = {'Game': 'A vs. B', 'Game Time': self.time, 'Team': 'A',
                      'Predicted Outcome': -4, 'average_total': 151, 'Moneyline Win Probability': .6,
                      'total_category': 2, 'spread_category': 1}
        self.models = [self.model, {**self.model, 'Team': 'B', 'Predicted Outcome': 4, 'Moneyline Win Probability': .4}]
        self.quotes = []
        for market, team, line, price in [('Spread', 'A', -3, -110), ('Spread', 'B', 3, -110),
            ('Moneyline', 'A', '', 110), ('Moneyline', 'B', '', -120),
            ('Over', '', 150, -105), ('Under', '', 150, -115)]:
            self.quotes.append({'Event ID': 'event-1', 'Commence Time': self.start.isoformat(),
                'Fetched At': self.now.isoformat(), 'Bookmaker Key': 'draftkings', 'Bookmaker': 'DraftKings',
                'Home Team': 'A', 'Away Team': 'B', 'Game Time': self.time,
                'Market': market, 'Team': team, 'Line': line, 'Price': price})
        self.write('Combo_Output.csv', self.models)
        self.write('data/sportsbook_quotes.csv', self.quotes)
        self.write('spreads_lookup_combined.csv', [
            {'total_category': 2, 'market_spread': -3, 'model_spread': -4, 'cover_prob': .56},
            {'total_category': 2, 'market_spread': 3, 'model_spread': 4, 'cover_prob': .44}])
        self.write('totals_lookup_combined.csv', [
            {'spread_category': 1, 'market_total': 150, 'model_total': 151, 'over_prob': .56, 'under_prob': .44}])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, path, rows):
        with (self.root / path).open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def captures(self):
        return tracker.capture(self.root, [], self.now)

    def scores(self, home=80, away=70, completed=True):
        return [{'id': 'event-1', 'home_team': 'A', 'away_team': 'B', 'completed': completed,
                 'scores': [{'name': 'A', 'score': home}, {'name': 'B', 'score': away}]}]

    def test_capture_all_six_quotes_only_three_positive(self):
        rows = self.captures()
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(r['eligible'] == 'yes' for r in rows), 3)
        spread = next(r for r in rows if r['bet_type'] == 'Spread' and r['selection'] == 'A')
        self.assertAlmostEqual(spread['edge'], .56 - 110/210)
        self.assertEqual(spread['line'], -3)
        self.assertEqual(spread['game_date_et'], '2026-11-02')

    def test_first_snapshot_is_immutable_and_totals_not_doubled(self):
        first = self.captures()
        frozen = json.dumps(first, sort_keys=True)
        self.quotes[0]['Line'] = -6
        self.write('data/sportsbook_quotes.csv', self.quotes + self.quotes)
        self.assertEqual(json.dumps(tracker.capture(self.root, first, self.now), sort_keys=True), frozen)
        self.assertEqual(len([r for r in first if r['bet_type'] == 'Total']), 2)

    def test_missing_models_wait_until_best_book_can_be_evaluated(self):
        self.write('Combo_Output.csv', [{**r, 'Predicted Outcome': '', 'average_total': '', 'Moneyline Win Probability': ''} for r in self.models])
        first = self.captures()
        self.assertEqual(first, [])
        self.write('Combo_Output.csv', self.models)
        self.assertEqual(len(tracker.capture(self.root, first, self.now)), 6)

    def test_skip_inplay_stale_wrong_book_or_missing_event_id(self):
        for field, value in [('Commence Time', self.now.isoformat()),
                             ('Fetched At', (self.now-timedelta(hours=2)).isoformat()),
                             ('Bookmaker Key', ''), ('Event ID', '')]:
            self.write('data/sportsbook_quotes.csv', [{**r, field: value} for r in self.quotes])
            self.assertEqual(self.captures(), [])

    def test_best_book_works_without_draftkings(self):
        self.quotes = [{**r, 'Bookmaker Key': 'fanduel', 'Bookmaker': 'FanDuel'} for r in self.quotes]
        self.write('data/sportsbook_quotes.csv', self.quotes)
        rows = self.captures()
        self.assertEqual(len(rows), 6)
        self.assertTrue(all(r['book'] == 'FanDuel' for r in rows))

    def test_rank_by_edge_not_book_order_and_freeze_winner(self):
        candidate = {**self.quotes[0], 'Bookmaker Key': 'fanduel', 'Bookmaker': 'FanDuel', 'Price': 110}
        self.write('data/sportsbook_quotes.csv', self.quotes + [candidate])
        rows = self.captures()
        winner = next(r for r in rows if r['bet_type'] == 'Spread' and r['selection'] == 'A')
        self.assertEqual(winner['book'], 'FanDuel')
        self.assertEqual(winner['odds'], 110)
        self.assertAlmostEqual(winner['edge'], .56 - 100/210)
        self.assertEqual(len(rows), 6)
        self.write('data/sportsbook_quotes.csv', [{**candidate, 'Price': 200}])
        self.assertEqual(tracker.capture(self.root, rows, self.now), rows)

    def test_existing_draftkings_snapshot_not_replaced(self):
        rows = self.captures()
        self.write('data/sportsbook_quotes.csv', [{**r, 'Bookmaker Key': 'fanduel', 'Bookmaker': 'FanDuel', 'Price': 200} for r in self.quotes])
        self.assertEqual(tracker.capture(self.root, rows, self.now), rows)

    def test_grades_spread_total_moneyline_push_and_actual_price_profit(self):
        rows = tracker.grade(self.captures(), self.scores(), self.now)
        over = next(r for r in rows if r['selection'] == 'Over')
        self.assertEqual(over['result'], 'Push')
        ml = next(r for r in rows if r['bet_type'] == 'Moneyline' and r['selection'] == 'A')
        self.assertEqual(ml['result'], 'Win')
        self.assertAlmostEqual(ml['profit_units'], 1.1)
        spread = next(r for r in rows if r['bet_type'] == 'Spread' and r['selection'] == 'A')
        self.assertEqual(spread['result'], 'Win')
        self.assertAlmostEqual(spread['profit_units'], 100/110)
        self.assertEqual(next(r for r in rows if r['selection'] == 'B' and r['bet_type'] == 'Spread')['result'], 'Loss')

    def test_incomplete_missing_score_or_wrong_event_stays_pending(self):
        for scores in [self.scores(completed=False), [{**self.scores()[0], 'id': 'other'}],
                       [{**self.scores()[0], 'scores': []}], self.scores(home=70, away=70)]:
            self.assertTrue(all(r['result'] == 'Pending' for r in tracker.grade(self.captures(), scores, self.now)))

    def test_tiers_have_no_gaps_and_exclude_zero(self):
        for edge, band in [(0, ''), (-.01, ''), (.0001, '0–0.9%'), (.00999, '0–0.9%'),
                           (.01, '1–2.9%'), (.03, '3–5.9%'), (.055, '3–5.9%'), (.06, '6%+')]:
            self.assertEqual(tracker.tier(edge), band)

    def test_roundtrip_public_report_and_persistence(self):
        rows = tracker.grade(self.captures(), self.scores(), self.now)
        tracker.publish(self.root, rows, self.now, 'Test scores')
        payload = json.loads((self.root / 'docs/cbb_opening_results.json').read_text())
        self.assertEqual(payload['snapshots'], 6)
        self.assertEqual(len(payload['ledger']), 3)
        totals = next(s for s in payload['summaries'] if s['bet_type'] == 'Total' and s['edge_tier'] == 'All')
        self.assertEqual(totals['pushes'], 1)
        self.assertIsNone(totals['win_rate'])
        reread = tracker.read_csv(self.root / 'data/cbb_opening_snapshots.csv')
        self.assertEqual(len(tracker.capture(self.root, reread, self.now)), 6)
        self.assertTrue(all(r['captured_at'] == self.now.isoformat() for r in reread))


if __name__ == '__main__':
    unittest.main()
