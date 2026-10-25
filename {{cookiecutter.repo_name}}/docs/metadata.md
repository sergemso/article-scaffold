# metadata.yaml

`metadata.yaml` is the single source for the title block, abstract, version, README
header, `CITATION.cff` and `.zenodo.json`. Edit it, not the generated files.

`make pdf`, `make docx`, `make html`, `make quick` and the CI build regenerate those
files before building, so an artifact never lags behind `metadata.yaml`. A build stops
with the metadata error if the file is invalid. `python3 -m scripts.article build
<kind> --no-regenerate` skips the refresh. On the default branch,
`.github/workflows/metadata-sync.yml` opens (or updates) a pull request on the branch
`metadata/sync` when the committed copies have drifted.

A new repo contains only the keys it uses. Add these when you need them; the full
list is in `schemas/metadata.schema.json`.

| Key | Effect |
|---|---|
| `subtitle` | Printed under the title. |
| `abstract_note` | A paragraph headed "A note on evidence" after the abstract. Omitted when absent or empty. |
| `release_notes` | Markdown printed under the current version heading in `CHANGES.md`. |
| `references` | List of short citations for the `references` field of `.zenodo.json`, for example `"Perez, C. (2002). Technological Revolutions and Financial Capital."`. |
| `communities` | Verified Zenodo community identifiers; the generator never invents one. |
| `description` | Legacy alias of `abstract`; still read, no longer written. |
