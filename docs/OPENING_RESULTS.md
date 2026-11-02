# CBB opening snapshot results

Public page: `docs/cbb-results.html` (GitHub Pages `/cbb/cbb-results.html`). The model board links to it.

## Snapshot policy

This is a forward-only record of first-evaluable Best Book quotes evaluated by the weighted Combo model, separate from the legacy CBB/Hasla grader.

After each successful Combo generation, `uv run src/utils/track_opening_results.py --capture` freezes each selection's first **evaluable pregame Best Book** quote: the highest calculated edge across all available tracked sportsbooks, with ties resolved alphabetically by book, matching the live board's ranking. It records event ID, scheduled tipoff, capture timestamp, teams, side, line, price, contemporaneous model prediction, lookup probability, implied probability, edge, and eligibility. It captures Spread and Moneyline for each team and Over/Under once per game.

The snapshot is keyed by API event ID + market + selection. Reruns and later quotes cannot overwrite the opening line, model, or edge. A newly encountered event is not assumed to have the sportsbook's historical opening price: the public page explicitly calls it the first captured price after tracking began. Capture requires a fresh API snapshot (at most 90 minutes old) and a game that has not tipped off. Bookmaker timestamps may be older than fetch time; these are observed quotes, not a guaranteed first publication time.

For new captures, quotes without model/lookup probabilities cannot be ranked and are skipped until an evaluable pregame capture exists. That capture is timestamped when it happens, never backdated. One highest-edge quote per selection is frozen, including negative/zero edges. The ledger includes only selections whose unrounded edge was strictly positive **at first evaluable capture**. Missing probabilities in an already frozen record are never filled from later predictions. This avoids retrospective selection bias. Existing DraftKings-only snapshots are preserved, including their exclusions; they are not converted to Best Book retroactively. The snapshot note and book identify provenance. Prior records are not backfilled from current models or from legacy `Opening ... Edge` fields.

Spread and total probabilities use the CBB lookup tables at the captured book line, using that capture's rounded weighted Combo prediction and category. Moneyline uses the weighted Combo win probability. Edge = model probability − implied probability of the captured odds. The live market and Best Book columns continue to update; this ledger retains only its first evaluable Best Book capture.

## Files

- `data/cbb_opening_snapshots.csv`: authoritative frozen snapshots and current results for all captured selections.
- `data/cbb_opening_ledger.csv`: positive-edge selections only; derived from snapshots.
- `data/cbb_opening_scores.json`: cached completed score responses, keyed by API event ID.
- `docs/cbb_opening_snapshots.csv`, `docs/cbb_opening_ledger.csv`: public downloadable copies.
- `docs/cbb_opening_results.json`: page payload with details, market summaries, and tier summaries.

Do not delete the authoritative snapshot CSV; the tracker would regard selections as new. Ledger/JSON can be regenerated from snapshots and score cache. Opening fields are immutable; grading fields can update when the score provider corrects a final.

The model board does not link to this validation page. The direct GitHub Pages URL is still public; removing navigation is not access control.

## Automated grading

`.github/workflows/cbb-results.yml` checks The Odds API scores every 30 minutes at :17 and :47, independently of scraper success. It requires the existing `ODDS_API_KEY` secret. It requests three days of recent scores, caches completed responses, and matches exact event ID and home/away identities. Final scores include overtime. A spread uses team final margin + captured handicap; Over/Under use combined final points vs captured total. A tie with the captured line is Push. An incomplete/unmatched/canceled/postponed game remains Pending; never guess or silently mark it a loss.

Both workflows use the same concurrency group to serialize CSV writes. Grade failures retain existing results, publish the failure status when possible, and mark the workflow failed. Pending outcomes older than the score provider's recent window need review/import after prolonged downtime. This record makes no cancellation/refund assumption.

For score recovery, supply completed score objects in the official Odds API schema (`id`, `home_team`, `away_team`, `completed`, `scores` with team `name` and `score`), then run:

```sh
python src/utils/track_opening_results.py --grade --scores-json recovered_scores.json
```

Review and commit the resulting `data/cbb_opening_*` and `docs/cbb_opening_*` files. Do not manufacture an old opening snapshot during recovery. Scores without a genuine recorded snapshot do not create bets.

## Reports

Tiers use raw decimals without rounding: `0 < edge < .01`, `.01 <= edge < .03`, `.03 <= edge < .06`, `.06 <= edge`. The third tier is labelled **3–5.9%** to cover the gap between the requested “3–5%” and “6%+” buckets. The first two labels are shorthand too; all boundaries are explained on the page.

Win rate = Wins / (Wins + Losses). Pushes and Pending are separate. Net units assume one unit risked per selection and actual captured American odds: positive odds win `odds/100`, negative odds win `100/abs(odds)`, losses −1, pushes 0. Reports describe hypothetical model selections, not bets placed.

Tests: `uv run --with pandas python -m unittest discover -s tests -p 'test_opening_results.py' -v`.
