# E.4: keyword search is enough; no virage, B.4 not started

Date: 2026-11-08. Plan step: E.4 of `docs/plans/token-economy-ledger.md`.

## Decision

Keyword search (`sources find`, B.3) is enough for the source set of the bridge-contract article. Do not install virage and do not build the locator adapter (B.4 is marked `[>]`, skipped). Reopen only if a reader-side miss shows up that a second keyword query cannot recover.

The retrieval prompt hook is absent: `inject-context` appears in no settings file of the article repo (`.claude/settings.local.json` is the only file there) nor in the scaffold template (`{{cookiecutter.repo_name}}/.claude/` holds only `skills/`), and not in `~/.claude/settings.json`. The only scaffold file that contains the string is the plan itself.

## Method

Root: `articles.bridge_contract_for_agent_session_governance`, branch `upgrade/44076df7`, read only (`git status` clean before and after). Command: `python -m scripts.article --root <repo> sources find ...` run from the scaffold worktree. The store holds eleven sources (nine IETF drafts, one arXiv paper, one product page), all searched, none skipped.

Queries were formed by one person (the agent), from the six `source-claim` nodes in `theses.yaml` and from the paper sentences in `paper/sections/02_related_work.tex` that cite the drafts. The wanted address was judged by reading the slice. This is a small sample with a single judge; it is evidence for "enough", not a measurement.

## Evidence

Rank is the position of the wanted address in the output; `n` is the `total` the command reported.

| Query | Reader wants | Result |
|---|---|---|
| `Session-ID header` | AGTP `para:236` (node `sc-agtp-session-id`) | hit, rank 2 of 4 (a table row ranks first) |
| `Authority-Scope` | AGTP `para:80` (node `sc-agtp-authority-scope`) | weak, rank 9 of 67; hit at rank 1 with `declared set of permissions` |
| `SUSPEND resumption nonce` | AGTP SUSPEND method text | hit, rank 1 |
| `single-use nonce invalidated` | the sentence the paper quotes | hit, rank 1 (`para:842`) |
| `resume by reconnecting` | PACE `para:165` (node `sc-pace-resume`) | hit, rank 1 |
| `session recovery` | PACE section 4.5 | hit, rank 2 (table-of-contents line ranks first), n 27 |
| `SESSION_RESUME` | PACE registry row | hit, rank 1 |
| `persistent session identifier stable` | AGTP-Session `para:43` | hit, rank 1 |
| `audit artifacts generate` | GAR `para:44` (node `sc-gar-gec-generates`) | weak, rank 4 of 5 |
| `HEM_PENDING reject state transition` | HEM `para:442` | hit, rank 3 of 3 |
| `minimum 60 seconds` | HEM `para:469` (minimum timeout) | hit, rank 3 of 4 |
| `prev_hash canonical JSON` | Audit Trail `para:80` | hit, rank 1 |
| `tamper-evident` | Audit Trail chaining section | hit, rank 1 |
| `narrow waist` | AGTP `para:67` (hyphenated across a line) | hit, rank 1 |
| `Owner-ID` | AGTP `para:79` | hit, rank 1 |
| `timeout budget minimum` | HEM `para:469` | miss, 0 results (no paragraph holds all three terms); recovered by the row above |
| `Merkle chain tamper-evident` | GAR Merkle and chain text | miss, 0 results; `Merkle` and `hash chain` alone hit GAR |
| `auto-approve` | HEM `AUTO_APPROVE` (`para:475`) | miss, 0 results (underscore form); `auto approve` hits |
| `Ed25519 decision` | HEM decision verification (paper cites section 12.8) | miss, one result, a field list at `para:435` |
| `detach` | any text about detachment | miss, 15 results, none relevant (all `Detached-...` names) |
| `RESUME request message` | AGTP RESUME message | no address exists: the paper says that draft does not define it; zero results is the true answer |
| `client disconnects while agent continues` | a passage on bridge behaviour | no address exists (the paper claims absence); zero results |
| `human confirmation during pause` | a passage on held confirmations | no address exists (absence claim); zero results |

Tally: of the 20 queries whose wanted address exists, 15 found it (two of them weakly, at rank 4 or worse: `Authority-Scope`, `audit artifacts generate`) and 5 missed (`timeout budget minimum`, `Merkle chain tamper-evident`, `auto-approve`, `Ed25519 decision`, `detach`). The other 3 target claims of absence, where no retrieval index can return an address.

## Reading

The misses fall in three classes, and none needs embeddings:

1. All-terms matching: a long natural-language query fails when its terms sit in different paragraphs. A shorter query recovered every case tried.
2. Spelling variants: `auto-approve` against `AUTO_APPROVE`, and a word that the sources use only inside compound names (`detach`). The reader retries with the source's form.
3. Absence claims ("defines no handling of ..."): these cite no passage. What helps there is the claim-check procedure, not retrieval.

Ranking noise (table-of-contents lines and table rows ahead of the paragraph) cost one extra look at most. Every returned address resolved through `sources slice`.

Cost against the other side: an index adds a local embedder, a command taken from user configuration, and a hook that injects chunks on every prompt (fact 0010). The recorded misses do not justify any of that.

## Not done

No fresh-session check of hook injection was run, since nothing was installed. Query forming and judging were done by one agent; a second reader may find other misses.
