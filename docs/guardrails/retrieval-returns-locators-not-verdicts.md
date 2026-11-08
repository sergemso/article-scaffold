---
id: retrieval-returns-locators-not-verdicts
title: A retrieval layer returns source addresses, never verdicts or summaries stored as fact
status: active
date: 2026-11-07
tags: [sources, retrieval, guardrail]
governed-by: 0080-sources-are-fetched-once-normalized-and-addressed
grounded-in: [0080-sources-are-fetched-once-normalized-and-addressed]
derivation-note: Given retrieval is approximate (fact 0010) and a claim check needs the exact passage (0067), a retrieved chunk is a pointer that the claim check must resolve to an addressed excerpt.
go-getter:
  enforcement:
    - tier: 1
      check: A test that the CLI accepts a retrieval result only as a list of `source@hash#locator` addresses, resolves each through the source store, and writes nothing to the ledger from retrieval output.
---

## Guardrail

Retrieval output is used only as addresses. It is resolved through the source store before any claim check, and it is never written to the ledger, the theses map or a prompt as a verdict or summary. The per-prompt injection hook of a retrieval plugin is not enabled in article repos.
