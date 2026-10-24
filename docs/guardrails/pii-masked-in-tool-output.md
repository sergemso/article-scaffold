---
id: pii-masked-in-tool-output
title: Personal data is masked in tool output
status: active
date: 2026-10-24
tags: [practice-packs, governance, security, guardrail]
governed-by: 0036-pii-masking
grounded-in: [0036-pii-masking, 0106-scanning-and-masking-share-one-pattern-library]
derivation-note: Given the agent must not read personal data it does not need (0106), tool output that carries it must be masked before the agent sees it, where the host allows.
go-getter:
  enforcement:
    - tier: 2
      check: The post-tool hook masks email, card numbers, IBANs and the listed types in tool output
      run: builtin:redact-pii classes="email,card,iban,"
    - tier: 1
      check: Do not paste personal data into prompts or files; a prompt and a file write are never masked
  generated-by: sanitization@0.7.0
  pack-answer: pii-masking
  pack-option: on
---

## Guardrail

Tool output that carries email addresses, card numbers or IBANs (and []) reaches the agent with each value replaced by a per-session name. Hosts that cannot replace tool output show it unmasked (the coverage report lists them); prompts and file writes are never masked, so personal data is not pasted into either.
