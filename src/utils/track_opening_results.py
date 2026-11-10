# /// script
# dependencies = ["pandas"]
# ///
"""Immutable, forward-only Best Book opening snapshots and positive-edge grading.

Snapshots freeze quote AND contemporaneous Combo model; no retrospective filling.
Run --capture after generate_combo_edges.py; run --grade independently of scrapers.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

UTC = timezone.utc
ET = ZoneInfo('America/New_York')
ROOT = Path(__file__).resolve().parents[2]
FIELDS = ['snapshot_id', 'event_id', 'game', 'home_team', 'away_team', 'commence_time',
          'game_date_et', 'captured_at', 'book', 'bet_type', 'selection', 'line', 'odds',
          'model_prediction', 'probability', 'implied_probability', 'edge', 'edge_tier',
          'eligible', 'spread_consensus', 'total_consensus', 'total_consensus_source',
          'snapshot_note', 'result', 'home_score', 'away_score', 'graded_at', 'profit_units']
TIERS = ['0–0.9%', '1–2.9%', '3–5.9%', '6%+']


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def stamp(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except ValueError:
        return None


def implied(odds):
    odds = number(odds)
    if odds is None or abs(odds) < 100:
        return None
    return 100 / (odds + 100) if odds > 0 else -odds / (100 - odds)


def tier(edge):
    edge = number(edge)
    if edge is None or edge <= 0:
        return ''
    return TIERS[0] if edge < .01 else TIERS[1] if edge < .03 else TIERS[2] if edge < .06 else TIERS[3]


def read_csv(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows({key: row.get(key, '') for key in FIELDS} for row in rows)
    temporary.replace(path)


def lookup_probabilities(root, wanted):
    """Read lookup files in chunks, retaining only the snapshot keys we need."""
    import pandas as pd
    found = {}
    for kind, filename, keys, probabilities in [
        ('Spread', 'spreads_lookup_combined.csv', ['total_category', 'market_spread', 'model_spread'], ['cover_prob']),
        ('Total', 'totals_lookup_combined.csv', ['spread_category', 'market_total', 'model_total'], ['over_prob', 'under_prob'])
    ]:
        requested = wanted.get(kind, set())
        if not requested or not (root / filename).exists():
            continue
        target = pd.DataFrame(list(requested), columns=keys)
        for chunk in pd.read_csv(root / filename, usecols=keys + probabilities, chunksize=200000):
            matched = chunk.merge(target, on=keys, how='inner')
            for record in matched.to_dict('records'):
                key = tuple(float(record[k]) for k in keys)
                for probability in probabilities:
                    value = number(record[probability])
                    if value is not None and 0 <= value <= 1:
                        found[(kind, key, probability)] = value
    return found


def captured_spread_consensus(model, line):
    values = [number(model.get('spread_' + system)) for system in ('kenpom', 'evanmiya', 'barttorvik')]
    if line is None or any(value is None for value in values):
        return 'No'
    return 'Yes' if all(value < line for value in values) else 'No'


def captured_total_consensus(model, line, selection, missing='No'):
    values = [number(model.get('projected_total_' + system))
              for system in ('kenpom', 'evanmiya', 'barttorvik')]
    if line is None or any(value is None for value in values):
        return missing
    if selection == 'Over':
        return 'Yes' if all(value > line for value in values) else 'No'
    if selection == 'Under':
        return 'Yes' if all(value < line for value in values) else 'No'
    return missing


def backfill_total_consensus(root, rows):
    """Recover the three projections from the commit that introduced each snapshot."""
    missing = {row['snapshot_id']: row for row in rows
               if row['bet_type'] == 'Total' and not row.get('total_consensus')}
    if not missing:
        return

    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, encoding='utf-8')

    snapshot_path = 'data/cbb_opening_snapshots.csv'
    commits = git('log', '--reverse', '--format=%H', '--', snapshot_path).splitlines()
    recovered = 0
    for commit in commits:
        archived = csv.DictReader(git('show', f'{commit}:{snapshot_path}').splitlines())
        introduced = [missing.pop(row['snapshot_id']) for row in archived
                      if row['snapshot_id'] in missing]
        if not introduced:
            continue
        # An older checkout can start at a shallow boundary containing existing rows.
        # Only trust an archive with a parent so that boundary cannot serve as evidence.
        parents = git('rev-list', '--parents', '-n', '1', commit).split()
        if len(parents) < 2:
            for row in introduced:
                row['total_consensus'] = 'Not Recorded'
            continue
        models = {}
        for model in csv.DictReader(git('show', f'{commit}:Combo_Output.csv').splitlines()):
            teams = tuple(sorted(model.get('Game', '').split(' vs. ')))
            models[(teams, model.get('Game Time'), model.get('Team'))] = model
        for row in introduced:
            start = stamp(row.get('commence_time'))
            teams = tuple(sorted([row['home_team'], row['away_team']]))
            game_time = start.astimezone(ET).strftime('%b %d %I:%M%p ET') if start else ''
            model = models.get((teams, game_time, teams[0]), {})
            frozen = number(row.get('model_prediction'))
            if frozen is None or frozen != number(model.get('average_total')):
                row['total_consensus'] = 'Not Recorded'
                continue
            consensus = captured_total_consensus(model, number(row.get('line')), row['selection'], missing='Not Recorded')
            row['total_consensus'] = consensus
            if consensus in ('Yes', 'No'):
                row['total_consensus_source'] = commit
                recovered += 1
        if not missing:
            break
    for row in missing.values():
        row['total_consensus'] = 'Not Recorded'
    print(f'Recovered total consensus for {recovered} historical snapshots from capture commits.')


def capture(root, existing, now):
    quotes = read_csv(root / 'data/sportsbook_quotes.csv')
    models = read_csv(root / 'Combo_Output.csv')
    model_map = {}
    for model in models:
        teams = model.get('Game', '').split(' vs. ')
        if len(teams) == 2:
            key = (tuple(sorted(teams)), model.get('Game Time'), model.get('Team'))
            model_map[key] = model
    known = {row['snapshot_id'] for row in existing}
    pending = []
    wanted = {'Spread': set(), 'Total': set()}
    for quote in quotes:
        if not quote.get('Bookmaker Key') or not quote.get('Bookmaker'):
            continue
        event, start, fetched = quote.get('Event ID'), stamp(quote.get('Commence Time')), stamp(quote.get('Fetched At'))
        # Never backfill a pregame snapshot using post-tipoff or stale data.
        if not event or not start or start <= now or not fetched or not 0 <= (now-fetched).total_seconds() <= 5400:
            continue
        market = quote.get('Market')
        if market not in ('Spread', 'Moneyline', 'Over', 'Under'):
            continue
        selection = quote.get('Team') if market in ('Spread', 'Moneyline') else market
        if market in ('Spread', 'Moneyline') and selection not in (quote['Home Team'], quote['Away Team']):
            continue
        snapshot_id = hashlib.sha256(f'{event}|{market}|{selection}'.encode()).hexdigest()[:24]
        odds, line = number(quote.get('Price')), number(quote.get('Line'))
        if snapshot_id in known or implied(odds) is None or (market != 'Moneyline' and line is None):
            continue
        team = selection if market in ('Spread', 'Moneyline') else min(quote['Home Team'], quote['Away Team'])
        model = model_map.get((tuple(sorted([quote['Home Team'], quote['Away Team']])), quote['Game Time'], team), {})
        prediction = number(model.get('Predicted Outcome' if market == 'Spread' else 'Moneyline Win Probability' if market == 'Moneyline' else 'average_total'))
        category = number(model.get('total_category' if market == 'Spread' else 'spread_category'))
        lookup_key = None
        if market != 'Moneyline' and prediction is not None and category is not None:
            lookup_key = (category, round(line*2)/2, round(prediction*2)/2)
            wanted['Spread' if market == 'Spread' else 'Total'].add(lookup_key)
        pending.append((quote, model, snapshot_id, market, selection, start, prediction, lookup_key))
    probabilities = lookup_probabilities(root, wanted) if pending else {}
    candidates = {}
    for quote, model, snapshot_id, market, selection, start, prediction, key in pending:
        probability = prediction if market == 'Moneyline' else probabilities.get(
            ('Spread' if market == 'Spread' else 'Total', key,
             'cover_prob' if market == 'Spread' else 'over_prob' if market == 'Over' else 'under_prob'))
        if probability is not None and not 0 <= probability <= 1:
            probability = None
        if probability is None:
            continue  # Best Book cannot be ranked without a contemporaneous model probability.
        odds = number(quote['Price'])
        edge = probability - implied(odds)
        candidate = dict(snapshot_id=snapshot_id, event_id=quote['Event ID'],
            game=quote['Home Team']+' vs. '+quote['Away Team'], home_team=quote['Home Team'], away_team=quote['Away Team'],
            commence_time=start.isoformat(), game_date_et=start.astimezone(ET).date().isoformat(),
            captured_at=now.isoformat(), book=quote['Bookmaker'], bet_type='Total' if market in ('Over', 'Under') else market,
            selection=selection, line=number(quote.get('Line')) if market != 'Moneyline' else None, odds=odds,
            model_prediction=prediction, probability=probability, implied_probability=implied(odds), edge=edge,
            edge_tier=tier(edge), eligible='yes' if edge is not None and edge > 0 else 'no',
            spread_consensus=captured_spread_consensus(model, number(quote.get('Line'))) if market == 'Spread' else '',
            total_consensus=captured_total_consensus(model, number(quote.get('Line')), selection) if market in ('Over', 'Under') else '',
            total_consensus_source='capture' if market in ('Over', 'Under') else '',
            snapshot_note='First evaluable Best Book snapshot; highest edge across available tracked books',
            result='Pending', home_score=None, away_score=None, graded_at='', profit_units=None)
        # Same ranking as the live Best Book: highest edge, alphabetical book on ties.
        rank = lambda row: (-row['edge'], row['book'], row['line'] if row['line'] is not None else 0, row['odds'])
        previous = candidates.get(snapshot_id)
        if previous is None or rank(candidate) < rank(previous):
            candidates[snapshot_id] = candidate
    return existing + list(candidates.values())


def grade(rows, games, now):
    final = {game['id']: game for game in games if game.get('id') and game.get('completed') is True}
    for row in rows:
        game = final.get(row['event_id'])
        if not game:
            continue
        # Event ID AND exact team identities prevent accidental rematch grading.
        if game.get('home_team') != row['home_team'] or game.get('away_team') != row['away_team']:
            continue
        scores = {score.get('name'): number(score.get('score')) for score in (game.get('scores') or [])}
        home, away = scores.get(row['home_team']), scores.get(row['away_team'])
        if home is None or away is None or home == away or home < 0 or away < 0:
            continue
        line = number(row.get('line'))
        if row['bet_type'] == 'Total':
            if line is None:
                continue
            margin = home + away - line
            if row['selection'] == 'Under':
                margin = -margin
        else:
            margin = home - away if row['selection'] == row['home_team'] else away - home
            if row['bet_type'] == 'Spread':
                if line is None:
                    continue
                margin += line
        result = 'Win' if margin > 0 else 'Loss' if margin < 0 else 'Push'
        odds = number(row['odds'])
        profit = (odds/100 if odds > 0 else 100/-odds) if result == 'Win' else -1 if result == 'Loss' else 0
        row.update(result=result, home_score=home, away_score=away, profit_units=profit)
        if not row.get('graded_at'):
            row['graded_at'] = now.isoformat()
    return rows


def fetch_scores():
    key = os.environ.get('ODDS_API_KEY')
    if not key:
        raise RuntimeError('ODDS_API_KEY is required for automatic score updates')
    url = 'https://api.the-odds-api.com/v4/sports/basketball_ncaab/scores/?'+urlencode({'apiKey': key, 'daysFrom': 3, 'dateFormat': 'iso'})
    try:
        with urlopen(url, timeout=45) as response:
            data = json.load(response)
    except Exception:
        raise RuntimeError('Score request failed; existing results retained. Check API status and quota.') from None
    if not isinstance(data, list):
        raise RuntimeError('Unexpected scores response; existing results retained')
    return data


def publish(root, snapshots, now, status):
    ledger = [row for row in snapshots if row['eligible'] == 'yes']
    write_csv(root / 'data/cbb_opening_snapshots.csv', snapshots)
    write_csv(root / 'data/cbb_opening_ledger.csv', ledger)
    write_csv(root / 'docs/cbb_opening_snapshots.csv', snapshots)
    write_csv(root / 'docs/cbb_opening_ledger.csv', ledger)
    summaries = []
    for market in ('Spread', 'Total', 'Moneyline'):
        for band in ['All'] + TIERS:
            subset = [r for r in ledger if r['bet_type'] == market and (band == 'All' or r['edge_tier'] == band)]
            wins, losses, pushes, pending = [sum(r['result'] == value for r in subset) for value in ('Win', 'Loss', 'Push', 'Pending')]
            summaries.append(dict(bet_type=market, edge_tier=band, wins=wins, losses=losses, pushes=pushes,
                pending=pending, win_rate=wins/(wins+losses) if wins+losses else None,
                profit_units=sum(number(r.get('profit_units')) or 0 for r in subset)))
    def clean(row):
        return {key: (number(value) if key in ['line','odds','model_prediction','probability','implied_probability','edge','home_score','away_score','profit_units'] else value) for key,value in row.items()}
    payload = dict(updated_at=now.isoformat(), score_status=status, tiers=TIERS, summaries=summaries,
                   snapshots=len(snapshots), ledger=[clean(r) for r in ledger])
    (root / 'docs').mkdir(exist_ok=True)
    (root / 'docs/cbb_opening_results.json').write_text(json.dumps(payload, allow_nan=False, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--grade', action='store_true')
    parser.add_argument('--scores-json', type=Path, help='Offline score import/recovery in Odds API schema')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    now = datetime.now(UTC)
    rows = read_csv(args.root / 'data/cbb_opening_snapshots.csv')
    if args.capture:
        rows = capture(args.root, rows, now)
    cache_path = args.root / 'data/cbb_opening_scores.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    status = 'Scores not requested in this run'
    failed = False
    if args.grade:
        backfill_total_consensus(args.root, rows)
        try:
            games = json.loads(args.scores_json.read_text()) if args.scores_json else fetch_scores()
            for game in games:
                if game.get('id') and game.get('completed') is True:
                    cache[game['id']] = game
            status = 'Score update successful'
        except RuntimeError as error:
            status, failed = str(error), True
    rows = grade(rows, list(cache.values()), now)
    publish(args.root, rows, now, status)
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2)+'\n')
    print(f'Opening snapshots: {len(rows)}; positive-edge selections: {sum(r["eligible"] == "yes" for r in rows)}. {status}')
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
