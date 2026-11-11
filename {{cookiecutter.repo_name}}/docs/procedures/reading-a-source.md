# Reading a source

A source is read once. Its text is extracted once, kept in the repo, and every later read is a slice of that text. Fetching or OCRing a source that is already stored wastes the cost twice and leaves a second copy nobody can check.

## Before you read

1. Run `python3 -m scripts.article sources list`. A source with `readable: true` has stored text; `read` lists what has been covered and by whom, and `unread_pages` what has not.
2. Never fetch, download or OCR a source whose key is in that list. If a file you hold is not yet stored, `python3 -m scripts.article sources add FILE --origin ... --edition ...` then `python3 -m scripts.article sources index KEY`; a scan is OCRed there, once, when `pdftoppm` and `tesseract` are installed, and the text is kept (re-running `index` reuses it; `--force` is for a person). Fetching a source that is not stored is a separate, confirmed step; it is not part of this procedure.
3. A PDF's text has `[page N]` marker lines and is in reading order, not interleaved columns. A scan's OCR is lossy: say so in the report and do not quote it as exact.

## Read only what is unread

- Pages: `python3 -m scripts.article sources slice KEY --pages 4-6`. A section: `python3 -m scripts.article sources slice KEY --section 3.2`. Where a term is: `python3 -m scripts.article sources find TERMS --key KEY`, then `python3 -m scripts.article sources slice KEY@hash#locator`. Each answer is capped; ask for the next range rather than the whole text.
- Skip ranges `read` already covers, unless the question is about what that range says; then slice it, do not re-extract.
- Never open `paper/sources/` files directly and never read a whole source.

## Record what you read, then report

Before you report, record the coverage, even when you read little:

```bash
python3 -m scripts.article sources read KEY --pages 1-5 --by model --note "appendices not read"
python3 -m scripts.article sources read KEY --section 3.2 --by owner --verified
```

`--by` says who read it (`model` or `owner`); `--verified` means the reading was checked against the stored text. Coverage is refused for a source with no stored text. Say in the report which ranges you read and which you did not.

## Briefing a subagent

Name the key, the slice commands for the ranges it should read, and the questions. Do not ask it to fetch, download or OCR the source. Ask it to record its coverage with `python3 -m scripts.article sources read ... --by model`, and to quote only text it got from a slice, so that its claims can be spot-checked with `python3 -m scripts.article sources slice` rather than a re-fetch.

## Privacy

`paper/sources/` is private. It is excluded from the public companion release, and only text you may keep (for example CC BY) belongs in it. A third-party PDF you may not redistribute stays in a private repo; do not add it to a repo whose sources directory is published. A note in `refs.bib` that says full text is stored in `paper/sources` points at files readers cannot see.
