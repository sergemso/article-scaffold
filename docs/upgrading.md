# Upgrading a generated repo

A generated article repo is archival: it has no runtime dependency on this
template and is never updated automatically. When a template fix matters to
you, run `upgrade` to bring it in. It automates every step except resolving
conflicts, which stay with you; nothing here merges silently. The manual
procedure further down is the fallback for repos that cannot use the command.

## What the repo records

`template.json` at the generated repo root records how it was made:

| Key | Meaning |
|---|---|
| `template` | Where the template was rendered from (path or URL) |
| `template_version` | Template version (`pyproject.toml`) at generation time |
| `template_commit` | Template git commit, or `null` for a non-git source |
| `context.cookiecutter` | Every prompt answer used to render the repo |

## Upgrading with the command

From the generated repo, on a clean working tree (commit first):

```bash
python3 -m scripts.article upgrade --plan            # or: make upgrade
python3 -m scripts.article upgrade --apply
# resolve any conflicts, then `git add` the files
python3 -m scripts.article upgrade --finish
git commit
```

- `--plan` is read-only. It refuses, with a stable code, when `template.json` is
  missing or has no `template_commit`, the tree is dirty, `metadata.yaml` is still
  schema 1 (do `docs/migrating-to-v2.md` first), or the template or ref cannot be
  reached. Add `--to REF` to choose a branch, tag or commit; the default is the
  template's `HEAD`.
- `--apply` renders the old and the new template with the answers stored in
  `template.json`, applies the difference with `git apply --3way` on a new branch
  `upgrade/<sha>`, and lists `applied`, `conflicted` and `skipped` files. It does
  not commit, and it leaves conflict markers for you.
- `--finish` refuses while any file is unmerged or still has conflict markers. It
  then runs `make metadata` and `make validate`, bumps `template_version` and
  `template_commit`, and stages the result.

Needs `git` and, for the render, `cookiecutter` installed for the Python that runs
the command (`python3 -m pip install cookiecutter`); a URL template also needs the
network. `--json` gives the machine-readable result in `schemas/upgrade.schema.json`.

Limits, deliberately:

- A repository generated before the command existed does not contain it. Install
  it once with the bootstrap script (below), then use the command from then on.
- A file you added that the template also adds is skipped, not overwritten.
- It reproduces the template from the stored answers. Edits you made to
  `metadata.yaml`, sections and figures are yours and are merged, not replaced.

## Installing the command into an older repo

From the root of the generated repo, on a clean tree (the script needs only `git`
and `python3`):

```bash
curl -fsSLO https://raw.githubusercontent.com/sergemso/article-scaffold/master/scripts/bootstrap-upgrader.py
python3 bootstrap-upgrader.py            # template from template.json
python3 bootstrap-upgrader.py --template https://github.com/sergemso/article-scaffold --ref v1.1.5
rm bootstrap-upgrader.py
python3 -m pip install cookiecutter PyYAML
git add scripts schemas && git commit -m 'chore: add the article upgrade command'
python3 -m scripts.article upgrade --plan
```

It copies `scripts/article/` and the `schemas/*.json` the template ships into your
repo, and nothing else; it does not commit. It refuses to replace an existing
`scripts/article/` unless you pass `--force`. Delete the script and commit the
result before `--plan`, which refuses a dirty tree. A repo with no `template.json` cannot be planned: use the manual merge
below for that first upgrade.

## Automatic upgrade pull requests

A generated repo includes `.github/workflows/upgrade.yml`. Every Monday (and on
demand from the Actions tab) it runs `upgrade --plan`; when the template has a
newer commit it runs `upgrade --apply --commit` on a branch `upgrade/<sha>`,
pushes it and opens a pull request. The PR lists applied, conflicted and skipped
files. With conflicts it is a draft and the markers are committed. It never runs
`--finish`: check out the branch, resolve, run `upgrade --finish`, then commit and
push.

It is opt-in by its requirements, and otherwise only prints a notice:

- `template` in `template.json` is a public `https://` URL. A local path or an
  SSH URL cannot be reached from the runner.
- `template_commit` is set (the template was a git checkout when you generated).
- Settings > Actions > General > "Allow GitHub Actions to create and approve pull
  requests" is on.
