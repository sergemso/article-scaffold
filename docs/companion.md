# Public companion repos

Article repos are private. Zenodo's GitHub integration only archives public repos and
reacts to a published GitHub Release (fact `0002-zenodo-github-integration-constraints`).
So each article repo gets a public **companion** repo, `<owner>/<article repo>.public`,
that receives an allowlisted snapshot on every final release. Zenodo archives the
companion. Rationale: decision `0059-public-companion-repo-per-article`.

## What is and is not published

Published: what `companion.yaml` in the article repo allows (by default `paper/`, `data/`,
`analysis/`, `schemas/`, licences, `README.md`, `CHANGES.md`, `CITATION.cff`,
`.zenodo.json`, `metadata.yaml`) plus the built `manuscript.pdf`, `manuscript.docx` and
`supp/`. Never published: `.github/`, `.claude/`, `.scholar/`, `scripts/`, `docs/`, build
output, and key or `.env` files. Deny patterns beat the allowlist, and a leak scan fails the
build if the private repo's name or a secret pattern appears in the snapshot.

## Scaffold secrets

Both live in this repo under Settings, Secrets and variables, Actions.

| Secret | Purpose | Scope |
| --- | --- | --- |
| `GH_PAT` | Creates repos and sets secrets. Stays in the scaffold. | Classic PAT: `repo` + `workflow`. Fine-grained PAT: all repositories, with Contents, Workflows, Administration and Secrets read/write (Administration is what `gh repo edit` needs; without it provisioning fails with `Resource not accessible by personal access token`). |
| `COMPANION_PAT` | Copied into each article repo as `COMPANION_TOKEN`. | Fine-grained PAT, repository permission *Contents: read and write*, repositories: the companions only. |

A fine-grained token can only be scoped to repositories that already exist, so the
order is: provisioning creates the companion (this works with `GH_PAT` alone and
reports the secret as `deferred`), then you create `COMPANION_PAT` scoped to the
companions (repository permission *Contents: read and write*), set it as a scaffold
secret, and run provisioning again to install `COMPANION_TOKEN`. When a new companion
appears later, edit the token to add it (or choose all repositories of the owner with
only contents write), then run provisioning again to refresh the secret. Guardrail
`companion-token-least-privilege`.

## Provisioning

Run `provision-companion.yml` from the Actions tab (or `gh workflow run`):

```bash
gh workflow run provision-companion.yml -f repo=OWNER/articles.topic -f dry_run=true
gh workflow run provision-companion.yml -f repo=all -f owner=OWNER -f dry_run=false
```

It creates the public companion if absent, sets description and topics, installs
`COMPANION_TOKEN` in the article repo and reports drift. It never changes visibility and
never deletes. Per repo the result is `created`, `updated`, `unchanged`, `needs-upgrade`
(the article repo has no `companion.yaml`: upgrade it first), `drift` (the companion exists
but is private), `refused` or `error`; the secret column reads `refreshed`, `deferred`
(no `COMPANION_PAT` yet: scope it and run again) or `would-refresh`. Re-running changes
nothing except the secret.
`bootstrap-article.yml` calls it for new repos (input `create_companion`).

## Switching Zenodo on

Manual and per companion: zenodo.org, account settings, GitHub tab, sync, toggle the
companion on. Then push a final `vX.Y.Z` tag in the article repo. Full procedure:
`docs/skills/enabling-zenodo-for-a-companion.md`. Decisions: `0060`, `0061`.
