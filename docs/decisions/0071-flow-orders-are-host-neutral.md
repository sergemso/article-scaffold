---
id: 0071-flow-orders-are-host-neutral
title: The lifecycle is driven by work orders from the vendored CLI, served over MCP by scholar-authors, and bound to no agent host
status: active
date: 2026-11-02
tags: [orchestration, architecture, scholar-mcp, host-neutral]
track: process
accepted-by: Sergey Strebulaev
governed-facts: [0007-go-getter-is-maintainer-tooling]
---

## Decision

`article flow status`, `flow next` and `flow done <order-id>` live in the vendored CLI (`scripts/article`, JSON-first). `flow next` prints one JSON work order: stage, node ids to read, allowed outputs, a tier hint (`script`, `small`, `large`), a procedure reference and the name of a check. Whoever executes it, a person or any agent host, closes it with `flow done`, which runs the named check and records the result only if it passes. `scholar-authors` exposes the same three operations as MCP tools, a thin wrapper with closed schemas and fixed argument vectors (scholar-mcp decision 0070). Orders name no model and no host.

## Why

Gates enforced by the CLI cannot be skipped by prose, and humans, CI and hosts without MCP can all call it. MCP adds a uniform call, an audit log, a path guard and out-of-band confirmation. A CLI that calls a model API itself was rejected: it needs keys and a network path and duplicates what hosts do. Per-host skills were rejected: they lock the logic to one host. go-getter plans were rejected as the engine: go-getter is maintainer tooling, not shipped (fact 0007).

## Consequence

An autonomous multi-step run is the host's loop, not the CLI's. Partly supersedes decision 0068, which kept map operations out of MCP: orchestration is the case where MCP earns its schema cost, and only three small tools are added.
