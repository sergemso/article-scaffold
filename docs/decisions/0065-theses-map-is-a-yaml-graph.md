---
id: 0065-theses-map-is-a-yaml-graph
title: An article's argument is kept as one YAML graph with a JSON schema, read in slices
status: active
date: 2026-11-02
tags: [theses-map, argument, cost]
track: product
accepted-by: Sergey Strebulaev
---

## Decision

Each article repo carries `theses.yaml`: typed nodes (`thesis`, `hypothesis`, `objection`, `defense`, `source-claim`) and typed edges (`supports`, `attacks`, `rebuts`). A node holds an id, one line of text, a status (`proposed`, `accepted`, `retired`), the LaTeX `\label` it is anchored to, and the bib keys it rests on. `source-claim` nodes also hold a verbatim quote and a locator. A JSON schema in `schemas/` validates the file, as `metadata.schema.json` validates `metadata.yaml`. Readers get a node and its neighbourhood by id from the vendored CLI, never the whole file or the whole paper.

## Why

Hypotheses, offense and defense, and claim checking all need the same structure, and a 6000-line `article.tex` is the expensive thing to read. Markdown per node was rejected: edges would still need a script. Reusing facts and decisions as the map was rejected: an objection is not a guardrail, and project knowledge is not the article's argument.

## Consequence

One file can grow large and conflict in merges; the CLI must slice it and keep node order stable. The map is private working material (guardrail `theses-map-never-reaches-companion`).
