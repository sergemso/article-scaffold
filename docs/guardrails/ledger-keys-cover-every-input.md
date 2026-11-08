---
id: ledger-keys-cover-every-input
title: A ledger key hashes every input that can change the result
status: active
date: 2026-11-07
tags: [cost, ledger, guardrail]
governed-by: 0079-results-ledger-is-committed-and-hash-keyed
grounded-in: [0079-results-ledger-is-committed-and-hash-keyed]
derivation-note: Given the ledger serves stored results in place of a run or a model call (0079), a key that omits an input would serve a wrong result silently.
go-getter:
  enforcement:
    - tier: 1
      check: A test that, for each ledger kind, changes each declared input (file content, procedure version, tier, tool version) and fails unless the key changes.
---

## Guardrail

A ledger key is computed from the content of every input file or excerpt, the procedure or check version, the tier and the declared tool versions. A kind declares its inputs in one place; a result whose inputs are not all declared is not ledgered.
