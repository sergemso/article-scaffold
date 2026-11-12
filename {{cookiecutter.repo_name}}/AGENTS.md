# Agent instructions

Procedures for argument and source checks are in docs/procedures/. Read the one a work order names; do not read article.tex or whole sections, use `python3 -m scripts.article index` and `theses slice`.

To move the article forward, follow docs/procedures/lifecycle.md: run `python3 -m scripts.article flow next`, do the order, close it with `flow done`, and stop on a needs-human order.
Accepted items are frozen: never retire or rewrite what you did not write; a `flow done` that reports `ratchet:` means restore your own edits and report.

Before you read or run anything slow, ask the repo:
- Results: `python3 -m scripts.article ledger get ...` and `check NAME` return a stored verdict for unchanged inputs; run `check record NAME` only on a miss. `docs/ledger/` is committed and shared by every worktree.
- Sources: follow docs/procedures/reading-a-source.md. Run `sources list` first; never fetch or OCR a source that is stored; read only unread ranges with `sources slice KEY --pages A-B` or `sources find`; run `sources read` before you report. Code: `index slice NAME`.
- Orders: `flow next --brief` carries the finding, the slices and the one verify command. Stop at the order's `max_context` (when set) or `max_calls` and run `flow handoff <id> --file -`; the next agent resumes from it.
