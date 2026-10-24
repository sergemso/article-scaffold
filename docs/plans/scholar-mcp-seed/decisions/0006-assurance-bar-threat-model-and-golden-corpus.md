---
id: 0006-assurance-bar-threat-model-and-golden-corpus
title: A written threat model and a zero-tolerance golden corpus gate every release
status: active
date: 2026-10-24
tags: [security, testing, release]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

Baseline for every server: the official MCP Python SDK, stdio transport only (no network listener), pinned dependencies with hashes, and a test for every refusal path. Before the first release the repository must hold a written threat model (assets, trust boundaries, abuse cases such as prompt injection through manuscript text or fetched records, path escape, SSRF through lookups, secret leakage), each mapped to a control and a test.

The reference pipeline is gated by a frozen golden corpus of real records: diacritics and non-Latin names, corporate authors, very long author lists, retracted and corrected papers, preprint versus published versions, DOI case and URL variants, DataCite datasets, books by ISBN, and known wrong-metadata cases. Recorded responses replay offline in CI; a nightly job runs against the live registries. A field not traceable to its source record, or an unflagged mismatch, fails the build.

## Why

"Highly proven, secure, reliable" needs a concrete bar. Fuzz testing, signed releases and an independent review were offered and not required for the first release; they can be added by a later decision. The correctness requirement is stricter than the security one, so it has the hard gate.

## Consequence

Corpus maintenance is ongoing work: a new registry quirk becomes a new corpus entry. Live-run failures are triaged, not ignored, since they show a registry changed.
