---
id: 0021-agent-roster
title: Work is delegated to implementer and reviewer agents
status: active
date: 2026-10-24
tags: [practice-packs, agent-roles, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  roles:
    - id: implementer
      description: Makes the change a brief describes and runs the project checks.
      task-class: implement
      access: write
      instructions: Make the change the brief describes, nothing more. Run the project's checks before you report.
    - id: reviewer
      description: Reviews a change against the brief, decisions and guardrails and reports findings by severity.
      task-class: review
      access: read-only
      instructions: Review the change against the brief and the project's decisions and guardrails. Report findings by severity, each with file and line; say so when there are none.
  generated-by: orchestration@0.1.1
  pack-answer: roster
  pack-option: implementer-reviewer
---

## Decision

Delegate work to these agent roles: implementer (implement), reviewer (review); the parenthesis is the routing task class. `go-getter apply` compiles them into each host agent's native format. (pack orchestration@0.1.1).

## Why

Separate roles are the routing lever and keep verification independent of implementation (decisions 0014, 0016).
