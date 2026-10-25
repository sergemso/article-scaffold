---
id: 0047-verification-build-command
title: The verification build command is "python -m pip install build && python -m build"
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-build-command: python -m pip install build && python -m build
  generated-by: verification-gate@0.4.0
  pack-answer: build-command
  pack-option: python -m pip install build && python -m build
---

## Decision

Verification runs `python -m pip install build && python -m build` for the build check, where the machine profile places it; an empty command skips it (pack verification-gate@0.4.0).

## Why

The command is project-specific, so it is recorded as an answer rather than guessed at run time.
