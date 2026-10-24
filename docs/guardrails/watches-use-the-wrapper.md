---
id: watches-use-the-wrapper
title: Watches start through go-getter watch, --until done for CI runs and long commands
status: active
date: 2026-10-24
tags: [practice-packs, harness, guardrail]
governed-by: 0006-watcher-noise
grounded-in: [0006-watcher-noise]
derivation-note: Given the noise decision, a watch started outside the wrapper is not throttled.
go-getter:
  enforcement:
    - tier: 1
      check: Where no hook wraps the watch, start it through `go-getter watch`
    - tier: 2
      check: Pre-tool hook wraps the host watcher command in `go-getter watch` where the host allows
      run: builtin:wrap-watch
  generated-by: context@0.3.1
  pack-answer: watcher-noise
  pack-option: quiet
---

## Guardrail

Start watches through `go-getter watch`; use `--until done` for CI runs and long commands. Where the host allows, the pre-tool hook wraps the watch command.
