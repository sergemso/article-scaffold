# Migrating from v1 to v2

> **Important**: There is **no automated migration tool** and none is planned.
> This guide provides a complete manual mapping for users who want to upgrade
> their v1 `metadata.yaml` to the v2 format. The v2 schema is a breaking
> change that prioritizes correctness and extensibility over backward
> compatibility.

---

## Overview of Changes

| Aspect | v1 (Legacy) | v2 (Current) |
|--------|-------------|--------------|
| Authors | Single `author` object | `authors` list + `affiliations` map |
| Affiliations | Inline in author | Separate `affiliations` map with IDs |
| ORCID | Optional string in author | Required format validation per author |
| Manuscript type | Free-text `manuscript_type` | Structured `manuscript_kind` (enum) |
| Citations | Implicit numeric | Explicit `citation_style` (numeric/author-year) |
| Dates | Free text | ISO 8601 (`YYYY-MM-DD`) |
| License | Free text | SPDX identifier (enum) |
| DOI | Free text | Validated DOI format |
| Keywords | Comma-separated string | List or comma-separated string |
| Abstract | `description` or `abstract` | `abstract` field only |

---

## Field-by-Field Mapping

### Author Information

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `author.name` | `authors[0].name` | Full name; split into given/family |
| `author.orcid` | `authors[0].orcid` | Must be valid ORCID checksum |
| `author.affiliation` | `authors[0].affiliations[0]` + `affiliations` map | See Affiliations below |

**v1 Example:**
```yaml
author:
  name: "Ada Lovelace"
  orcid: "0000-0002-1825-0097"
  affiliation: "Analytical Engine Institute"
```

**v2 Equivalent:**
```yaml
authors:
  - name: "Ada Lovelace"
    given: "Ada"
    family: "Lovelace"
    orcid: "0000-0002-1825-0097"
    email: ""
    affiliations: ["aff1"]
    affiliation_names: ["Analytical Engine Institute"]
    corresponding: true
    ror: ""

affiliations:
  aff1:
    name: "Analytical Engine Institute"
    ror: ""
```

> **Note**: The v2 schema splits the author's full name into `given` and `family` names.
> The migration tool would need to guess the split; manual review is required.

### Affiliations

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `author.affiliation` | `affiliations.<id>.name` | New `affiliations` map with IDs |
| N/A | `affiliations.<id>.ror` | Optional ROR identifier |

```yaml
# v2
affiliations:
  aff1:
    name: "Analytical Engine Institute"
    ror: "https://ror.org/00000001"
```

### Manuscript Type & Kind

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `manuscript_type` | `manuscript_type` (unchanged) | Free-text label for README |
| N/A | `manuscript_kind` | **Required**: `perspective`, `empirical`, or `review` |

```yaml
# v2
manuscript_type: "Perspective Essay"
manuscript_kind: "perspective"  # or "empirical", "review"
```

### Citation Style

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| N/A | `citation_style` | **Required**: `numeric` or `author-year` |

```yaml
citation_style: "numeric"  # or "author-year"
```

### Dates

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `date` | `date` | Must be ISO 8601: `YYYY-MM-DD` |

```yaml
date: "2024-03-15"
```

### License

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `license` | `license` | Must be SPDX identifier: `CC-BY-4.0` or `MIT` |

```yaml
license: "CC-BY-4.0"
```

### DOI

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `doi` | `doi` | Validated DOI format (e.g., `10.1234/example`) |

```yaml
doi: "10.1234/example.2024"
```

### Keywords

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `keywords` | `keywords` | Comma-separated string or YAML list |

```yaml
# Either format works
keywords: "machine learning, neural networks"
keywords: ["machine learning", "neural networks"]
```

### Abstract

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `description` or `abstract` | `abstract` | Single field `abstract` |

```yaml
abstract: "This paper presents..."
```

### Other Fields

| v1 Field | v2 Path | Notes |
|----------|---------|-------|
| `github_user` | `github_user` | Unchanged |
| `repo_name` | `repo_name` | Unchanged (default: `articles.<topic>`) |
| `title` | `title` | Unchanged |
| `subtitle` | `subtitle` | Unchanged |
| `version` | `version` | Semantic version (e.g., `1.0.0`) |
| `version_label` | `version_label` | Unchanged |
| `target_deposit` | `target_deposit` | Unchanged |
| `doi` | `doi` | Validated DOI format |
| `abstract` | `abstract` | Renamed from `description` |
| `keywords` | `keywords` | List or comma-separated string |
| `manuscript_type` | `manuscript_type` | Unchanged (display label) |
| `manuscript_kind` | `manuscript_kind` | **New required field** |

---

## Complete Before/After Example

### v1 `metadata.yaml` (Legacy)

