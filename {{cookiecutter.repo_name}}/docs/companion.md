# Public companion repo

Zenodo only archives public repos, so a final release is mirrored to a public companion
repo. `companion.yaml` at the repo root controls it:

- `repo` and `branch`: the companion and the branch that receives the snapshot.
- `include`: globs that are published. `exclude`: deny globs that beat `include`.

The file is yours after the first render; `upgrade` never overwrites it.

## Check what would be published

```bash
python3 -m scripts.article companion --plan          # resolved files and what was dropped
python3 -m scripts.article companion --gate v1.0.0   # would this tag publish?
python3 -m scripts.article companion --build snap --artifacts DIR   # write the snapshot
```

`--build` fails if the snapshot holds an excluded path, this repo's private name or URL, or a
secret-looking string. `--json` prints the file list with hashes and a `tree_sha256`.

## Release flow

Pushing a `v*` tag runs `publish-companion.yml`. Only a final `vX.Y.Z` equal to the `version`
in `metadata.yaml` publishes: it commits the snapshot to the companion as `release vX.Y.Z`,
tags it and creates a GitHub Release with the PDF and DOCX, which Zenodo archives. Other tags
(release candidates, mismatches) only build. Re-running a published tag is a no-op.

To rehearse, run the workflow by hand (`workflow_dispatch`) with the tag and `dry_run` on
(the default) and read the uploaded snapshot artifact. The workflow needs the repo secret
`COMPANION_TOKEN`, installed by the scaffold's provisioning workflow.
