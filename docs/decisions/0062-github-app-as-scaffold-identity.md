---
id: 0062-github-app-as-scaffold-identity
title: One GitHub App, installed on each article org, is the scaffold's only credential
status: active
date: 2026-10-31
tags: [companion, ci, security, bootstrap, github-app]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

- **Org:** article repos and their companions live in the GitHub org `strebulaev-articles`. `github_user` in the cookiecutter names the org.
- **App:** one GitHub App, owned by the personal account `sergemso` and set to "Any account" so it can be installed on every article org or account, installed on all repositories of each owner in use (today `strebulaev-articles`). Repository permissions: Administration write, Contents write, Workflows write, Actions read, Metadata read.
- **Secret:** the app ID and private key are the only secret. They live in the scaffold repo, which stays at `sergemso/article-scaffold`. No secret is ever set in an article repo.
- **Tokens:** every workflow job mints an installation token for `owner` and narrows it to the repositories and permissions the job needs. `owner` is an input with default `strebulaev-articles`, checked against an allowlist held in a scaffold repo variable.
- **Replaces:** `GH_PAT`, `COMPANION_PAT` and `COMPANION_TOKEN`.

## Why

A fine-grained PAT must be edited for each new companion, and a per-article secret must be set by someone for each new repo. An installation token is minted on demand, scoped per job, expires in an hour, and needs no per-repo setup because the app covers every repo in the org. The org is needed because an installation token cannot create repos in a personal account, only in an org (community reports; verified by plan step 1.1). Ownership does not limit where an app acts, only installability: a private app installs only on its owner's account, so a personal-owned "Any account" app is what lets several orgs share one key. Installing it grants no one access without the key, and the `APP_OWNERS` allowlist limits which owners the scaffold's workflows act on. The app can change owner later. The scaffold stays where it is so `upgrade` and existing `template.json` files keep working.

## Consequence

The app key controls every repo of every installed owner, so the scaffold's workflows become the trust boundary: protect its default branch and limit who can push to it. Guardrail `app-key-stays-in-scaffold`. Supersedes the auth part of 0060.
