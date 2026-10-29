---
id: companion-token-least-privilege
title: COMPANION_PAT is scoped to companions and GH_PAT never enters an article repo
status: active
date: 2026-10-29
tags: [companion, security, guardrail]
governed-by: 0060-companion-provisioning-and-auth
grounded-in: [0060-companion-provisioning-and-auth]
derivation-note: Given article-repo CI runs author-editable workflows (0060), the only credential placed there may write companion contents and nothing else.
---

## Guardrail

The scaffold sets only `COMPANION_TOKEN` (from `COMPANION_PAT`) in an article repo. It never sets `GH_PAT` or any token with administration, workflow or article-repo access. `COMPANION_TOKEN` is read only by the publish job of `publish-companion.yml` and is never echoed. Enforced by tests that read the provisioning script and both workflows for secret names and `set +x` handling.
