---
id: 0003-reference-sources-and-unverified-policy
title: The registry of record is authoritative; disagreements and unverified references block until a human decides
status: active
date: 2026-10-24
tags: [references, correctness]
track: product
accepted-by: Sergey Strebulaev
governed-facts: [0001-registry-metadata-can-be-wrong]
---

## Decision

The authoritative source is the identifier's own registry: the DOI's registration agency (Crossref or DataCite via doi.org content negotiation), the arXiv API, NCBI for PMIDs, the ORCID public API for people. OpenAlex and publisher pages are cross-checks only. If a cross-check disagrees with the record on title, authors, venue, year or DOI, the entry is blocked for human review; the server never picks a winner and never votes among sources.

A reference that cannot be verified (no identifier that resolves, a lookup failure, or a record that disagrees with what the author typed) is stored as `unverified`. Validation fails and release and deposit refuse until the author supplies an identifier that resolves or records an attestation (who, when, why) in the repository. Nothing is auto-corrected.

## Why

Majority voting among sources is a guess, which contradicts decision 0002. Rejecting unverifiable references outright would make books, theses and web sources uncitable. A blocking, auditable attestation keeps the human accountable for what the machine cannot prove.

## Consequence

Records for works without a persistent identifier always need a human decision. Attestations are part of the repository and show up in review.
