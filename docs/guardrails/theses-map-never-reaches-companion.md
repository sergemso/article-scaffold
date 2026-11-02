---
id: theses-map-never-reaches-companion
title: The theses map and its check cache never reach the public companion
status: draft
date: 2026-11-02
tags: [companion, privacy, theses-map, guardrail]
governed-by: 0065-theses-map-is-a-yaml-graph
grounded-in: [0065-theses-map-is-a-yaml-graph, companion-publishes-allowlist-only]
derivation-note: Given the map holds unpublished objections and defenses (0065) and the companion is public and permanent once archived (fact 0002), the map must be a deny pattern, not merely absent from the allowlist.
go-getter:
  enforcement:
    - tier: 1
      check: Deny patterns for `theses.yaml` and `.theses/**` in the template's `companion.yaml`, plus a snapshot test that fails when either is present.
---

## Guardrail

`theses.yaml` and the check cache directory are deny patterns in `companion.yaml`. The snapshot build fails, publishing nothing, if the result contains either. Draft until the snapshot test exists.
