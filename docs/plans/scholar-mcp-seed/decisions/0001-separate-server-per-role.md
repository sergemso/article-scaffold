---
id: 0001-separate-server-per-role
title: One MCP server per role on a shared library
status: active
date: 2026-10-24
tags: [architecture, security, scope]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

`scholar-mcp` (MIT) ships three separately installable servers, `scholar_authors`, `scholar_editors` and `scholar_reviewers`, on a shared library `scholar_core`. `scholar_core` holds the path guard, audit log, confirmation tokens, output limits, registry clients and the reference pipeline. The authors server is built first; the other two start only after the shared library has been proven by it.

## Why

Editors handle other people's unpublished manuscripts and reviewer identities. An author's agent session must not be able to reach a tool that reads them, and the strongest way to guarantee that is to not install it. A launch-time profile in one server was rejected: it relies on configuration being right every time.

## Consequence

Three packaging surfaces and one shared library whose API must stay stable. A security fix in `scholar_core` is released for every server.
