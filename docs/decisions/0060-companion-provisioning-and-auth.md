---
id: 0060-companion-provisioning-and-auth
title: The scaffold provisions companions idempotently and fans out a scoped token
status: active
date: 2026-10-29
tags: [companion, ci, security, bootstrap]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

- **Provisioning:** `.github/workflows/provision-companion.yml` in the scaffold, triggered by `workflow_dispatch` and `workflow_call`. Inputs: `repo` (one article repo, or `all` for every owner repo that has a `companion.yaml`) and `dry_run`. It creates the companion if absent, sets description and topics, installs the `COMPANION_TOKEN` secret in the article repo, and reports drift. It never changes the visibility of an existing repo and never deletes anything. Re-running changes nothing except refreshing the secret. `bootstrap-article.yml` calls it for new repos; existing repos use it by hand.
- **Config:** `companion.yaml` at the article repo root (companion repo, branch, allowlist, deny patterns). It is a template file, so `upgrade` adds it to repos scaffolded earlier; the provisioning workflow reads it and reports "run upgrade" when it is missing.
- **Auth:** the scaffold holds `COMPANION_PAT`, a fine-grained token with contents write on companion repos and no access to article repos. Provisioning copies it into each article repo as `COMPANION_TOKEN`. `GH_PAT`, which can create and administer repos, stays in the scaffold.
- **Bootstrap default:** `repo_visibility` in `bootstrap-article.yml` defaults to `private`.

## Why

A deploy key authenticates git only, not the GitHub API, so it cannot create the Release that Zenodo listens for (fact 0002), and a workflow cannot read another repo's secret, so the scaffold must hold the token and push it out. One holder means one rotation point. Reusing `GH_PAT` would put a repo-deleting credential in every article's CI. Per-repo hand-made tokens are not automatable. Putting the config in `metadata.yaml` was rejected: it would change the v2 schema and collide with `upgrade`'s special handling of that file.

## Consequence

`COMPANION_PAT` must be kept covering every companion (a fine-grained token lists repositories, so a new companion may need the token edited, or the token set to all repositories of the owner limited to contents write). Zenodo's per-repo switch stays manual (fact 0002; skill `enabling-zenodo-for-a-companion`).
