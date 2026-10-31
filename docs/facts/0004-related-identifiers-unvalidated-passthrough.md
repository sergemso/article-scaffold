---
id: 0004-related-identifiers-unvalidated-passthrough
title: related_identifiers is copied into .zenodo.json with no validation and no documentation
status: active
date: 2026-10-31
tags: [metadata, zenodo, series]
---

## Fact

`gen_zenodo_json` in `{{cookiecutter.repo_name}}/scripts/article/metadata.py` copies `metadata["related_identifiers"]` into `.zenodo.json` unchanged when it is non-empty. `schemas/metadata.schema.json` does not list the key and `docs/metadata.md` does not mention it. `CITATION.cff`, the README and the title page ignore it. `tests/test_zenodo.py` only asserts that it is absent by default.

## Consequence

Any value, including a wrong relation, a private URL or a malformed DOI, reaches the Zenodo deposit and, through the companion, a permanent public record (fact 0002). Decision 0064 closes this.
