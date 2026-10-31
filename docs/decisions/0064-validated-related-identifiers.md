---
id: 0064-validated-related-identifiers
title: Linked articles are declared in related_identifiers, validated, and emitted to .zenodo.json only
status: active
date: 2026-10-31
tags: [metadata, zenodo, series]
track: product
accepted-by: Sergey Strebulaev
---

## Decision

- **Key:** `related_identifiers` in `metadata.yaml`, a list of `{identifier, relation, scheme}`. The name matches Zenodo's and the existing pass-through, so repos that already use it keep working.
- **Relations:** `isPartOf`, `hasPart`, `continues`, `isContinuedBy`, `isNewVersionOf`, `isPreviousVersionOf`, `obsoletes`, `isObsoletedBy`, `isSupplementTo`, `isSupplementedBy`, `references`, `isReferencedBy`, `isDocumentedBy`. Anything else is a validation error.
- **Targets:** `scheme` is `doi` or `url`. A bare DOI is normalised. A URL must be public: a URL on the org's private article repos fails validation.
- **Scope:** documented in `docs/metadata.md`, validated by `metadata.schema.json` and `validate_metadata`, emitted to `.zenodo.json`. Not rendered in `CITATION.cff`, the README or the title page. Reciprocal links are not inferred or checked: each article states its own side. A successor that has no DOI yet is added in a later version.

## Why

Zenodo already shows series and version links from this field; the cost is guidance and validation, not new output. Rendering and cross-repo checking would need the tracker and the app first, and can be added later without changing this format.

## Consequence

Existing entries that use another relation or a private URL start failing the metadata check after `upgrade`. Guardrail `related-targets-are-public`.
