---
id: 0036-pii-masking
title: Personal data in tool output is masked with per-session pseudonyms
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: sanitization@0.7.0
  pack-answer: pii-masking
  pack-option: on
---

## Decision

Where the host can replace tool output, the post-tool hook replaces email addresses, payment card numbers and IBANs, and the types in [], with names such as `[email-1]`: the same value keeps its name within a session (pack sanitization@0.7.0). Secrets keep the single marker `[redacted by go-getter]`.

## Why

An agent that does not need personal data should not read it, and a stable name lets it tell two values apart (decision 0106).
