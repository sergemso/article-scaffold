---
id: companion-release-final-tags-only
title: No Release is created on the companion unless the tag is final and matches the version
status: active
date: 2026-10-29
tags: [companion, zenodo, release, guardrail]
governed-by: 0061-companion-publish-trigger-and-gate
grounded-in: [0061-companion-publish-trigger-and-gate, 0002-zenodo-github-integration-constraints]
derivation-note: Given a published Release mints a permanent version (0002), only a tag of the form vX.Y.Z equal to metadata.yaml's version, with validate and the leak scan clean, may create one (0061).
---

## Guardrail

`publish-companion.yml` creates a companion Release only when the tag matches `^v[0-9]+\.[0-9]+\.[0-9]+$`, equals `v` plus `metadata.yaml`'s version, `make validate` passes and the leak scan is clean. Otherwise the run is a dry run. An existing companion tag is never moved or deleted. Enforced by the workflow's gate job and a static test of its conditions.
