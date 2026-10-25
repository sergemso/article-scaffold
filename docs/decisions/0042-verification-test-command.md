---
id: 0042-verification-test-command
title: The verification test command is "sh .github/scripts/install-tex.sh && make setup test"
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-test-command: sh .github/scripts/install-tex.sh && make setup test
  generated-by: verification-gate@0.4.0
  pack-answer: test-command
  pack-option: sh .github/scripts/install-tex.sh && make setup test
---

## Decision

Verification runs `sh .github/scripts/install-tex.sh && make setup test` for the test check; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
