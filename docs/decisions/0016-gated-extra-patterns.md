---
id: 0016-gated-extra-patterns
title: Project-specific commands that also need a human are listed
status: active
date: 2026-10-24
tags: [practice-packs, hooks]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  generated-by: hitl@0.6.0
  pack-answer: extra-patterns
  pack-option: []
---

## Decision

Commands matching the extra patterns [] also need a human, on top of the gated classes (pack hitl@0.6.0); an empty list adds none.

## Why

The catalog cannot know a project's own deploy or release commands, so the project names them (decision 0094).
