---
id: 0028-restricted-paths
title: Restricted data lives at a declared list of paths
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  restricted-paths: .env, .env.*, *.pem, *.key, id_rsa, id_ed25519
  generated-by: restricted-data@0.6.0
  pack-answer: restricted-paths
  pack-option: [.env, .env.*, "*.pem", "*.key", id_rsa, id_ed25519]
---

## Decision

The restricted data class is the paths .env, .env.*, *.pem, *.key, id_rsa, id_ed25519 (pack restricted-data@0.6.0). Agents do not read or write them, and only a local model may receive their content.

## Why

DLP needs a declared list that hooks and CI can enforce (decision 0018).
