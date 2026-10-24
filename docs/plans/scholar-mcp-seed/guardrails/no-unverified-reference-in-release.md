---
id: no-unverified-reference-in-release
title: A release or deposit refuses while any reference is unverified or unattested
status: active
date: 2026-10-24
tags: [references, release, guardrail]
governed-by: 0003-reference-sources-and-unverified-policy
grounded-in: [0003-reference-sources-and-unverified-policy, 0001-registry-metadata-can-be-wrong]
derivation-note: Given that unverifiable references block until a human attests (0003) and registries can be wrong (fact 0001), release must fail on any reference that is neither verified nor attested.
go-getter:
  enforcement:
    - tier: 3
      check: CI runs a test that release plan and apply exit non-zero for an unverified entry, a source disagreement and an attestation missing who, when or why
      run: python -m pytest tests/guardrails/test_release_gate.py -q
---

## Guardrail

Release plan, apply and deposit refuse while a reference is unverified, disagrees with a cross-check, or has an attestation without who, when and why. Nothing is auto-corrected.
