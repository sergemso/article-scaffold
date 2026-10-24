---
id: 0031-use-commands
title: The commands approved to receive a use path are listed
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  use-commands: ""
  generated-by: restricted-data@0.6.0
  pack-answer: use-commands
  pack-option: []
---

## Decision

Only the commands [] may receive a use path through `go-getter secret run`, each for its own pattern (pack restricted-data@0.6.0); with none listed `secret run` refuses every command.

## Why

Scrubbing an exact value cannot catch a re-encoded one, so a human decides which commands may hold a secret (decision 0107).
