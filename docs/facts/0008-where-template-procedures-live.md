---
id: 0008-where-template-procedures-live
title: Agent procedures ship as plain markdown under docs/procedures/; host files are thin pointers
status: active
date: 2026-11-02
tags: [template, procedures, host-neutral, upgrade]
---

## Fact

Established from `{{cookiecutter.repo_name}}/scripts/article/upgrade.py`, `{{cookiecutter.repo_name}}/companion.yaml` and fact 0007 on 2026-11-02.

**Neutral procedures path.** `docs/procedures/<name>.md` in the article repo, one file per procedure (`red-team.md`, `blue-team.md`, `claim-check.md`). Plain markdown, under 150 lines, naming the CLI commands it uses and nothing host-specific. Work orders (decision 0071) reference a procedure by this path. The template already has a `docs/` directory (`cli.md`, `companion.md`, `metadata.md`), and `companion.yaml` excludes `docs/**`, so procedures never reach the public companion.

**Adapter locations.** Two, both thin and free of logic:

- `.claude/skills/<name>/SKILL.md` for hosts that load skills: frontmatter (`name`, `description`) and one sentence telling the agent to follow `docs/procedures/<name>.md`. `companion.yaml` already excludes `.claude/**`.
- `AGENTS.md` at the repo root: the pointer line below. Most agent hosts read this file.

**Upgrade ownership.** `upgrade` renders the old and the new template, diffs the two trees and applies the patch with a three-way merge. A file is therefore template-owned unless it is listed as owned. The rule in `upgrade.py`:

```
# Files the template adds once and the author owns afterwards: later template edits are skipped.
_OWNED_AFTER_ADD = ("companion.yaml",)
```

- `docs/procedures/*.md` and `.claude/skills/*/SKILL.md` are template-owned: `upgrade` adds them when absent and merges later changes. An author who edits one gets a conflict to resolve, which is intended for procedures.
- `AGENTS.md` is author-owned after the first add (the author appends their own instructions), as is `theses.yaml` (the map is data). Both must be added to `_OWNED_AFTER_ADD` (plan step 5.1). Until then an upgrade would text-merge into them.
- An existing file with different content is never overwritten on an add (`exists locally with different content; merge it by hand`).

**Pointer text for an instruction file** (`AGENTS.md`, or any host's equivalent):

```
Procedures for argument and source checks are in docs/procedures/. Read the one a work order names; do not read article.tex or whole sections, use `python3 -m scripts.article index` and `theses slice`.
```

## Consequence

Steps 3.2 to 3.4 write `docs/procedures/{red-team,blue-team,claim-check}.md` plus the matching `.claude/skills/` adapters, and add `AGENTS.md` with the pointer. A scan that fails on the string go-getter, on model names, and on host-specific paths outside `.claude/` and `AGENTS.md` enforces guardrail `article-tooling-is-host-neutral`.
