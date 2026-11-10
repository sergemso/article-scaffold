# What the source store and the ledger add to a repository

Date: 2026-11-09. Plan step: 2.1, `docs/plans/token-economy-followup.md`.
Read-only measurement of `articles.bridge_contract_for_agent_session_governance`
at `cdaef0d` (master). No code changed.

## Figures

**`paper/sources/`: 9.42 MB on disk, 49 tracked files.**

| Part | Files | Bytes | Share of the store | gzip of the part |
|---|---|---|---|---|
| raw (`raw.*` per edition) | 11 | 3,480,665 | 60% | 1.33 MB |
| normalized text | 11 | 1,304,923 | 22% | 0.35 MB |
| locators (`locators.json`) | 11 | 1,027,269 | 18% | 0.18 MB |
| store total (11 sources, 1 edition each) | 33 | 5,812,857 | | 1.85 MB |
| older flat copies and notes (`draft-*.txt`, pdf, html, `MANIFEST.md`, `NOTICE.md`, `manifest.json`) | 15 | 3,510,326 | | |

The flat copies predate the store (they are in `bc0fd54^`). All 11 store `raw`
files are byte-identical to a flat copy (11 blob hashes occur twice in
`git ls-files -s`), so the raw bytes are on disk twice but are one object in git.

**`docs/ledger/`: 23 files, 7,247 bytes** (149 to 615 bytes each; one `README.md`,
the rest verdicts and `.prov.json` files, no check outcomes yet). `du` reports 55 KB
because of filesystem blocks.

**Repository** (`git count-objects -vH` now: 12.38 MiB loose, 3.15 MiB in one pack).
Size and time of `git pack-objects` over everything reachable, a proxy for a
fresh clone (no network measured):

| Commit | Pack bytes | Time |
|---|---|---|
| `bc0fd54^` (before adoption) | 4,079,855 | 0.91 s |
| `bc0fd54` (adoption) | 4,483,092 | 0.74 s |
| `HEAD` | 4,588,317 | 0.94 s |

The adoption commit added 57 files and 108,510 lines to `paper/sources` and
`docs/ledger`: +0.40 MB packed (+10%). Clone time is below a second at this size
and the three timings sit inside their own noise.

**One added edition.** No source has a second edition yet (one hash directory per
key), so a real edition diff does not exist. The mean edition here is raw 316 KB
plus normalized 119 KB plus locators 93 KB, 528 KB on disk and about 168 KB
gzipped. Locators are the largest part after raw for text sources (`I-D.hood-agtp`:
306 KB of locators for a 453 KB raw file). A re-fetch that changes one line still
adds a whole new set of three files; git's delta compression recovers most of the
text editions, little of a PDF.

**Growth for 20 sources with 3 editions each** (60 editions, from the means above):
31.7 MB on disk, 10 MB gzipped as a ceiling (about 1.3 MB per 20 editions less if
git deltas the text editions; PDFs do not delta). The ledger stays small: at 300
bytes a file, 2,000 verdicts are 0.6 MB.

**Companion export.** `companion --plan` lists 290 files and none under
`paper/sources/` or `docs/ledger/`. Both directories stay out of the public
companion.

## Reading

1. **The cost is small now and bounded later.** Plus 0.4 MB in a 4.6 MB pack, and a
   projected tens of MB on disk for a large source set. Nothing needs a change for
   size or clone time at the sizes this plan expects. One run, one repository.
2. **Diff noise is the real cost.** A new edition adds three files and about 50 to
   100 KB of locator JSON that no one reviews. Pull requests that re-fetch a
   source will be dominated by it. Two cheap options, neither needed yet:
   mark `paper/sources/**/locators.json` as `linguist-generated` in
   `.gitattributes` so hosts fold the diff, or store locators only on demand and
   keep `normalized.txt` and `raw.*` (the machines without `pdftotext` need the
   normalized text, not the locators).
3. **The flat copies duplicate the store's raw bytes** (3.5 MB on disk, free in
   git). Whether to remove them is a decision for the article's source layout
   (`MANIFEST.md` points at them), not a token or size problem.
4. **Old editions:** pruning is not worth building before an article holds more
   than a few editions per source.

Decision for the plan: no code change; the `.gitattributes` fold for locators is
the only candidate and can wait until the first re-fetch shows the noise.
