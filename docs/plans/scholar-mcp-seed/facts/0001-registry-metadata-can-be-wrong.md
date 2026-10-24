---
id: 0001-registry-metadata-can-be-wrong
title: Registry metadata can itself be wrong, and some works have no persistent identifier
status: active
date: 2026-10-24
tags: [references, correctness]
kind: environmental
governed-by: 0002-bibliographic-fields-from-records-only
---

## Fact

Crossref, DataCite and OpenAlex contain errors (misspelled or truncated names, wrong author order, wrong venue or year, duplicated records). Books, theses, reports and web pages often have no DOI. Verification against a registry therefore shows traceability to a named record, not literal truth.

## Consequence

The honest guarantee is that every field traces to a named record and every mismatch is surfaced for a human (decisions 0002 and 0003).
