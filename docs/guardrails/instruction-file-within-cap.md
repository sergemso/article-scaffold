---
id: instruction-file-within-cap
title: The instruction file must stay within 150 lines
status: active
date: 2026-10-24
tags: [practice-packs, harness, guardrail]
governed-by: 0001-instruction-file-cap
grounded-in: [0001-instruction-file-cap]
derivation-note: Given the cap decision, every line past it is paid on every request.
go-getter:
  enforcement:
    - tier: 3
      check: AGENTS.md line count within the cap
      run: builtin:file-max-lines path=AGENTS.md max=150
  generated-by: context@0.3.1
  pack-answer: instruction-cap
  pack-option: cap-150
---

## Guardrail

Keep `AGENTS.md` within 150 lines; move detail into skills.
