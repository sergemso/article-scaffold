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
2. Check `companion.yaml` lists `theses.yaml` and the cache directory as deny patterns. Run the companion dry run and read the file list.
3. Fix `.mcp.json`: `command` and `SCHOLAR_REPO_ROOT` must be absolute paths that exist on this host. Restart the host and confirm `scholar-authors` connects.
4. Build the section index and read it instead of `article.tex`.
5. Seed `theses.yaml` from the paper's own claims and from existing notes (for example an enemies list or review-response plans), with every node `proposed`.
6. Run the gap linter, then work gaps one at a time with the red-team and blue-team skills. Accept nodes yourself with `theses accept <id>`.
7. Run `make validate`; fix schema errors before committing.
