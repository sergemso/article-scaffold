---
id: 0045-verification-format-command
title: The verification format command is "ruff format --check ."
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-format-command: ruff format --check .
  generated-by: verification-gate@0.4.0
  pack-answer: format-command
  pack-option: ruff format --check .
---

## Decision

Verification runs `ruff format --check .` for the format check, where the machine profile places it; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
