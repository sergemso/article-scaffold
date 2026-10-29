---
id: 0002-zenodo-github-integration-constraints
title: Zenodo's GitHub integration archives the release of a public repo and cannot be undone
status: active
date: 2026-10-29
tags: [zenodo, release, public-companion]
---

## Fact

Verified on 2026-10-29 against
https://rue-a.github.io/github-zenodo-integration/documentation,
https://support.zenodo.org/help/en-gb/24-github-integration/96-how-does-a-citation-cff-file-affect-metadata-of-my-github-release
and https://support.zenodo.org/help/en-gb/24-github-integration/127-which-github-permissions-do-you-request-and-why:

- Zenodo archives the repository when a new GitHub Release is published on a repository the author has switched on. The archive is the release's tree, so the tree at the tag is what becomes public and permanent.
- Zenodo has no access to private repositories; it installs a webhook on public ones. A private article repo cannot be the source.
- Switching a repository on is done by hand in the Zenodo account settings (GitHub tab). No workflow in this template can do it.
- When both exist, `.zenodo.json` takes precedence and `CITATION.cff` is ignored for the record's metadata (it still drives GitHub's citation box).
- A published record cannot be deleted; a fix is a new version.

Not confirmed in the documentation, so do not rely on it: whether draft or pre-release Releases are ignored, and whether a bare tag push is ignored. The design only creates a Release for a final tag, so it does not depend on either.

## Consequence

The release step on the companion is the irreversible step (decision 0061). Anything pushed to the companion and tagged is public history.
