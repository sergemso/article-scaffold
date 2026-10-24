---
id: bib-fields-from-records-only
title: Bibliography fields are copied from a fetched record, never supplied by the model
status: active
date: 2026-10-24
tags: [references, guardrail]
governed-by: 0002-bibliographic-fields-from-records-only
grounded-in: [0002-bibliographic-fields-from-records-only, 0001-registry-metadata-can-be-wrong]
derivation-note: Given that fields must come only from authoritative records (0002) and registries can still be wrong (fact 0001), every written field must trace to a stored record with its hash.
go-getter:
  enforcement:
    - tier: 3
      check: CI runs a test that every field of every generated entry equals the stored source record, and that no tool schema accepts bibliographic field values
      run: python -m pytest tests/guardrails/test_records_only.py -q
---

## Guardrail

No tool takes a title, author, venue, year, publisher or DOI as a value to write. Every entry field equals the stored source record and carries source, retrieval time and hash. A record that cannot be fetched is not added.
