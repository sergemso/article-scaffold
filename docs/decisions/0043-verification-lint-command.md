---
id: 0043-verification-lint-command
title: The verification lint command is "make lint"
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-lint-command: make lint
  generated-by: verification-gate@0.4.0
  pack-answer: lint-command
  pack-option: make lint
---

## Decision

Verification runs `make lint` for the lint check; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
