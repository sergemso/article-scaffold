---
id: 0086-zenodo-deposit-carries-the-artifacts-as-files
title: The publish workflow deposits the PDF and DOCX on Zenodo as separate files
status: active
date: 2026-11-21
tags: [companion, zenodo, release, ci]
track: process
accepted-by: Sergei Strebulaev
---

## Decision

- **Deposit:** after it creates the companion Release, `publish-companion.yml` runs `scripts/zenodo_deposit.py`. It deposits `manuscript.pdf` and `manuscript.docx` as their own files, plus one reproducible source archive of the rest of the snapshot, with the metadata of the snapshot's `.zenodo.json` (only a fixed list of keys is forwarded).
- **Opt in, per run opt out:** the step runs only when the scaffold has the `ZENODO_TOKEN` secret and the dispatch input `zenodo` is on (the default). A dry run never reaches it, and a tag that is not final never reaches the publish job (0061).
- **Versions:** the Release notes of the companion carry `zenodo-record: <id>`. The newest earlier Release that carries one is the record a new tag is added to as a new version; a tag whose own Release already carries one is not deposited again, so a re-run is safe.
- **Token and host:** the token stays in the scaffold, is read only by the lookup and deposit steps, travels only in the Authorization header, and goes only to `zenodo.org` or `sandbox.zenodo.org` over https with redirects refused. `ZENODO_API` (a repository variable) selects the sandbox for a rehearsal.
- **Integration:** a companion that uses this step has Zenodo's GitHub integration switched off, or each tag is archived twice.

## Why

Zenodo's GitHub integration archives only the repository's source zip for a release (fact 0002). The PDF and the DOCX built for the Release were never separate files in the record: a reader had to unzip the repository to find the paper. Release assets are not archived. The deposit API is the only way to make them files of the record, and it can be driven from the publish job, which already holds the snapshot and runs only scaffold code.

## Consequence

The scaffold owner creates the `ZENODO_TOKEN` secret once (deposit and write scopes) and switches the integration off per companion. Without the secret nothing changes. A record is permanent, so the first deposit of an article is best rehearsed with `ZENODO_API=https://sandbox.zenodo.org/api` and a sandbox token.
