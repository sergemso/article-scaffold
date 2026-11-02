---
id: 0068-research-tooling-split
title: Map, index, quote-match and cache ship in the vendored CLI; discovery extends scholar-authors; agent procedures are skills
status: active
date: 2026-11-02
tags: [theses-map, architecture, scholar-mcp, upgrade]
track: process
accepted-by: Sergey Strebulaev
governed-facts: [0006-scholar-mcp-checks-bibliographic-facts-only]
---

## Decision

- **Vendored CLI (`scripts/article`, JSON-first).** `theses` (lint, slice, gaps, accept), the section index, quote match and the check cache. Delivered to new repos by the template and to existing repos by `upgrade`; repos that predate the upgrade path adopt it through `scripts/bootstrap-upgrader.py`.
- **scholar-mcp.** Read-only discovery (related works, cited-by, venue search) is added to the authors server (scholar-mcp decision 0069). It stays candidate-only with a human pick. Claim checking stays out of scholar-mcp (its decision 0059).
- **Procedures.** Red-team, blue-team, hypothesis and claim-check procedures are host-neutral files in the template, referenced by work orders and loaded on demand (decision 0002); host-specific skills are thin adapters only (guardrail `article-tooling-is-host-neutral`).
- **Scaffold workflows.** `track-articles` reports map gaps across a series. The map stays out of the companion (guardrail `theses-map-never-reaches-companion`).

## Why

Local deterministic work gains nothing from MCP and each MCP tool costs schema tokens every session. Discovery is the case that needs scholar-mcp's egress allowlist, provenance and threat model. Putting discovery in the CLI would bypass them. A separate role server was rejected for now: a new package, threat-model rows and corpus for a small tool set.

## Consequence

Clarification (2026-11-02): the rationale that map operations gain nothing from MCP holds for slicing, linting and quote matching, but not for orchestration. Decision 0071 serves the lifecycle flow over MCP through scholar-authors as a thin wrapper over the same CLI.

Two release trains (scaffold and scholar-mcp) must agree on the discovery tool names; the plan sequences them. If the discovery tool set grows, revisit a separate role server.
