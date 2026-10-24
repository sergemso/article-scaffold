---
id: egress-allowlist
title: Outbound requests carry only identifiers and search strings, to allowlisted hosts
status: active
date: 2026-10-24
tags: [security, egress, guardrail]
governed-by: 0004-egress-identifiers-and-search-strings-only
grounded-in: [0004-egress-identifiers-and-search-strings-only]
derivation-note: Given that only identifiers and search strings may leave (0004), the HTTP client must reject any other payload, host or off-list redirect.
go-getter:
  enforcement:
    - tier: 3
      check: CI runs tests that the client refuses non-allowlisted hosts, HTTP, off-list redirects and manuscript-sized payloads
      run: python -m pytest tests/guardrails/test_egress.py -q
---

## Guardrail

Requests use HTTPS to the allowlisted registry hosts only, with the payload limited to identifiers and short search strings. Manuscript text never goes into a request. Changing the allowlist needs a decision.
