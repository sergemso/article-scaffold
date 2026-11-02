---
id: agent-nodes-need-human-promotion
title: A map node written by an agent is not accepted until a human accepts it
status: draft
date: 2026-11-02
tags: [theses-map, agents, guardrail]
governed-by: 0066-argument-agents-are-gap-driven-and-propose-only
grounded-in: [0066-argument-agents-are-gap-driven-and-propose-only]
derivation-note: Given agents only propose (0066), a node with status accepted and no accepted-by means an agent promoted its own work.
go-getter:
  enforcement:
    - tier: 1
      check: The theses schema and linter fail validation when a node has status accepted and no accepted-by, or when accepted-by names an agent role.
---

## Guardrail

Validation fails on any `accepted` node without `accepted-by` naming a person. The check runs in `make validate` and the pre-push hook. Draft until the linter exists.
