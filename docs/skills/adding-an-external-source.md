---
id: adding-an-external-source
title: Add an external source to an article repo so it is read once
status: active
date: 2026-11-07
tags: [sources, theses-map, procedural]
operationalizes: [claim-check-input-stays-local, retrieval-returns-locators-not-verdicts]
---

## Procedure

1. Fetch the source through the scholar-mcp source-fetch tool (confirm the plan in a terminal). It writes the raw file and a manifest entry under `paper/sources/`. A source you already hold by hand: place the file there and run `python3 -m scripts.article sources add <file> --origin <url-or-doi>` to hash it and add the entry.
2. Run `python3 -m scripts.article sources index`. Read the report: sections found, numbered paragraphs, requirement lines. A source it cannot normalize is listed as unreadable; do not paraphrase it from memory.
3. For each place the paper relies on the source, add a `source-claim` node holding the address from `sources slice` output (`source@hash#locator`), the verbatim quote, and the stance and edition fields of 0075.
4. Run `python3 -m scripts.article claims`. Tier 1 and tier 2 results are written to the ledger; unchanged inputs are not re-checked.
5. Commit the source files, manifest, ledger entries and nodes together.
6. If a retrieval index is in use, rebuild it only after step 2; its output is addresses, never evidence.
