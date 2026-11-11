---
id: 0075-source-claims-record-edition-translation-and-stance
title: A source-claim may record its edition, translation, stance and reading, and checks follow them
status: active
date: 2026-11-03
tags: [theses-map, sources, claim-check]
track: product
accepted-by: Sergei Strebulaev
---

## Decision

A `source-claim` (0065) gains optional fields so existing nodes stay valid: a structured `locator` (edition, page or section), `bib`, `rests-on` (`wording`, `argument`, `doctrine`, `fact`), an author-supplied `edition-map`, a `translation` block (original, translator, `original-quote`, `load-bearing-terms`), a `context` block (`stance`: `asserts`, `reports`, `concedes`, `rejects`, `example`, `ironic`; `scope-note`; a context `window`) and `reading` (`direct`, `paraphrase`, `interpretive`). Defaults cost nothing to leave out: one edition, no translation, `stance: asserts`, `reading: direct`. `reading: interpretive` stays a field, not a node type.

Source texts are filed one file per edition under `paper/sources/`, named by the edition key. The claim checks of 0067 keep their order and locality and read local text only:

- Tier 1 matches the quote in the named edition's file, matches `original-quote` in the original's file when it exists (otherwise reports `original-unavailable` as advice), checks the structure of the new fields, and reports quote drift with the normalisation used.
- Tier 2 gets the claim, the quote with its window, the stance and scope note, and for translations the original and the load-bearing terms. Verdicts add `out-of-context`, `translation-sensitive`, `needs-wider-context` and `supports-with-reading` to `supports`, `overstates` and `contradicts`. A fixed two-pass prompt states the strongest reading the author could accept, then judges the claim against it. `needs-wider-context` widens the window once automatically, then reports `unclear`. The cache key includes claim, excerpt, window, stance and original-quote.
- Tier 3 (human attestation) is required for any `interpretive` reading, for a kept `translation-sensitive` or `out-of-context` verdict, and for a claim whose edition cannot be verified locally; it records who, when, why, and which edition and translation were consulted.

## Why

0067 assumes one verbatim quote at one locator in one local text, which breaks when meaning depends on the edition, a translator's choice, the author's stance or a reading of the work. Three verdicts cannot express "accurate quote, wrong use". An interpretive node type was rejected for now as heavier than the field while interpretive claims are rare. Automatic mapping between editions was rejected: no tool guesses it.

## Consequence

Authors who cite several editions or translations take on structured locators and per-edition files. A small local model is unreliable on non-English or archaic originals, so tier 2 is advisory there and tier 3 is required. Whether a rendering is faithful, and whether a passage represents an author's view, stay human judgment.
