---
id: 0006-scholar-mcp-checks-bibliographic-facts-only
title: scholar-mcp proves a reference exists and matches its record, not that the paper represents it correctly
status: active
date: 2026-11-02
tags: [scholar-mcp, sources, coverage]
---

## Fact

Read from `/home/sergei/projects/sergemso/scholar-mcp` on 2026-11-02 (authors tools in `packages/authors/src/scholar_authors/`, reviewers in `packages/reviewers/`, registries in `packages/core/src/scholar_core/sources.py`).

| Need | Covered | By |
|---|---|---|
| Work exists at its registry; fields match | Yes | `verify_bibliography`, `check_references` (Crossref, DataCite, doi.org, arXiv, PubMed, OpenLibrary; OpenAlex as cross-check) |
| Retraction or expression of concern | Yes | `verify_bibliography`, `check_references` |
| Record drift since storage | Yes | stored hash, nightly corpus run |
| Add a reference without model-written fields | Yes | `search_candidates`, `plan_add_reference` |
| Release and deposit gating on unverified references | Yes | `plan_release`, `apply_release`, `plan_attestation` |
| Does the cited source say what the paper claims | **No** | out of scope by decision 0059 |
| Quote or locator verification | **No** | |
| Prior art, related works, cited-by, citation graph | **No** | `search_candidates` is title/author lookup only |
| Hypotheses, theses map, offense and defense | **No** | |

The authors server fails to connect in an article repo whose `.mcp.json` names a checkout path that does not exist on the host (seen as EACCES on `/home/ubuntu/...` on 2026-11-02).
