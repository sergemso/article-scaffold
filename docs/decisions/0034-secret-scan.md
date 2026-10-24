---
id: 0034-secret-scan
title: Secrets in added lines are scanned before a commit and a push
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: sanitization@0.7.0
  pack-answer: secret-scan
  pack-option: on
---

## Decision

A git hook before a commit, a git hook before a push and CI scan the lines a change adds for private keys, provider tokens, JWTs and labelled secret assignments, and fail with the file, line and kind (pack sanitization@0.7.0). A line marked `go-getter:allow-secret` and the paths  are skipped.

## Why

A credential that reaches a repository must be rotated, and a pattern scan on the lines being added stops it without reading history (decision 0106).
