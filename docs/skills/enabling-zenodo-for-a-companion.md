---
id: enabling-zenodo-for-a-companion
title: Enable the public companion and Zenodo for an article repo
status: active
date: 2026-10-29
tags: [companion, zenodo, procedural]
operationalizes: [companion-release-final-tags-only, app-key-stays-in-scaffold, companion-publishes-allowlist-only]
---

## Procedure

1. The scaffold's GitHub App is set up and installed on the article's org (`docs/skills/setting-up-the-article-github-app.md`). The article repo is on a template version that has `companion.yaml`; if not, run `python3 -m scripts.article upgrade --plan`, then `--apply` and `--finish`, and merge the result. The upgrade also removes the old article-side `publish-companion.yml`.
2. Review `companion.yaml`: companion name, allowlist and deny patterns. Add data, figures or supplementary paths the archive must contain.
3. In the scaffold, run `provision-companion.yml` with the article repo and `dry_run` on. Read the job summary for what it would create or change.
4. Run it again with `dry_run` off. It creates the public companion if absent.
5. On zenodo.org, account settings, GitHub tab: sync the repository list and switch the companion on. This cannot be automated.
6. Bump `version` in `metadata.yaml`, add the `CHANGES.md` entry, run `make metadata`, commit and push the tag `vX.Y.Z` in the article repo.
7. In the scaffold, run `publish-companion.yml` with the article repo (`repo`), the tag and `dry_run` on. Download the snapshot artifact and read its file list.
8. Run it again with `dry_run` off. It publishes the companion Release and Zenodo archives it.
9. After Zenodo mints the DOI, record it with the existing release flow (`release apply`) and publish a follow-up version if the DOI must appear in the archive.
