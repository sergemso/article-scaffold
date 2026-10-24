---
id: 0002-bibliographic-fields-from-records-only
title: Bibliographic fields come only from authoritative records, never from the model
status: active
date: 2026-10-24
tags: [references, correctness]
track: product
accepted-by: Sergey Strebulaev
governed-facts: [0001-registry-metadata-can-be-wrong]
---

## Decision

No tool accepts a title, author list, venue, year, publisher or DOI as input to write into a bibliography. A tool accepts an identifier (DOI, ISBN, arXiv id, PMID, ORCID) and the server fetches the record from its registry of record (decision 0003). Every field of a generated entry is copied verbatim from that record, and the entry carries provenance: source, retrieval time and a hash of the record. Anything that cannot be fetched is not added.

## Why

The product promise is that a reference the server adds is never invented, mis-attributed or misspelled. A language model can produce a plausible but false citation; if it cannot supply field values, it cannot introduce that error. Registry errors remain possible (fact 0001), which is why provenance is kept and verification can be repeated.

## Consequence

Search by title or author returns candidate records only (decision 0004). Formatting a record into BibTeX is deterministic code covered by the golden corpus (decision 0006), not model output.
