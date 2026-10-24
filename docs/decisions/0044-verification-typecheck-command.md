---
id: 0044-verification-typecheck-command
title: The verification typecheck command is ""
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-typecheck-command: ""
  generated-by: verification-gate@0.4.0
  pack-answer: typecheck-command
  pack-option: ""
---

## Decision

Verification runs `` for the typecheck check; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
