---
id: 0010-virage-is-semantic-and-injects-on-every-prompt
title: Virage retrieves by similarity, can use Qdrant, and its Claude Code hook injects retrieved chunks on every prompt
status: active
date: 2026-11-07
tags: [retrieval, cost, sources]
---

## Fact

Taken from go-getter's fact `0038-virage-integration-surface` (read in the virage source on 2026-10-12, not run here). Virage is not checked out under `/home/sergei/projects`; re-verify before relying on details.

- It indexes files by embedding chunks (local or hosted embedder) into a store (embedded LanceDB by default; Qdrant, Postgres and others are options). Results are similarity ranked, so they are approximate and depend on the embedder.
- The Claude Code plugin registers an MCP server and a `UserPromptSubmit` hook that, on every prompt, injects up to five chunks (similarity at least 0.65, budget 2000 tokens) without a tool call.
- A hosted embedder sends chunk text off the machine.
- No secret scan or restricted-path input was found.

This is why retrieval here is locator-only and explicit-call (0080) and why exact-key results go to the ledger (0079).
