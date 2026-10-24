---
id: 0005-out-of-band-confirmation-and-publish
title: Writes, picks and attestations are confirmed out of band; publish is a tool behind that confirm
status: active
date: 2026-10-24
tags: [security, confirmation, release]
track: process
accepted-by: Sergey Strebulaev
governed-facts: [0002-zenodo-publish-mints-permanent-doi]
---

## Decision

A tool that writes (bibliography entries, letters, release and deposit steps) or needs a human choice (candidate picks, attestations) returns a plan id and a content hash. The human runs `scholar-authors confirm <id>` in their own terminal, which shows the exact diff or record and asks y/N. The token is single-use, expires, and is bound to that hash; the model never sees it. MCP elicitation is not used as the confirmation path, because hosts differ in how faithfully they render and whether they auto-approve.

The final Zenodo publish is a tool, gated by this same confirmation with the exact metadata shown. The API token comes from the OS keyring or the environment and is never a tool argument or a log field.

## Why

Confirmation must be something a prompt-injected or confused model cannot give itself. The owner chose to allow publish as a gated tool instead of a human-only command, accepting more automation at the price that a compromised session is one human y/N away from a permanent DOI (fact 0002).

## Consequence

The confirmation CLI is part of the security boundary and has its own tests: stale token, wrong hash, replay, path escape, missing confirmation. The publish tool defaults to the Zenodo sandbox; production publish needs an explicit, separately confirmed setting.