```yaml
topic: "ai_governance"
repo_name: "articles.ai_governance"
github_user: "myusername"
title: "From AI Scaling to AI Governance"
subtitle: "Technological Revolutions and the Political Economy of Deployment"
manuscript_type: "Perspective / Review Essay"
author_name: "Ada Lovelace"
author_orcid: "0000-0002-1825-0097"
author_affiliation: "Analytical Engine Institute"
version: "1.0.0"
version_label: "v1 preprint"
date: "2024-01-15"
license: "CC-BY-4.0"
target_deposit: "Zenodo"
doi: ""
keywords: "AI governance, regulatory capture, Carlota Perez"
abstract: "This paper examines..."
```

### v2 `metadata.yaml` (Current)

```yaml
topic: "ai_governance"
repo_name: "articles.ai_governance"
github_user: "myusername"
title: "From AI Scaling to AI Governance"
subtitle: "Technological Revolutions and the Political Economy of Deployment"
manuscript_type: "Perspective / Review Essay"
manuscript_kind: "perspective"
citation_style: "numeric"
authors:
  - name: "Ada Lovelace"
    given: "Ada"
    family: "Lovelace"
    orcid: "0000-0002-1825-0097"
    email: ""
    affiliations: ["aff1"]
    affiliation_names: ["Analytical Engine Institute"]
    corresponding: true
    ror: ""
  # Add more authors here as needed
affiliations:
  aff1:
    name: "Analytical Engine Institute"
    ror: ""
version: "1.0.0"
version_label: "v1 preprint"
date: "2024-01-15"
license: "CC-BY-4.0"
target_deposit: "Zenodo"
doi: ""
keywords: "AI governance, regulatory capture, Carlota Perez"
abstract: "This paper examines..."
manuscript_kind: "perspective"
citation_style: "numeric"
```

---

## Migration Steps

Since there is **no automated migration tool**, follow these manual steps:

1. **Backup your v1 `metadata.yaml`**
   ```bash
   cp metadata.yaml metadata.yaml.v1.backup
   ```

2. **Create a new v2 `metadata.yaml`**
   - Copy the v2 template above
   - Fill in each field using the mapping table above
   - Pay special attention to:
     - Splitting author name into `given`/`family`
     - Creating the `affiliations` map with IDs
     - Setting `manuscript_kind` (`perspective`, `empirical`, or `review`)
     - Setting `citation_style` (`numeric` or `author-year`)
     - Using ISO 8601 date format (`YYYY-MM-DD`)

3. **Validate the new metadata**
   ```bash
   python3 -m scripts.article validate
   python3 -m scripts.article metadata --check
   ```

4. **Regenerate derived files**
   ```bash
   make metadata
   ```

5. **Verify the build**
   ```bash
   make pdf
   ```

5. **Commit the changes**
   ```bash
   git add metadata.yaml
   git commit -m "chore: migrate metadata.yaml to v2 schema"
   ```

---

## Why No Automated Migration Tool?

The v2 schema introduces structural changes that require human judgment:

1. **Name splitting**: Automatically splitting "Ada Lovelace" into `given: "Ada"` and `family: "Lovelace"` works for Western names but fails for mononyms, Eastern names, or names with particles (e.g., "von Neumann", "de la Cruz").

2. **Affiliation mapping**: v1 has a single affiliation string; v2 requires creating an affiliation map with IDs and optional ROR identifiers. This requires human knowledge.

3. **Manuscript kind inference**: v1's `manuscript_type` is free text; v2 requires choosing from a fixed enum. Automatic inference is error-prone.

3. **Citation style**: v1 implied numeric citations; v2 makes this explicit. The choice affects bibliography formatting.

**Decision**: Rather than ship a fragile migration tool that produces subtly broken metadata, we require manual migration with full human review. The v2 schema is designed to be explicit and self-documenting, making manual migration straightforward.

---

## Verification Checklist

After migration, verify:

- [ ] `python3 -m scripts.article validate` passes with no errors
- [ ] `python3 -m scripts.article metadata --check` reports no drift
- [ ] `make pdf` builds successfully
- [ ] `make validate` passes
- [ ] Generated `CITATION.cff` has correct author list and ORCIDs
- [ ] Generated `.zenodo.json` has correct creators and affiliations
- [ ] README citation block matches `metadata.yaml`
- [ ] `paper/article.pdf` builds without warnings

---

## Rollback Procedure

If migration causes issues:

```bash
git checkout metadata.yaml.v1.backup
make metadata
make pdf
```

The v1 `metadata.yaml` is still compatible with the legacy `scripts/generate-metadata.py` shim.

---

## Support

If you encounter issues during migration:

1. Check `python3 -m scripts.article validate` output for specific errors
2. Compare your `metadata.yaml` with the v2 example above
3. Open an issue in the article-scaffold repository with your `metadata.yaml` (redacted) and error output