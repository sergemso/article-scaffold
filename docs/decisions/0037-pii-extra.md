---
id: 0037-pii-extra
title: The locale-bound types masked in tool output are listed
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  pii-extra: ""
  generated-by: sanitization@0.7.0
  pack-answer: pii-extra
  pack-option: []
---

## Decision

The types masked in addition to email, card numbers and IBANs are [] (pack sanitization@0.7.0); an empty list adds none.

## Why

Phone and national-id formats are locale-bound and match ordinary numbers, so the project opts in (decision 0106).
