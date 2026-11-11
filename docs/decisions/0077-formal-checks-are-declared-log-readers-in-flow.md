---
id: 0077-formal-checks-are-declared-log-readers-in-flow
title: A formal check is a declared log reader in flow.yaml; the run itself is a gated order the flow never executes
status: active
date: 2026-11-03
tags: [orchestration, formal-methods, host-neutral]
track: product
accepted-by: Sergei Strebulaev
---

## Decision

`flow.yaml` may declare named formal checks. A declaration has a `name` starting with `formal-`, a `kind` from a closed list (only `log-verdict` for now), a repo-relative `log_dir` under `docs/logs/`, hashed `inputs`, `required_logs`, `pass_when` rules (files that must be absent, line patterns that must not or must match) and a `run_hint` shown to the human. The repo supplies patterns, never a command line (guardrail `flow-checks-are-named-not-supplied`).

`flow done` for a `formal-check` order reads the logs, a pure file read, and reports `pass`, `fail` or `stale`. Stale means the input hash recorded when the run finished no longer matches the current inputs. A missing `log_dir` or required log reports `unavailable`, never `pass`; the environment record (image digest, tool hash) must be present. The run is a separate gated order kind, `run-formal`, whose human-facing text shows `run_hint`; the flow never executes it. A repo with no `formal` entries gets no `formal-check` order (fact 0009). A mutation pass is a second declared check with its own log and pass rule.

## Why

A gate must be a cheap deterministic predicate with no network and no model call (fact 0009, 0070), and running a model checker is neither cheap nor offline: it pulls an image and downloads a jar. Splitting running (gated, human or CI) from reading (a predicate) keeps the gate honest. Declarations sit in `flow.yaml` and not the map because they describe the lifecycle, not the argument.

## Consequence

A log-verdict check trusts the log; it cannot show the run was honest or that the model matches the prose, and the environment file is what makes the run auditable. Regexes on tool output are brittle across tool versions, so the rules live in the repo's declaration and the flow reports which rule failed. Whether the formal model corresponds to the paper's claims stays human judgment. Because repo-supplied patterns decide pass or fail, implementation must confirm the reader cannot be made to run anything.
