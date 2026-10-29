---
id: 0061-companion-publish-trigger-and-gate
title: Publishing to the companion runs from its own tag workflow and only final tags release
status: active
date: 2026-10-29
tags: [companion, zenodo, release, ci]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

- **Trigger:** `publish-companion.yml` in the article repo runs on `v*` tags and on `workflow_dispatch` (inputs `tag`, `dry_run`). It calls `reusable-build.yml` for the PDF and DOCX, builds the snapshot with `python3 -m scripts.article companion`, and pushes with `COMPANION_TOKEN`. It is independent of `release.yml`.
- **Gate:** a Release is created on the companion only when the tag is a final `vX.Y.Z`, equals `metadata.yaml`'s version, `make validate` passes and the leak scan is clean. Any other tag, and every `dry_run`, builds the snapshot and uploads it as a workflow artifact without touching the companion.
- **Idempotency:** re-running a published version with an identical tree is a no-op. An existing companion tag with a different tree fails; it is never moved.
- **Deposit route:** for a repo with a companion, Zenodo's GitHub integration is the route. The `scholar-mcp` deposit tools are not used for the same version (refines 0057), so one version cannot get two records.
- **Skip:** with no `companion.yaml` or no `COMPANION_TOKEN` the workflow prints a notice and succeeds.

## Why

The Release is permanent (fact 0002), so a typo tag or a release candidate must not reach it, and the check must work on any GitHub plan, which rules out required-reviewer environments. A separate workflow keeps `release.yml`, which authors edit, out of the upgrade conflict path and out of this failure path. Cost: the manuscript builds twice per release. Rejected: `workflow_run` (default-branch copy, cross-run artifact download, silent skip on rename) and a job inside `release.yml`.

## Consequence

A forgotten version bump fails loudly at the gate instead of publishing the wrong version. DOI backfill into `metadata.yaml` after Zenodo mints it stays on the existing `release apply` flow.
