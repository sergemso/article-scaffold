---
id: 0042-verification-test-command
title: The verification test command is "make test"
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-test-command: make test
  generated-by: verification-gate@0.4.0
  pack-answer: test-command
  pack-option: make test
---

## Decision

Verification runs `make test` for the test check; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
