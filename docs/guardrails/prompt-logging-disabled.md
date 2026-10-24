---
id: prompt-logging-disabled
title: Host prompt logging must stay disabled
status: active
date: 2026-10-24
tags: [practice-packs, governance, guardrail]
governed-by: 0014-prompt-logging
grounded-in: [0014-prompt-logging]
derivation-note: Given host telemetry can export prompt content, a restricted path read once would leave the machine through logs, so the setting must be off wherever the host exposes it.
go-getter:
  enforcement:
    - tier: 3
      check: Host settings files that exist have prompt logging switched off
      run: builtin:prompt-logging-off
  generated-by: data-policy@0.6.0
  pack-answer: prompt-logging
  pack-option: disable-everywhere
---

## Guardrail

Keep prompt and content logging disabled in host settings; `go-getter apply` sets it and the check fails when a settings file turns it back on.
