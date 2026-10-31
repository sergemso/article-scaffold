---
id: related-targets-are-public
title: A related_identifiers target must be a DOI or a public URL
status: active
date: 2026-10-31
tags: [metadata, zenodo, privacy, guardrail]
governed-by: 0064-validated-related-identifiers
grounded-in: [0064-validated-related-identifiers, 0002-zenodo-github-integration-constraints, 0059-public-companion-repo-per-article]
derivation-note: Given a published Zenodo version is permanent (0002) and article repos are private (0059), a link to a private repo would publish a dead or revealing address forever.
---

## Guardrail

`validate_metadata` rejects any `related_identifiers` entry whose scheme is not `doi` or `url`, whose relation is outside the curated set, or whose URL points at a repository of the articles org other than a companion. Enforced by tests in `tests/test_metadata_v2.py`.
