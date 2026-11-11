---
id: 0070-article-lifecycle-is-derived-from-the-repo
title: Lifecycle stage readiness is computed from the repo; only decisions are stored
status: active
date: 2026-11-02
tags: [orchestration, lifecycle, theses-map]
track: process
accepted-by: Sergei Strebulaev
---

## Decision

An article moves through stages: frame, map, discover, draft, verify-sources, adversarial, revise, release-gate, publish. Whether a stage's gate passes is computed from the repo: map gaps (decision 0066), check-cache freshness (0067), `make validate`, bibliography verification, the layout check. Any stage can be re-entered: a late review that reopens the draft makes earlier gates fail again with no pointer to move back. A committed `flow.yaml` stores only what cannot be derived: the round number, human attestations and stage waivers (who, when, why), and budget used (decision 0072).

## Why

A stored stage pointer drifts when someone edits the paper outside the flow, and regress after a review is awkward. A stored per-stage status is a second source of truth beside the repo; the hand-written review-response plans show the same failure (a plan says done, the paper says otherwise).

## Consequence

Every gate must be a cheap, deterministic predicate; a stage with no computable gate cannot be a stage and stays a human step. Gate evaluation runs on every `flow status`, so it must stay fast and quiet.
