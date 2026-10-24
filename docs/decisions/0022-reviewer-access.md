---
id: 0022-reviewer-access
title: The reviewer reports findings and changes nothing
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  role-access:
    reviewer: read-only
  role-notes:
    reviewer: Do not modify files; report findings only.
  generated-by: orchestration@0.1.1
  pack-answer: reviewer
  pack-option: read-only
---

## Decision

The reviewer agent gets read-only access and reports findings only (pack orchestration@0.1.1).

## Why

The reviewer's independence is what makes its verdict worth a gate (decision 0013).
