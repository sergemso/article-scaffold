# Agent instructions

Procedures for argument and source checks are in docs/procedures/. Read the one a work order names; do not read article.tex or whole sections, use `python3 -m scripts.article index` and `theses slice`.

To move the article forward, follow docs/procedures/lifecycle.md: run `python3 -m scripts.article flow next`, do the order, close it with `flow done`, and stop on a needs-human order.

Before you read or run anything slow, ask the repo:
- Results: `python3 -m scripts.article ledger get ...` and `check NAME` return a stored verdict for unchanged inputs; run `check record NAME` only on a miss. `docs/ledger/` is committed and shared by every worktree.
- Sources: `sources find` and `sources slice <key@hash#locator>` give one passage; never open a source file whole. Code: `index slice NAME`.
- Orders: `flow next --brief` carries the finding, the slices and the one verify command. Stop at the order's `max_calls` and run `flow handoff <id> --file -`; the next agent resumes from it.
