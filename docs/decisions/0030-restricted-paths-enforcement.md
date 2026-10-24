---
id: 0030-restricted-paths-enforcement
title: Restricted paths are blocked in the host and never committed
status: active
date: 2026-10-24
tags: [practice-packs, governance, enforcement]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: restricted-data@0.6.0
  pack-answer: enforcement
  pack-option: hook-and-never-committed
---

## Decision

A host pre-tool hook blocks tool calls that touch a restricted path (tier 2) and CI and pre-push fail if one is tracked (tier 3) (pack restricted-data@0.6.0).

## Why

DLP must not depend on agent compliance (decisions 0009, 0018).
