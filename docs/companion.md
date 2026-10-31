# Public companion repos

Article repos are private. Zenodo's GitHub integration only archives public repos and
reacts to a published GitHub Release (fact `0002-zenodo-github-integration-constraints`).
So each article repo gets a public **companion** repo, `<owner>/<article repo>.public`,
that receives an allowlisted snapshot on every final release. Zenodo archives the
companion. Rationale: decision `0059-public-companion-repo-per-article`. Both repos live
in an org that has the scaffold's GitHub App installed (default `strebulaev-articles`);
the `owner` parameter of each workflow names it (decision `0062`).

## What is and is not published

Published: what `companion.yaml` in the article repo allows (by default `paper/`, `data/`,
`analysis/`, `schemas/`, licences, `README.md`, `CHANGES.md`, `CITATION.cff`,
`.zenodo.json`, `metadata.yaml`) plus the built `manuscript.pdf`, `manuscript.docx` and
`supp/`. Never published: `.github/`, `.claude/`, `.scholar/`, `scripts/`, `docs/`, build
output, and key or `.env` files. Deny patterns beat the allowlist, and a leak scan fails the
build if the private repo's name or a secret pattern appears in the snapshot.

## Scaffold credentials

One GitHub App is the only credential (decision `0062`). It is owned by `sergemso`,
installed on each article org, and its key never leaves this repo. Set up once with
`docs/skills/setting-up-the-article-github-app.md`. They live under Settings, Secrets and
variables, Actions.

| Name | Kind | Purpose |
| --- | --- | --- |
| `APP_PRIVATE_KEY` | secret | The App's private key. Read only by scaffold workflows. |
| `APP_ID` | variable | The App ID. |
| `APP_OWNERS` | variable | Allowed owners, one per line. A workflow refuses any other `owner`. |

Every job mints its own short-lived installation token with
`.github/actions/app-token`, narrowed to one owner and only the permissions it needs.
Article repos hold no secret for this. Guardrail `app-key-stays-in-scaffold`, enforced by
`tests/test_app_key_guardrail.py`.

## Provisioning

Run `provision-companion.yml` from the Actions tab (or `gh workflow run`):

```bash
gh workflow run provision-companion.yml -f repo=OWNER/articles.topic -f dry_run=true
gh workflow run provision-companion.yml -f repo=all -f owner=OWNER -f dry_run=false
```

It creates the public companion if absent, sets description and topics and reports drift.
It never changes visibility and never deletes. Per repo the result is `created`,
`updated`, `unchanged`, `needs-upgrade` (the article repo has no `companion.yaml`: upgrade
it first), `drift` (the companion exists but is private), `refused` or `error`.
`bootstrap-article.yml` calls it for new repos (input `create_companion`).

## Publishing a release

Publishing runs from the scaffold, never from the article repo (decision `0063`). After
the owner pushes a final `vX.Y.Z` tag equal to `metadata.yaml`'s version:

```bash
gh workflow run publish-companion.yml -f repo=articles.topic -f tag=vX.Y.Z -f dry_run=true
```

The first job, with a read-only token for that one article, checks out the tag, builds
the PDF and DOCX, applies the gate and uploads the snapshot as an artifact. With
`dry_run` off, a second job with a Contents-write token for the companion only commits the
snapshot as `release vX.Y.Z`, tags it and creates the GitHub Release Zenodo listens for.
Always dry-run first and read the artifact's file list.

## Tracking

`track-articles.yml` runs daily and on demand. For every owner in `APP_OWNERS` it lists
the article repos (those with `companion.yaml`) and writes a table to the run summary:
version, latest tag and Release, last successful run, and the companion's latest Release.
It flags drift: an article tag newer than the companion's, or a companion that is missing
or private. It is read only and never publishes. Locally:
`GH_TOKEN=... python3 scripts/track_articles.py --owner OWNER [--json]`.

## Linked articles

An article can declare its place in a series with `related_identifiers` in
`metadata.yaml`: a DOI or a public URL per link, validated by `make validate` (decision
`0064`). A link to a private article repo is refused. Each article declares its own side
of a link; see the generated repo's `docs/metadata.md`.

## Switching Zenodo on

Manual and per companion: zenodo.org, account settings, GitHub tab, sync, toggle the
companion on. Then push a final `vX.Y.Z` tag in the article repo. Full procedure:
`docs/skills/enabling-zenodo-for-a-companion.md`. Decisions: `0062`, `0063`, `0064`.
