# Interpretive fidelity of quoted sources: editions, translations, context

Status: proposal for the owner to accept as a decision. It extends decision 0067 (tiered local claim checks) and decision 0065 (`source-claim` nodes), and feeds step 2.1 (schema), step 2.4 (quote match) and step 3.4 (claim-check skill). No code changes.

## Problem

Decision 0067 assumes a `source-claim` has one verbatim quote at one locator in one local text, and that tier 2 can answer `supports`, `overstates` or `contradicts` from that excerpt. That holds for a modern article with stable pagination. It breaks when meaning depends on:

- **Edition.** Page numbers differ between printings; a later edition may have changed the passage; a critical edition numbers by section or line, not page.
- **Translation.** The paper quotes a translation, but the claim rests on what the original says. A word that carries the argument may be a translator's choice.
- **Context.** A sentence is quoted accurately but is a view the author is about to reject, a concession, an example, or an irony. Three verdicts cannot express "accurate quote, wrong use".
- **Reception.** A claim about what a work "holds" rests on a reading, not a sentence; the quote is evidence for it, not the claim.

## Proposal: node fields on `source-claim`

All new fields are optional so existing nodes stay valid.

```yaml
- id: src-example
  type: source-claim
  quote: "..."                      # verbatim, as in 0065
  locator: {edition: ed-2nd, page: 114}      # structured instead of a free string
  bib: smith1999                    # the bib key the paper cites
  rests-on:                         # what the claim actually needs from the source
    kind: wording                   # wording | argument | doctrine | fact
  edition-map:                      # how this locator maps in other editions
    - {edition: ed-1st, page: 98}
    - {edition: critical, section: "4.2"}
  translation:                      # present only when the quote is not in the source language
    of: smith1999-orig              # id of a source-claim or source entry for the original
    translator: "Jones"
    original-quote: "..."           # verbatim original, local text
    load-bearing-terms:             # words the claim depends on
      - {rendered: "reason", original: "ratio", note: "also 'proportion'"}
  context:
    stance: asserts                 # asserts | reports | concedes | rejects | example | ironic
    scope-note: "Applies to the case of contracts, not to wills."
    window: {before: 1, after: 1}   # sentences of context to pass to tier 2
  reading: direct                   # direct | paraphrase | interpretive
```

Notes:

- `locator` as a map keeps today's string form valid (a string is read as `{page: ...}` or as an opaque locator). The quote matcher then searches the text file that belongs to the named edition. Source texts are filed per edition under `paper/sources/` (for example one file per edition, named by the edition key); the node names the edition its quote came from.
- `edition-map` is author-supplied. No tool guesses a mapping between editions.
- `translation` makes the translation a first-class link: the quote matched at tier 1 is the translated text, and a second tier-1 match runs on `original-quote` when the original is available locally.
- `stance` is an author judgment recorded once and then used to steer tier 2; it is not inferred.
- `reading` says how the paper uses the source: `direct` (the quoted words are the claim), `paraphrase` (the claim restates them), `interpretive` (the claim is a reading the quote supports).

## Tier rules

Tiers keep decision 0067's order and locality. Every tier reads local text only.

**Tier 1 (script).**
1. Match `quote` at `locator` in the named edition's file; fail if the edition has no local text (listed, not guessed, as in 0067).
2. If `translation` is present, also match `original-quote` in the original's file when it exists; if not, report `original-unavailable`, which is advice, not an error.
3. Check structure: `edition-map` entries name known editions; `load-bearing-terms` strings occur in the respective quotes; `stance` is present when `reading` is `interpretive`.
4. Report quote drift: the quote matches only after normalisation of quotation marks, dashes, hyphenation or ligatures (report the normalisation used so a reviewer sees it).

**Tier 2 (small local model).** Input is the claim wording, the quote with its window of context, the `stance`, `scope-note`, and for translations the original-quote and the load-bearing terms. Verdict set extends 0067:

| Verdict | Meaning |
|---|---|
| `supports` | The excerpt, read in its stance, supports the claim. |
| `overstates` | The claim is stronger than the excerpt (as in 0067). |
| `contradicts` | The excerpt says the opposite (as in 0067). |
| `out-of-context` | The quote is accurate but the stance or window shows it is not the author's own view or does not apply to the claim's scope. |
| `translation-sensitive` | The claim depends on a rendering the original does not clearly bear (a load-bearing term has other plausible readings). |
| `needs-wider-context` | The window is too small to judge. The tool asks for a larger window, once, then reports `unclear`. |

The charitable-reading step is a fixed two-pass prompt: first state the strongest reading of the excerpt that the author could accept, then judge whether the claim is within it. A claim that holds only on an uncharitable reading of the source is `overstates`; a claim that holds only on a reading the source rules out is `contradicts`. `reading: interpretive` claims are never marked better than `supports-with-reading`; they always route to tier 3.

Cache key is the hash of claim text, excerpt, window, stance and original-quote, so any change to the context fields invalidates the cached verdict.

**Tier 3 (human attestation).** Required for: any `interpretive` reading; any `translation-sensitive` or `out-of-context` verdict that the author wants to keep; any claim whose edition cannot be verified locally. The attestation records who, when, why, and which edition and translation were consulted.

## What remains human judgment

- Whether a rendering is faithful enough, and whether the original carries the word the argument needs. Tier 2 can flag sensitivity; it cannot adjudicate scholarship.
- Whether a passage is representative of the author's view across a corpus, and whether a contested interpretation is the right one to adopt.
- Choice of edition for the claim, and the mapping between editions when a passage changed.
- Whether an `example` or `concede` stance still allows the paper's use.
- Any claim about intent, influence or reception.

## Limits and failure modes

- A small local model is unreliable on non-English originals and on archaic text. For those, tier 2 is advisory and a missing tier-2 result does not block; tier 3 is required instead.
- Matching the original-quote only proves the original says that; it does not prove the translation renders it fairly.
- Structured locators add burden for authors who cite one edition only. The defaults (one edition, no translation, `stance: asserts`, `reading: direct`) must cost nothing to leave out.

## Open choices for the owner

- Whether edition texts live as separate files per edition or as sections of one file; this note assumes separate files.
- Whether `reading: interpretive` should be a node type of its own (a claim about the source) linked to the quote as evidence, rather than a field. The field is cheaper; the node type is cleaner if interpretive claims are frequent.
- Whether `needs-wider-context` should widen automatically (once) or only report.
