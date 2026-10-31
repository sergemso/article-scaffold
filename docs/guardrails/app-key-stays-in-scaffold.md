---
id: app-key-stays-in-scaffold
title: The GitHub App key stays in the scaffold and every token is narrowed per job
status: active
date: 2026-10-31
tags: [companion, security, github-app, guardrail]
governed-by: 0062-github-app-as-scaffold-identity
grounded-in: [0062-github-app-as-scaffold-identity, 0063-publish-and-track-from-the-scaffold]
derivation-note: Given the app key can act on every repo in the org (0062) and article-repo CI runs author-editable code, no secret may be set in an article repo and each job may hold only the access it needs.
---

## Guardrail

The app ID and private key are read only by scaffold workflows. No workflow, script or template file sets, passes or echoes a secret into an article repo. Every token is minted with an explicit `owner`, an explicit repository list and the minimum permissions for that job, and `owner` must be on the allowlist. Enforced by tests that read the scaffold and template workflows and scripts for secret names, token-mint inputs and `set +x` handling.
