---
id: verification-gate-blocks-done
title: A step is not done while its verification checks fail
status: active
date: 2026-10-24
tags: [practice-packs, verification, guardrail]
governed-by: 0055-verification-gate
grounded-in: [0055-verification-gate]
derivation-note: Given the quality bar of routing is the verification checks (0016, 0031), completion must wait for them, since an instruction alone lets a failing step end.
go-getter:
  enforcement:
    - tier: 1
      check: Run `go-getter verify --class implement` before reporting a step done
    - tier: 2
      check: Stop hook keeps the agent working while the checks fail, bounded by the escalation limit
      run: builtin:verify-gate
  generated-by: verification-gate@0.4.0
  pack-answer: gate
  pack-option: block
---

## Guardrail

Before reporting an implement or debug step done, run `go-getter verify --class <class>` and fix every failure; on a pushed branch, wait for CI with `go-getter watch --until done -- go-getter ci status --wait` and fix every red job. Where the host supports it, a stop hook enforces this and hands over to a human after the escalation limit.
