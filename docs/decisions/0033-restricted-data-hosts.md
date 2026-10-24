---
id: 0033-restricted-data-hosts
title: Restricted data is handled only on hosts with a blocking pre-tool hook
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  restricted-data-hosts:
    rule: blocking-hook
  generated-by: restricted-data@0.6.0
  pack-answer: restricted-hosts
  pack-option: hook-hosts
---

## Decision

Only host agents with a blocking pre-tool hook handle restricted data; `go-getter coverage` shows each host's tier for guardrails and DLP (pack restricted-data@0.6.0).

## Why

Where a host cannot block, DLP is advisory (decision 0018).
