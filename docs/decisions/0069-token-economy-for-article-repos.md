---
id: 0069-token-economy-for-article-repos
title: Article repos use a section index, a hash-keyed check cache, tiered routing and verdict-only noisy work
status: active
date: 2026-11-02
tags: [cost, practice-packs, theses-map]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

- **Section index.** A script emits label to file:line plus a one-line summary per section. Agents read sections through it and never read `article.tex` whole.
- **Hash-keyed cache.** Claim checks, quote matches and summaries are cached against the content hash of their inputs; unchanged inputs are not re-checked.
- **Tier hints by step.** Quote matching and graph linting run as scripts (`script`); excerpt judgments use a small model (`small`); hypothesis and defense drafting use the larger one (`large`). Work orders carry the hint (decision 0071); it names no model and no host.
- **Verdict-only noisy work.** LaTeX builds, layout checks and model-checker logs return pass or fail and the failing lines only, from the CLI's own check commands; a host may also delegate them.

## Why

In a large paper the dominant cost is rereading prose; the index and cache remove it. Tier hints and verdict-only output are host-neutral, so they hold for any agent host (fact 0007). Clarified 2026-11-02: this decision first cited the maintainer's routing classes and delegation rules; those do not ship to article repos.

Clarified 2026-11-08: the cache clause ("Hash-keyed cache") is replaced by the committed results ledger of decision 0079; the section index, tier hints and verdict-only work stand. Section summaries are no longer cached at all (they are a deterministic heuristic).

## Consequence

The index must be regenerated when sections change (the pre-push hook and `make validate` do it). A stale index is a defect, not a cache miss.
