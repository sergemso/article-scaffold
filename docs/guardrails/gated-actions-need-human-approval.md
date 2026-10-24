---
id: gated-actions-need-human-approval
title: Irreversible commands need a human
status: active
date: 2026-10-24
tags: [practice-packs, hooks, guardrail]
governed-by: 0015-gated-actions
grounded-in: [0015-gated-actions, 0043-human-escalation]
derivation-note: Given agents must hand over before irreversible or outward-facing actions (0043), the host must ask a human or deny the command, since an instruction alone fails silently.
go-getter:
  enforcement:
    - tier: 2
      check: Host ask rules and the pre-tool hook gate these commands
      run: builtin:gate-command classes=irreversible extra=""
  generated-by: hitl@0.6.0
  pack-answer: gated-classes
  pack-option: irreversible
---

## Guardrail

Shell commands of the irreversible class need a human: do not run them yourself, ask the user to run them or approve them. Hosts with project ask rules prompt natively, because `go-getter apply` writes the rules into their settings. The other hosts get a hand-over: the pre-tool hook denies the command and the human runs it. `go-getter coverage` shows the tier per host. A mode that skips permission prompts defeats the native rules. A wrapped command (`sh -c`, `eval`) is matched on its literal text only.
