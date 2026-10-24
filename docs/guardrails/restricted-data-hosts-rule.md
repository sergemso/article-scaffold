---
id: restricted-data-hosts-rule
title: Restricted data is handled only on hosts with a blocking pre-tool hook
status: active
date: 2026-10-24
tags: [practice-packs, governance, guardrail]
governed-by: 0033-restricted-data-hosts
grounded-in: [0033-restricted-data-hosts]
derivation-note: Given DLP must not depend on agent compliance (0018), only hosts whose hook can block may be near restricted data.
go-getter:
  enforcement:
    - tier: 1
      check: Instruction; the coverage report shows the tier per host
  generated-by: restricted-data@0.6.0
  pack-answer: restricted-hosts
  pack-option: hook-hosts
---

## Guardrail

Handle restricted data only in host agents with a blocking pre-tool hook. Advisory (tier 1): `go-getter coverage` shows where DLP is only advisory.