- Optional: an `UPGRADE_TOKEN` secret (below). Without it, upgrades that change
  files under `.github/workflows/` fail at the push, and the checks of the PR it
  opens wait for someone to approve them.

The job has `contents: write` and `pull-requests: write`, nothing else. It
installs `cookiecutter==2.7.1` on the runner and does not add it to your repo.
Delete the workflow file if you do not want scheduled upgrades.

### Setting up `UPGRADE_TOKEN`

The template ships workflows, so a template upgrade usually changes files under
`.github/workflows/`. In practice GitHub rejects a push that does so when it is made
with the default `GITHUB_TOKEN` (reported by users; the docs do not mention it). GitHub's
documentation does say that events caused by `GITHUB_TOKEN` do not start new workflow
runs, except that `pull_request` runs for `opened`, `synchronize` and `reopened` wait for
approval, and that a personal access token or GitHub App token avoids this. The token
belongs to the generated repo, not to the template: the template is read over public
HTTPS with no credentials.

1. On GitHub: profile picture > Settings > Developer settings > Personal access
   tokens > Fine-grained tokens > Generate new token.
2. Name it (for example `upgrade-<repo>`) and choose an expiration. Note the date.
3. Under Repository access choose "Only select repositories" and pick this repo.
4. Under Repository permissions set Contents: write, Pull requests: write and
   Workflows: write (Workflows has no read option). Generate the token and copy it.
5. In the repo: Settings > Secrets and variables > Actions > New repository secret.
   Name `UPGRADE_TOKEN`, paste the token.
6. Check it: Actions > "Template upgrade" > Run workflow. When the template has a
   newer commit, the run should push `upgrade/<sha>` and open a PR, and the PR's
   checks should start without approval.

The token acts as you, so the PR and pushes carry your name, and it stops working at
its expiry; the workflow then falls back to `GITHUB_TOKEN` and upgrades that touch
workflow files fail again. Renew it before the date from step 2. Delete the secret to
go back to the default behaviour.

GitHub's own pages: [fine-grained personal access
tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens),
[repository permissions for them](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens)
and [using secrets in Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions).

## Why not cruft or Copier

- **cruft** is the nearest fit. It stores the same information (template,
  commit, context) and does a three-way update. It is not required here: it
  would add a tool to every repo that is meant to stay dependency-free, and
  its update step merges automatically.
- **Copier** needs the template converted to `copier.yml` and would replace the
  Cookiecutter prompts and hooks. Too invasive for a fix-pickup path.

`template.json` follows the cruft layout (`template`, `commit`, `context`), so
a team that wants cruft can adopt it later without re-stamping.

## Three-way merge by hand (fallback)

Run from the generated repo, on a clean branch. `OLD` is `template_commit` from
`template.json`; `NEW` is the template commit you want.

1. Build a config from the stored answers:

   ```bash
   python3 -c 'import json; c=json.load(open("template.json"))["context"]; print(json.dumps({"default_context": c["cookiecutter"]}))' > /tmp/upgrade-config.json
   ```

2. Render the old and the new template with those answers:

   ```bash
   cookiecutter <template> --checkout OLD --no-input --config-file /tmp/upgrade-config.json --output-dir /tmp/old
   cookiecutter <template> --checkout NEW --no-input --config-file /tmp/upgrade-config.json --output-dir /tmp/new
   ```

3. Diff old against new and apply it with a three-way fallback:

   ```bash
   (cd /tmp && git diff --no-index --binary old/<repo_name> new/<repo_name> > upgrade.patch)
   git apply --3way -p3 /tmp/upgrade.patch
   ```

4. Resolve conflicts, then review `git diff`.
5. Run `make metadata` and `make validate`.
6. Edit `template_version` and `template_commit` in `template.json` to NEW and
   commit.

Never skip step 4: your own edits to `metadata.yaml`, sections and figures will
conflict where the template changed the same lines.

## Copying files by hand

If the merge is not worth it, read the release notes and copy only the files
you need (usually `scripts/`, `.github/workflows/` and `Makefile`). Run
`make metadata` and `make validate` afterwards. Do not copy `metadata.yaml`,
`paper/` or `analysis/`: they hold your work.

## Version-specific notes

For the v1 to v2 metadata change, follow `docs/migrating-to-v2.md` in the
generated repo instead; it has a field-by-field mapping.
