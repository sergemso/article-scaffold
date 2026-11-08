---
id: 0080-sources-are-fetched-once-normalized-and-addressed
title: An external source is fetched once into a store, normalized and indexed, and agents read only addressed excerpts
status: active
date: 2026-11-07
tags: [sources, cost, retrieval, scholar-mcp, theses-map]
track: process
accepted-by: Sergey Strebulaev
governed-facts: [0010-virage-is-semantic-and-injects-on-every-prompt]
---

## Decision

- **Store.** Under `paper/sources/`, each source has the raw file as fetched, a normalized plain-text file, a manifest entry (origin, retrieval time, content hash, edition key per 0075) and a locator index (headings, numbered paragraphs, requirement keywords with line ranges).
- **Acquisition.** Only a fetch step, run through scholar-mcp (its decision 0071), brings a source in. It writes the raw file and manifest entry. Normalization and indexing are CLI steps (`sources add|index`) and make no network call (guardrail `claim-check-input-stays-local`).
- **Address.** A passage is `source-key@hash#locator`. `source-claim` nodes (0065, 0075) hold that address. Claims that reference an edition whose hash changed are reported stale by the CLI, not re-read.
- **Reading.** `sources slice <address>` returns the passage with a bounded window. Agents never read a whole source file; the work-order brief (0081) carries the addresses.
- **Optional locator layer.** Where a source set is large, a virage index (embedder local, store embedded or Qdrant) may answer "where is X" with addresses. It is explicit-call only, its per-prompt injection hook is disabled, it never stores or returns a verdict (guardrail `retrieval-returns-locators-not-verdicts`), and the CLI works without it.

## Why

The article repos cite standards drafts and papers kept as raw text. Without addresses, every agent re-reads them and re-infers what they say, and no claim can be checked against a stable passage. Fetching once, with a hash, makes the claim check (0067) and the ledger (0079) exact.

## Consequence

A source with no normalized text is listed, not guessed. Normalizing PDF and HTML is lossy and is recorded in the manifest so a quote mismatch can name the cause. Virage adds an external dependency only when a repo opts in.
