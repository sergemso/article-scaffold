---
id: restricted-paths-denied
title: Agents must not touch restricted paths and none may be committed
status: active
date: 2026-10-24
tags: [practice-packs, governance, guardrail]
governed-by: 0030-restricted-paths-enforcement
grounded-in: [0030-restricted-paths-enforcement]
derivation-note: Given restricted data must not reach a model or a repository (0018), the host must block access and git must refuse the files, since instructions alone fail silently.
go-getter:
  enforcement:
    - tier: 2
      check: Pre-tool hook blocks tool calls that touch a restricted path
      run: builtin:deny-path paths=".env, .env.*, *.pem, *.key, id_rsa, id_ed25519"
    - tier: 3
      check: No tracked file matches a restricted path
      run: builtin:deny-path paths=".env, .env.*, *.pem, *.key, id_rsa, id_ed25519"
  generated-by: restricted-data@0.6.0
  pack-answer: enforcement
  pack-option: hook-and-never-committed
---

## Guardrail

Never read, write or commit a path on the restricted list. The host hook blocks tool calls that mention one where the host supports it; git hooks and CI fail when a tracked file matches.
