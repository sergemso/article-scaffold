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
| `related_identifiers` | Links to other records, for a series or a chain of versions. A list of `identifier`, `relation` and `scheme` (`doi` or `url`), copied into `.zenodo.json`. See [Linked articles](#linked-articles). |
| `description` | Legacy alias of `abstract`; still read, no longer written. |

## Linked articles

`related_identifiers` publishes links to other records with the Zenodo deposit.

```yaml
related_identifiers:
  - identifier: 10.5281/zenodo.1234567   # this article is part 2 of a series
    relation: isPartOf
    scheme: doi
  - identifier: 10.5281/zenodo.2345678   # it continues part 1
    relation: continues
    scheme: doi
  - identifier: 10.5281/zenodo.3456789   # it replaces an earlier article
    relation: obsoletes
    scheme: doi
```

- `relation` is one of `isPartOf`, `hasPart`, `continues`, `isContinuedBy`,
  `isNewVersionOf`, `isPreviousVersionOf`, `obsoletes`, `isObsoletedBy`,
  `isSupplementTo`, `isSupplementedBy`, `references`, `isReferencedBy`,
  `isDocumentedBy`.
- Point at a DOI (`10.NNNN/suffix`; a leading `https://doi.org/` or `doi:` is
  stripped) or a public `https` URL. A URL under your GitHub account is accepted only
  when it is the public companion repo; the private article repo and other repos of
  yours fail `make validate` with the entry named.
- Each article declares its own side of a link. A successor that has no DOI yet is
  added to this article (`isContinuedBy`) in a later version, once the successor is
  published.
- The links go to `.zenodo.json` only. They are not rendered in `CITATION.cff`, the
  README or the title page.
- `upgrade` never rewrites `metadata.yaml`; add the key by hand.
