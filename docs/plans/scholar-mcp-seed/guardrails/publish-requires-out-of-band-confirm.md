---
id: publish-requires-out-of-band-confirm
title: Writes and publish need a single-use, hash-bound out-of-band confirmation
status: active
date: 2026-10-24
tags: [security, confirmation, release, guardrail]
governed-by: 0005-out-of-band-confirmation-and-publish
grounded-in: [0002-zenodo-publish-mints-permanent-doi, 0005-out-of-band-confirmation-and-publish]
derivation-note: Given that publish mints a permanent DOI (fact 0002) and the model must not confirm itself (0005), every write and publish must consume a fresh token bound to the shown content hash.
go-getter:
  enforcement:
    - tier: 3
      check: "CI runs refusal-path tests (stale token, wrong hash, replayed token, path escape, missing confirmation, and publish defaulting to the sandbox)"
      run: python -m pytest tests/guardrails/test_confirmation.py -q
---

## Guardrail

A write or publish runs only after the human confirms the exact content in a terminal the model cannot drive. Tokens are single-use, expire and are bound to the content hash. Publish defaults to the Zenodo sandbox.
