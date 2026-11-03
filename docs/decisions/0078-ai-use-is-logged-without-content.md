---
id: 0078-ai-use-is-logged-without-content
title: AI use is logged as an append-only, content-free record that drafts the AI-use statement
status: active
date: 2026-11-03
tags: [provenance, privacy, host-neutral, orchestration]
track: product
accepted-by: Sergey Strebulaev
---

## Decision

The flow tooling and `theses accept` append one JSON object per event to `docs/provenance/ai-use.jsonl`, committed with the repo. An event records the time, the order, the stage and kind, the tier (`script`, `small`, `large`, as in 0072), a coarse `tool_class` (`script`, `agent`, `human`), node ids, repo-relative output paths, an `outcome` (`proposed`, `accepted`, `rejected`, `waived`, `failed`), who accepted and when, and the named check with its result. Human acceptance is a separate line referencing the same order; an agent-authored node stays `proposed` until such a line exists (guardrail `agent-nodes-need-human-promotion`).

The log never holds manuscript, source or review text, prompts, responses or reasoning, file contents, secrets, personal data, absolute paths, model, host or vendor names, or counts written into prose. The writer accepts only the defined fields; there are no free-text fields. `provenance lint` rejects an unknown key or an over-long value.

`provenance report` reads the log and prints a draft paragraph for the AI-use statement, grouped by kind and tool class, and flags mismatches between the current statement and the log. It never writes the backmatter. The log covers work done through the flow only; work outside it (an editor assistant, a pasted conversation, un-tooled human edits) is not captured, the report says so, and the author is still asked. Un-tooled human work is not loggable.

The log is excluded from the public companion (guardrail `theses-map-never-reaches-companion`, extended to cover it).

## Why

The AI-use statement is written by hand and can drift from what happened. A structural content-free log makes "AI was not used for X" checkable against events instead of asserted. A model name is not a stable fact about the work and article repos are host-neutral, so none is recorded. Keeping the log outside the repo was rejected: the evidence should be versioned with the work. A `provenance note` command for human edits was rejected: self-reported entries add little and the author is asked anyway.

## Consequence

The file grows. The log lists internal node ids, so the companion exclusion is required, not optional. A log that passes lint can still be incomplete, so the statement stays the author's to write.
