---
id: 0076-defined-terms-are-registered-in-the-map-and-linted
title: Defined terms are registered in the map file and linted for use before definition and second definitions
status: active
date: 2026-11-03
tags: [theses-map, terms, lint]
track: product
accepted-by: Sergei Strebulaev
---

## Decision

The map file (0065) gains a `terms` section. A term has a stable `id`, a canonical `name`, the surface `forms` the linter searches for, a `kind` (`defined`, `external`, `acronym`), an `anchor` (the LaTeX label of the defining `definition` environment or section), a short author-written `definition`, optional `senses` (the author's declaration that a word is used in two senses, each with its own anchor), a `status`, and `author` (`human` or `agent`, the same field as on nodes, so agent-written terms need promotion under guardrail `agent-nodes-need-human-promotion`). `kind: defined` requires `anchor`, `kind: external` requires `source`, `kind: acronym` requires `expansion`. A sub-definition, such as an item of a `description` list, is registered as a child of its parent term and needs no label of its own. Nodes may list the terms they rely on so a slice carries those definitions and nothing else.

Matching is whole-word and case-insensitive with the listed plurals, and `match: phrase-only` is the default, so only the full phrase counts; a per-term `scope` listing sections is an override. A definition is never inferred from `\emph` alone, only from the `definition` environment or a registered anchor.

Tier 0 (script, offline) checks: dangling anchor (error); use before definition, except in a sentence that refs the anchor (warning, error once the term is accepted); second defining site (warning); unregistered `definition` environment (gap); orphan term (info); case and plural drift (info). The scanner skips math, verbatim, listings, comments, label strings, quotations and generated section files. Tier 2 sense-drift follows 0067: local model, input stays local, windows around occurrences and never the whole paper, verdicts `consistent`, `narrower`, `broader`, `different-sense`, `unclear`, cached by gloss and window hash; only `different-sense` and `broader` produce a gap, and the agent proposes a `senses` entry or a wording fix for a human to accept.

## Why

A paper that defines its own vocabulary fails quietly when a term is used before it is defined, used in two senses, or restated with a small change; a cheap linter finds the first two and flags candidates for the third. Terms sit in the map file because one validation pass then covers nodes and terms and the companion exclusion applies once. A separate `terms.yaml` was rejected for that reason. Phrase-only matching is the default because common words such as "contract", "session" and "gap" would otherwise fire the lint on every casual earlier use.

## Consequence

The schema, the section index and `theses gaps` need extending. The scanner has to strip non-prose contexts, and an over-broad form still floods the report, so forms need review when a term is added. Whether two senses are really one, whether a definition is good, and whether a deliberate early use is acceptable stay human judgment; the registry records the decision.
