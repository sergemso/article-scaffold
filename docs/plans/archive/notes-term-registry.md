# Term registry: defined terms, first-use anchors and a consistency lint

Status: proposal for the owner to accept as a decision. It extends decision 0065 (nodes and edges) and feeds step 2.1 (schema) and step 2.3 (section index). No code changes.

## Problem

A paper that defines its own vocabulary can fail in three quiet ways: a term is used before it is defined, a term is used in two senses, or a definition is restated with a small change that nobody notices. Reviewers find these by reading; a cheap linter can find the first two shapes and flag candidates for the third.

## How the article repo defines terms today

Read from `A/paper/sections/`, not copied:

- Formal definitions use the `definition` environment with a title and a label of the form `def:<slug>` (for example the bridge component, the responsibility gap, the contract, the session identity descriptor, the resume record, the state machine, the Merkle constructions, the deployment profile). They sit in sections 02, 03, 04, 05 and 13.
- Terms are named inside the environment by `\emph{...}` on first mention (the bridge, the responsibility gap). The same `\emph` is used elsewhere for plain emphasis (in the introduction it marks the title of the contract and several positioning phrases), so `\emph` alone does not mark a definition.
- Acronyms are expanded in running prose (for example the enforcement component is spelled out once in the introduction). There is no glossary package, no `\gls`, no term macros.
- Gap classes are defined as a `description` list inside one definition, each item a short label plus a sentence. The items are defined terms too, but have no label of their own.
- Some terms come from outside the paper (named protocols). They are cited, not defined.

So the reliable machine signal today is: a `definition` environment with a `\label{def:...}`; everything else is prose.

## Proposal: a `terms` section in the map file

Terms live beside nodes in the same YAML file (decision 0065), not in a second file, so one validation pass covers both and the companion exclusion (step 2.5) applies once.

```yaml
terms:
  - id: term-bridge                 # stable, never reused
    name: bridge                    # canonical surface form
    forms: [bridge, bridges, "bridge component"]   # surface forms the linter searches for
    kind: defined                   # defined | external | acronym
    anchor: def:bridge              # LaTeX \label of the defining environment or section
    definition: A component that mediates between a client transport and an agent runtime.   # short gloss, author-written
    source: null                    # for kind: external, a bibliography key
    senses: []                      # only if the paper deliberately uses the word in two senses
    status: proposed                # proposed | accepted | retired (as other nodes)
    owner: human                    # human | agent; agent entries need promotion (guardrail agent-nodes-need-human-promotion)
```

Rules:

- `anchor` must resolve in the section index (step 2.3) or the term is a gap.
- `kind: external` requires `source`; `kind: defined` requires `anchor`; `kind: acronym` requires `expansion`.
- `senses` is the author's explicit declaration that a word has more than one meaning, each with its own anchor. Without it, a second defining site is a conflict.
- Nodes may name terms they rely on: `terms: [term-bridge]` on a node. This lets a slice (step 2.2) carry the definitions an agent needs, and nothing else.

## Deterministic lint (tier 0, no model)

All checks read the section index and the `.tex` sources; none needs the network.

1. **Dangling anchor.** A term's `anchor` is not a known label. Error.
2. **Use before definition.** The first occurrence of any `forms` entry, in document order across `paper/sections/NN_*.tex`, precedes the anchor's position. Warning, error for `kind: defined` once the author has accepted the term.
3. **Second defining site.** A `definition` environment whose title or first `\emph` matches a registered form, but whose label is not the term's anchor. Warning.
4. **Unregistered definition.** A `definition` environment with a label that no term anchors. Gap, reported by `theses gaps` like other missing links.
5. **Orphan term.** A registered term never used outside its own definition. Info; the paper may be carrying dead vocabulary.
6. **Case and plural drift.** Forms are matched case-insensitively with the listed plurals; a capitalised variant that is not in `forms` (for example a title-cased name used as a proper noun) is reported as a form to add or a drift to fix. Info.

Output is a list of `(term, check, file:line)`, small enough to hand to an agent without reading the paper.

## Tier-2 sense-drift check

Tier 2 follows decision 0067: local model, input stays local (guardrail `claim-check-input-stays-local`), verdict is advice, never an edit.

- Input: the term's `definition` gloss, the defining paragraph, and up to a small fixed number of other usage windows chosen by the lint (windows around occurrences, a few sentences each). The paper is never passed whole.
- Question per window: does this use match the definition, extend it, or contradict it? Verdicts: `consistent`, `narrower`, `broader`, `different-sense`, `unclear`.
- Output is cached by the hash of the gloss plus window text (the check cache of step 2.4), so an unchanged term costs nothing on re-run.
- Only `different-sense` and `broader` produce a gap; `unclear` is shown but does not block. The agent proposes either a new `senses` entry or a wording fix; a human accepts.

## False-positive risks

- **Common words as terms.** A term such as "contract", "session" or "gap" is also ordinary English. The use-before-definition lint will fire on every casual earlier use. Mitigation: per-term `scope` listing the sections where the technical sense is intended, or a `match: phrase-only` flag so only the full phrase counts. Without one of these the lint is noisy for exactly the most important terms.
- **Forward references by design.** Introductions deliberately use terms before the formal definition and point ahead (`Section~\ref{...}`). Mitigation: an occurrence within a sentence containing a `\ref` or `\cref` to the term's anchor is not a violation.
- **Math and code contexts.** Forms inside `\texttt`, `verbatim`, listings, `$...$`, captions of generated tables, comments and `\label` strings are not prose uses. The scanner must strip them, and even then identifiers such as field names collide with plain words.
- **Generated sections.** Files such as `generated_vectors.tex` are written by scripts and are excluded from the scan.
- **Inflection and abbreviation.** Forms missed by `forms` become false negatives, not positives, but an over-broad form (a common stem) becomes a positive flood. Matching is on whole words only, no stemming.
- **Quoted material.** A term appearing inside a quotation of another author is that author's usage. Skip text in quote environments and `\enquote`/`\quote`-style macros.
- **Multiple `\emph` roles.** Treating `\emph` as a definition marker would flag every emphasis; the proposal therefore never infers a definition from `\emph` alone, only from the `definition` environment or a registered anchor.
- **Sense drift judgments.** Tier 2 will disagree with the author on legitimate narrowing in a specific section. That is why the verdict is advisory and `senses` exists to record intent.

## What stays human judgment

Whether two senses are really one, whether a definition is good, and whether a deliberate early use is acceptable. The registry records the decision; it does not make it.

## Open choices for the owner

- One file or a separate `terms.yaml`. This note assumes one file (see above).
- Whether `description` list items (sub-definitions such as the gap classes) get their own anchors via an inline label, or are registered as children of the parent term.
- Whether the per-term `scope` or `match: phrase-only` is the primary noise control; the proposal prefers `match: phrase-only` as the cheaper default, with `scope` as an override.
