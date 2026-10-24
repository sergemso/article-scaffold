---
id: 0004-egress-identifiers-and-search-strings-only
title: Only identifiers and bibliographic search strings leave the machine
status: active
date: 2026-10-24
tags: [security, privacy, egress]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

Outbound requests carry only identifiers (DOI, ISBN, arXiv id, PMID, ORCID) and bibliographic search strings (title and author terms typed for a lookup). Manuscript text, abstracts, figures and data never leave the machine. Requests go only to an allowlist of registry hosts, over HTTPS, with redirects off the allowlist refused. A search returns candidate records only; a human picks one through the confirmation CLI (decision 0005), and the model can neither choose nor edit a candidate.

## Why

Unpublished work must stay on the machine, and authors often have a title but no DOI, so search is needed. Candidate-only search with a human pick keeps decision 0002 intact.

## Consequence

Tools that need manuscript text, such as similarity or claim checking, are out of scope. An addition to the host allowlist is a decision, not a configuration tweak.
