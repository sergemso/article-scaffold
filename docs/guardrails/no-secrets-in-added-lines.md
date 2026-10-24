---
id: no-secrets-in-added-lines
title: Added lines must not contain secrets
status: active
date: 2026-10-24
tags: [practice-packs, governance, security, guardrail]
governed-by: 0034-secret-scan
grounded-in: [0034-secret-scan, 0106-scanning-and-masking-share-one-pattern-library]
derivation-note: Given a committed credential must be rotated (0106), the lines a change adds must be checked for secrets before they leave the machine.
go-getter:
  enforcement:
    - tier: 3
      check: No added line holds a private key, provider token, JWT or labelled secret
      run: builtin:secret-scan allow=""
      stages: [pre-commit, pre-push]
    - tier: 1
      check: Never paste a credential into a file; refer to it by environment variable name
  generated-by: sanitization@0.7.0
  pack-answer: secret-scan
  pack-option: on
---

## Guardrail

Added lines carry no private keys, provider tokens, JWTs or `password = <value>` assignments. A false positive is marked with `go-getter:allow-secret` on its line, or its path is added to the skipped paths (). A leaked secret must be rotated; deleting the commit is not enough.
