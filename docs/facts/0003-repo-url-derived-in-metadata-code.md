---
id: 0003-repo-url-derived-in-metadata-code
title: The repository URL in derived files is computed in code, not read from metadata.yaml
status: active
date: 2026-10-29
tags: [metadata, template, upgrade]
---

## Fact

`normalize_metadata` in `{{cookiecutter.repo_name}}/scripts/article/metadata.py` sets `_repo_url` to `https://github.com/<github_user>/<repo_name>`. `CITATION.cff` (`url`, `repository-code`) and the README BibTeX block read `_repo_url`. The `repo_url` key that the template writes into `metadata.yaml` is not read by that code.

## Consequence

Pointing derived files at a different repository is a change to `scripts/article/`, which `upgrade` delivers to existing repos, followed by `make metadata`. It needs no edit to an author's `metadata.yaml`, which `upgrade` never text-merges.
