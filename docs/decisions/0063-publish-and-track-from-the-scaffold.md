---
id: 0063-publish-and-track-from-the-scaffold
title: The scaffold publishes companions on manual dispatch and tracks articles on a schedule
status: active
date: 2026-10-31
tags: [companion, zenodo, release, ci, github-app]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

- **Publish:** `publish-companion.yml` moves from the article repo to the scaffold. It runs on `workflow_dispatch` with inputs `owner`, `repo`, `tag` and `dry_run`. It checks out the article at the tag with a read-only token, builds with the article's own tooling, builds the snapshot with `article companion`, and pushes to the companion with a write token narrowed to that one repo. It then creates the Release.
- **Gate (kept from 0061):** a Release is created only when the tag is a final `vX.Y.Z`, equals `metadata.yaml`'s version, `make validate` passes and the leak scan is clean. Any other tag, and every `dry_run`, uploads the snapshot as a workflow artifact and touches nothing.
- **Track:** a scheduled scaffold workflow lists the installation's repos that have `companion.yaml`, reads their latest `v*` tag, Release and last build artifact, compares with the companion, and writes a registry to the job summary. It never publishes.
- **Provisioning:** creation and repair of companions (description, topics, drift report) move into bootstrap and the tracker with the app token. Nothing is deleted and visibility is never changed.

## Why

Publishing is irreversible and the owner's call, so a manual trigger loses nothing. Moving it into the scaffold removes the last reason an article repo needs a credential. A webhook-driven trigger would need a hosted receiver; a schedule needs none, and latency is irrelevant for tracking. Supersedes the trigger part of 0061.

## Consequence

Article repos lose `publish-companion.yml`; `upgrade` removes it. The article's build is run from the scaffold, so the scaffold must check out and run code from an article repo: treat `companion.yaml` and the article's scripts as untrusted input, as the current script already does.
