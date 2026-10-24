# Upgrading a generated repo

A generated article repo is archival: it has no runtime dependency on this
template and is never updated automatically. When a template fix matters to
you, you can pick it up by hand with a three-way merge. Nothing here merges
for you.

## What the repo records

`template.json` at the generated repo root records how it was made:

| Key | Meaning |
|---|---|
| `template` | Where the template was rendered from (path or URL) |
| `template_version` | Template version (`pyproject.toml`) at generation time |
| `template_commit` | Template git commit, or `null` for a non-git source |
| `context.cookiecutter` | Every prompt answer used to render the repo |

## Why not cruft or Copier

- **cruft** is the nearest fit. It stores the same information (template,
  commit, context) and does a three-way update. It is not required here: it
  would add a tool to every repo that is meant to stay dependency-free, and
  its update step merges automatically.
- **Copier** needs the template converted to `copier.yml` and would replace the
  Cookiecutter prompts and hooks. Too invasive for a fix-pickup path.

`template.json` follows the cruft layout (`template`, `commit`, `context`), so
a team that wants cruft can adopt it later without re-stamping.

## Three-way merge (recommended)

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

## Manual fallback

If the merge is not worth it, read the release notes and copy only the files
you need (usually `scripts/`, `.github/workflows/` and `Makefile`). Run
`make metadata` and `make validate` afterwards. Do not copy `metadata.yaml`,
`paper/` or `analysis/`: they hold your work.

## Version-specific notes

For the v1 to v2 metadata change, follow `docs/migrating-to-v2.md` in the
generated repo instead; it has a field-by-field mapping.
