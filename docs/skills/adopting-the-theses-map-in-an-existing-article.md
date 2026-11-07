---
id: adopting-the-theses-map-in-an-existing-article
title: Bring the theses map and research tooling into an existing article repo
status: active
date: 2026-11-02
tags: [theses-map, upgrade, procedural]
operationalizes: [theses-map-never-reaches-companion, agent-nodes-need-human-promotion]
---

## Procedure

1. In the article repo, start from a clean tree. Run `python3 -m scripts.article upgrade --plan`, read it, then `--apply`, resolve conflicts, `git add`, `--finish`. A repo that predates the upgrade path uses `scripts/bootstrap-upgrader.py` from the scaffold first.
2. Check `companion.yaml` lists `theses.yaml`, the cache directory, `paper/sources/**` and `docs/ledger/**` as deny patterns (the plan prints notices `N001` and `N002`; `upgrade` never edits that file). Run the companion dry run and read the file list.
3. Fix `.mcp.json`: `command` and `SCHOLAR_REPO_ROOT` must be absolute paths that exist on this host. Restart the host and confirm `scholar-authors` connects.
4. Build the section index and read it instead of `article.tex`.
5. Seed `theses.yaml` from the paper's own claims and from existing notes (for example an enemies list or review-response plans), with every node `proposed`.
6. Run the gap linter, then work gaps one at a time with the red-team and blue-team skills. Accept nodes yourself with `theses accept <id>`.
7. Bring in the results ledger and source store: the upgrade adds `docs/ledger/`, `.gitattributes` and an empty `paper/sources/manifest.json`. Run `sources add` for each source (it reads `MANIFEST.md` and keeps it) then `sources index`; commit `docs/ledger/` and the normalized texts. Run `claims quote-check --all` once so the old `.theses/claims-cache.json` verdicts move into the ledger, then delete that file (notice `N003`). Optional `max_calls`, `brief_bytes` and `group_size` in `flow.yaml` are shown as comments; your values are never changed.
8. Run `make validate`; fix schema errors before committing.
