---
id: 0059-public-companion-repo-per-article
title: Each private article repo has a public companion holding an allowlisted snapshot per release
status: active
date: 2026-10-29
tags: [companion, zenodo, release, privacy]
track: product
accepted-by: Sergey Strebulaev
---

## Decision

Scaffolded article repos are private. Each has one public companion repo, named `<repo_name>.public` unless `companion.yaml` says otherwise. The companion is where Zenodo's GitHub integration (fact 0002) reads releases.

- **Content:** a reproducible snapshot built from an allowlist in `companion.yaml`: paper sources, the built PDF and DOCX, data, analysis, schemas, licence, `CITATION.cff`, `.zenodo.json`, README and CHANGES. Drafts, plans, agent configuration and tooling stay private. Deny patterns beat the allowlist.
- **History:** one commit per release, `release vX.Y.Z`, on the companion's branch, tagged `vX.Y.Z`. Private history is never replayed.
- **URLs:** when `companion.yaml` exists, `_repo_url` is the companion URL, so `CITATION.cff` and the README citation point at a repo readers can open (fact 0003).

## Why

Zenodo needs a public repo, and the article repos stay private to hold drafts. A snapshot per release keeps version lineage intact (every tag resolves to a real commit) and leaks nothing between releases. Rejected: a built-artifacts-only companion (not reproducible, so a weak archive), a full mirror (publishes drafts and agent files), a single force-pushed orphan commit (earlier tags orphaned, which breaks Zenodo versions), and replaying filtered history (commit messages leak).

## Consequence

Two repos per article, and a fix to published content is a new release. Authors own `companion.yaml` after first render and must extend the allowlist for extra files.
