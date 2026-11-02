---
id: 0067-claim-checks-are-tiered-and-local
title: Claim-versus-source checks run as script, then small-model excerpt judgment, then human attestation, all on local text
status: active
date: 2026-11-02
tags: [theses-map, sources, cost, privacy]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

Checking that the paper represents a source correctly has three tiers. Tier 1 is a script that confirms a `source-claim` node's verbatim quote exists at its locator in the local source text (under `paper/sources/`). Tier 2 gives only that excerpt and the paper's claim wording to a small model, which answers `supports`, `overstates` or `contradicts`. Tier 3 is a human attestation recorded in the map (who, when, why), as scholar-mcp does for references. Results are cached against the hash of the claim text and the excerpt. Source and manuscript text are never sent to any outbound service.

## Why

Bibliographic checks (scholar-mcp) prove a work exists, not that it says what the paper claims. Deterministic matching alone catches fabricated quotes but not distortion. Reading whole sources per claim costs tokens in proportion to source length times claims.

## Consequence

Cost scales with the number of claims, not source length. A source with no local text cannot pass tier 1; it is listed, not guessed. Third-party source texts keep their own terms (see the repo's sources notice).
