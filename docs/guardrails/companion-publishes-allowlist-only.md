---
id: companion-publishes-allowlist-only
title: Nothing outside the allowlist, or matching a deny pattern, reaches the companion
status: active
date: 2026-10-29
tags: [companion, privacy, guardrail]
governed-by: 0059-public-companion-repo-per-article
grounded-in: [0059-public-companion-repo-per-article, 0002-zenodo-github-integration-constraints]
derivation-note: Given a published Zenodo version is permanent (0002) and the companion is public by construction (0059), only files named by the allowlist may be copied, and deny patterns and a leak scan must be able to veto them.
---

## Guardrail

The snapshot builder copies only paths matched by `companion.yaml`'s allowlist. A path that also matches a deny pattern is dropped. The build fails, publishing nothing, when the result contains a denied path, the private repo's name or URL, or text matching the secret patterns. Enforced by `python3 -m scripts.article companion` and its tests; the workflow does not publish unless the builder exits 0.
