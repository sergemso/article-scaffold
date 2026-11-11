# Public companion repo

Zenodo only archives public repos, so a final release is mirrored to a public companion
repo. `companion.yaml` at the repo root controls it:

- `repo` and `branch`: the companion and the branch that receives the snapshot.
- `include`: globs that are published. `exclude`: deny globs that beat `include`.

The file is yours after the first render; `upgrade` never overwrites it.

## `paper/sources/` is private

`paper/` is published, but `paper/sources/` is not: the template excludes
`paper/sources/**`, and `--build` fails if any file under it would be copied, even when your
`companion.yaml` lacks the exclude. The source store may only hold text you may keep (for
example CC BY); third-party PDFs you may not redistribute belong in a private repo, never in a
published one. `refs.bib` is published, so a note there such as "full text stored in
`paper/sources`" points at files readers cannot see.

## Check what would be published

```bash
python3 -m scripts.article companion --plan          # resolved files and what was dropped
python3 -m scripts.article companion --gate v1.0.0   # would this tag publish?
python3 -m scripts.article companion --build snap --artifacts DIR   # write the snapshot
```

`--build` fails if the snapshot holds an excluded path, this repo's private name or URL, or a
secret-looking string. `--json` prints the file list with hashes and a `tree_sha256`.

## Release flow

Publishing runs from the scaffold repository, not from this one, so this repo holds no
publishing credential. After tagging a final `vX.Y.Z` equal to the `version` in
`metadata.yaml`, the owner dispatches the scaffold's `publish-companion.yml` with this repo,
the tag and `dry_run`. It builds the PDF and DOCX, applies the same gate, commits the
snapshot to the companion as `release vX.Y.Z`, tags it and creates a GitHub Release with the
PDF and DOCX, which Zenodo archives. Other tags (release candidates, mismatches) never
publish. Re-running a published tag is a no-op.

To rehearse, dispatch it with `dry_run` on (the default) and read the uploaded snapshot
artifact. An older repo that still has `.github/workflows/publish-companion.yml` loses it on
the next `upgrade`.
