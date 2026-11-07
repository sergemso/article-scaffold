# Results ledger

Committed, append-only results of claim verdicts and declared checks, one file per
result at `docs/ledger/<kind>/<key[:2]>/<key>.json`. The key is a hash of every input
that can change the result, so a changed input is a miss, never a stale hit. Entries
hold hashes and verdicts, never source or manuscript text, and are not shipped to the
public companion.

Read and maintain it with `python3 -m scripts.article ledger` (`get`, `explain`,
`verify`, `evict`, `gc`, `stats`). Nothing writes an entry by hand: `claims` and `check`
record them. `ARTICLE_LEDGER=off` bypasses lookups while debugging.
