---
id: theses-map-never-reaches-companion
title: The theses map, its check cache and the AI-use log never reach the public companion
status: active
date: 2026-11-02
tags: [companion, privacy, theses-map, guardrail]
governed-by: 0065-theses-map-is-a-yaml-graph
grounded-in: [0065-theses-map-is-a-yaml-graph, 0078-ai-use-is-logged-without-content, companion-publishes-allowlist-only]
derivation-note: Given the map holds unpublished objections and defenses (0065) and the AI-use log lists internal node ids (0078) and the companion is public and permanent once archived (fact 0002), the map must be a deny pattern, not merely absent from the allowlist.
go-getter:
  enforcement:
    - tier: 1
      check: Deny patterns for `theses.yaml`, `.theses/**` and `docs/provenance/**` in the template's `companion.yaml`, plus a snapshot test that fails when any is present.
---

## Guardrail

`theses.yaml`, the check cache directory and `docs/provenance/` are deny patterns in `companion.yaml`. The snapshot build fails, publishing nothing, if the result contains any of them.
