---
id: 0005-github-app-installation-token-capabilities
title: What a scaffold GitHub App installation token can and cannot do in the article org
status: active
date: 2026-10-31
tags: [github-app, companion, zenodo, security]
---

## Fact

Probed on 2026-10-31 with the scaffold App (installed on `strebulaev-articles`, all repositories, permissions as in `docs/skills/setting-up-the-article-github-app.md`), using `gh api` and tokens minted by hand from the App key. The probe repo `articles.app_probe` and a second one were deleted afterwards.

| # | Claim | Result |
|---|---|---|
| 1 | A token creates a repo in the org with `POST /orgs/strebulaev-articles/repos` | **Verified.** Created `strebulaev-articles/articles.app_probe` (private, `auto_init`). |
| 2 | A token pushes a file under `.github/workflows/` | **Verified.** `PUT /repos/.../contents/.github/workflows/probe.yml` returned a commit. |
| 3 | A token minted for one repo creates a Release | **Verified.** `POST /repos/.../releases` created `v0.0.1`. |
| 4 | A token narrowed to one repo cannot touch another | **Verified for existing repos, with a caveat.** On an existing second repo, writing a file, creating a Release and deleting the repo each returned `403 Resource not accessible by integration`; `GET /installation/repositories` listed only the one repo. Caveat: the same token could still **create** a new repo in the org (`POST /orgs/.../repos` succeeded, and without `private=true` the repo was **public**). |
| 5 | A Release created with an installation token triggers Zenodo's release webhook | **Unverified.** Needs the owner to enable the probe repo at `sandbox.zenodo.org/account/settings/github/` before a Release is created; Zenodo's GitHub integration has no documented API. The probe repo is gone, so the question stays open for the first real dry run. |

Also seen: an installation token cannot create repos in a personal account. `POST /orgs/sergemso/repos` returned `404 Not Found` (`sergemso` is a user, not an org), and `POST /user/repos` returned `403 Rate Limit Exceeded`, which is not conclusive; this is why the org is the owner (decision 0062).

## Consequence

- Decisions 0062 and 0063 stand; claims 1 to 3 hold, so no step is blocked.
- Repo narrowing limits access to existing repositories only. Org-level Administration lets any token the App mints create repos, so scaffold code that creates repos must always pass `private=true` explicitly (or the chosen visibility) and must not rely on the narrowing for that.
- Step 3.4 may create the Release with `gh api POST /repos/<companion>/releases` using the Contents-write token narrowed to the companion repo; this call was proven for a single-repo token.
- Claim 5 must be checked on the first real dry run before the owner switches a companion on in Zenodo; until then treat webhook delivery for app-created Releases as unproven.
