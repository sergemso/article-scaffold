---
id: 0052-verification-coverage-bar
title: Coverage must meet what the coverage command enforces
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-coverage-bar: command
  generated-by: verification-gate@0.4.0
  pack-answer: coverage-bar
  pack-option: command
---

## Decision

The coverage check passes when the coverage command exits zero; the command holds the bar. (pack verification-gate@0.4.0).

## Why

Go-getter does not read coverage reports, so the bar is passed to the coverage command, which fails when the bar is missed; the check fails on a non-zero exit. A command that ignores the variables enforces only its own configuration.
