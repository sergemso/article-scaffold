---
id: 0066-argument-agents-are-gap-driven-and-propose-only
title: Argument agents work on gaps found by a linter and only propose; a human promotes
status: active
date: 2026-11-02
tags: [theses-map, agents, cost, review]
track: process
accepted-by: Sergei Strebulaev
---

## Decision

A graph linter in the vendored CLI lists gaps: a thesis with no support, an objection with no defense, a claim resting on a single source, a node whose anchor label no longer exists. A red-team skill (objections, hypotheses) and a blue-team skill (defenses) each receive one gap and its neighbourhood and emit nodes with status `proposed`. Only a human sets `accepted`, with `accepted-by`. An agent doing review work stays read-only.

## Why

The linter costs no tokens and decides where a model is worth calling. Propose-only keeps the argument from drifting silently, in the spirit of scholar-mcp's out-of-band confirmation (its decision 0060). Direct writes reviewed in git were rejected because bad nodes accumulate between reviews. On-demand suggestions with no write were rejected because the same ground is re-derived every session.

## Consequence

A human step sits in the loop. Promotion needs a cheap command (`theses accept <id>`) or the loop stalls.
