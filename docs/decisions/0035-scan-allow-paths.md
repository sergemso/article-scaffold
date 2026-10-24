---
id: 0035-scan-allow-paths
title: The secret scan skips a declared list of paths
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  scan-allow-paths: ""
  generated-by: sanitization@0.7.0
  pack-answer: scan-allow-paths
  pack-option: []
---

## Decision

The secret scan skips the paths  (pack sanitization@0.7.0); an empty list skips none.

## Why

Fixtures and documentation hold fake keys on purpose, and a path is easier to review than a marker on every line (decision 0106).
