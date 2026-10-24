---
id: mcp-arguments-hold-no-secret
title: MCP calls carry no secret
status: active
date: 2026-10-24
tags: [practice-packs, hooks, guardrail]
governed-by: 0038-mcp-arguments-scanned
grounded-in: [0038-mcp-arguments-scanned]
derivation-note: Given an MCP server is third-party code reached with the project's context (0138), a secret in a call's arguments must be stopped by the host's hook before it leaves, since an instruction alone fails silently.
go-getter:
  enforcement:
    - tier: 2
      check: The pre-tool hook denies an MCP call whose arguments contain a secret
      run: builtin:mcp-scan
  generated-by: sanitization@0.7.0
  pack-answer: mcp-argument-scan
  pack-option: on
---

## Guardrail

Do not put a secret in the arguments of an MCP tool call. The pre-tool hook denies a call whose input matches the secret patterns and names the kind; remove the value and use `go-getter secret run` or an environment variable the server reads itself. `go-getter coverage` shows the tier per host.
