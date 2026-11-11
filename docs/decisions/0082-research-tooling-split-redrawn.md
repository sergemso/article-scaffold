---
id: 0082-research-tooling-split-redrawn
title: The vendored CLI owns everything derived and cached; scholar-mcp owns only what leaves the machine
status: active
date: 2026-11-07
tags: [architecture, scholar-mcp, theses-map, cost]
track: process
accepted-by: Sergei Strebulaev
governed-facts: [0006-scholar-mcp-checks-bibliographic-facts-only]
---

## Decision

Supersedes 0068.

- **Vendored CLI (`scripts/article`, JSON-first)** owns the section and code index, the source store operations after fetch, locator slicing, quote matching, the results ledger (0079), brief compilation (0081) and the flow.
- **scholar-mcp** owns registry lookups, discovery candidates, the allowlisted source fetch (its decision 0071) and the out-of-band confirmations. It holds no verdicts and no cache of derived results.
- **Procedures** stay host-neutral files loaded on demand (0002); host skills are thin adapters.
- **Retrieval** (virage or similar) is an optional adapter over the source store, per 0080.
- The flow tools in scholar-mcp (its 0070) remain thin wrappers; their schema cost is accepted only because gated stages need the out-of-band path.

## Why

0068 drew the line at "local work gains nothing from MCP", and kept discovery in scholar-mcp. The new need is a fetch-once source store: acquisition has to be allowlisted and logged, everything after it is deterministic and local. Placing the ledger in the CLI keeps the repo buildable with TeX and Python only.

## Consequence

0068's delivery by `upgrade` carries over. The two release trains still have to agree on the fetch tool name and the manifest format; the plan sequences them.
