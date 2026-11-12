# Dialectic: map the niche's tensions, move them, develop the chain, open the thesis

Use this when a work order of the `dialectic` stage names you (`flow next` gives `map-contradictions`, `move-contradiction`, `develop-move` or `trace-thesis`), or when the author asks for a dialectic pass. Do one order, then stop. The stage runs before the thesis is fixed: nothing you write here is the thesis; it is what the thesis will have to answer.

You propose. You never accept. Every contradiction, move and node you write has `status: proposed`; promoting one is the author's own command (`theses accept`), which you do not run. The stage closes when a person has accepted the items and recorded `python3 -m scripts.article flow attest dialectic --by NAME --why TEXT`; you do not run that either.

## Inputs you may read

- The order and its brief: `python3 -m scripts.article flow next --brief`. Start from it and read nothing it already shows.
- `python3 -m scripts.article theses dialectic` (contradictions, the chain of moves in order, which thesis each opening opens, the gaps) and `theses gaps` (kinds `niche-unmapped`, `contradiction-unmoved`, `move-without-opening`, `opening-undeveloped`, `thesis-untraced`, `thesis-restates-pole`).
- `python3 -m scripts.article theses slice <id> --depth 2` for the ids the order names.
- Sources already in `paper/sources/`, read once, by the `reading-a-source` procedure (`docs/procedures/reading-a-source.md`): `python3 -m scripts.article sources find <terms>`, then `python3 -m scripts.article sources slice <key@hash#locator>`. Fetch nothing new; never open a whole source.
- `source-claim` nodes already in the map.

Do not read `paper/article.tex` or whole section files. At the order's `max_calls`, stop and run `python3 -m scripts.article flow handoff <order-id> --file -`.

## Before any order

1. Run `python3 -m scripts.article theses lint`. If it fails, report the diagnostics and stop; do not edit around them.
2. Run `python3 -m scripts.article theses dialectic` to see what the map already holds. Do not propose what is already there.

## Writing items

Write every item with `python3 -m scripts.article theses add --section contradictions|moves|nodes --file -` and JSON on stdin (one object, or a list). The command refuses an item that would not validate and writes `status: proposed` for you. Each item needs an `id` (one namespace with all node ids: lowercase, unique), a one-line `text`, and `author: agent`. Add no field the schema (`schemas/theses.schema.json`) does not list. Do not edit `theses.yaml` by hand, and never edit, retire or delete an item you did not write.

A contradiction has two `poles`, each anchored to exactly one of `claim: <source-claim id>` or `niche: <one line>`, and a `kind`:

- `dialectical`: two positions that exclude each other.
- `technical`: improving one thing worsens another; add `improving` and `worsening` (one line each) and, if one fits, `principle`, a tag from `schemas/triz-principles.json`.
- `physical`: one property is needed both ways; `principle` is optional.

A technical or physical contradiction may add `ideal-result` (one line) and `resources` (a list of one-line items).

A move has a `type` and, except for an `opening` that starts from nothing, `cites` (contradiction and move ids):

- `negation`: cites a contradiction and rejects one pole, saying why that pole cannot stand as stated.
- `negation-of-negation`: cites the `negation` it answers (it must cite a prior negation) and rejects the rejection: what the negated pole was right about.
- `synthesis`: cites at least two contradictions or moves and joins them into one position. Use it when you can say how they fit but not yet what is dropped.
- `aufhebung`: cites at least two and records all three of `preserved` (what is kept), `cancelled` (what is dropped) and `lifted` (what rises to a higher level and was said by neither pole). Prefer it over `synthesis` whenever you can name all three. `lifted` must not repeat `preserved`, `cancelled` or a pole of a contradiction it cites (lint error T095).
- `opening`: opens a thesis or hypothesis node through `opens: <id>` and cites the move it follows; an `opening` must cite the move it follows, or `move-without-opening` fires for that move.

## The orders

### `map-contradictions` (gap `niche-unmapped`)

The map has source-claims or stored sources and no contradiction. Niche scan: from the source-claims and the sources the order names, list what the field already says and where two accounts pull apart. Topic scan: do the same for the article's own topic, to find tensions the niche leaves open. Propose at least one contradiction, and no more than you can anchor: every pole points at a `source-claim` or states the niche position in one line. Add a `source-claim` node (verbatim `quote`, `locator`, `bib_keys`) when a pole rests on a passage you read and no claim exists for it yet.

### `move-contradiction` (gap `contradiction-unmoved`)

One contradiction no live move cites. Propose the move the material supports: usually a `negation` of the weaker pole, or a `synthesis` or `aufhebung` when this contradiction and another already moved one resolve together. Do not invent a move to fill a type; if nothing can be grounded, say so in your report and propose nothing.

### `develop-move` (gaps `move-without-opening`, `opening-undeveloped`)

The chain stops short. For `move-without-opening`, the named move is cited by nothing: continue it (a `negation-of-negation` answering a negation, a `synthesis` or `aufhebung` joining it with another move or contradiction) or, when it already resolves the tension, propose the `opening` that follows it. For `opening-undeveloped`, the named opening has nothing but bare negations behind it, so the thesis it opens is the other pole restated: propose the `negation-of-negation`, `synthesis` or `aufhebung` the opening should follow, and a new `opening` citing it. Leave the old opening alone; the author retires it.

### `trace-thesis` (gaps `thesis-untraced`, `thesis-restates-pole`)

A thesis has no `opening`, or the thesis an opening opens repeats a pole. For `thesis-untraced`, propose the `opening` that reaches it from the chain, citing the move it follows; if the chain cannot reach the thesis, say so in your report. A thesis that was fixed by the call for papers or a prior decision needs a one-line `untraced-reason` on the node; the author writes that, not you. For `thesis-restates-pole`, propose a new `thesis` node (`--section nodes`, `status: proposed`) that says what the move behind the opening lifted, and a new `opening` for it. Never edit the old thesis.

## Development checks

Three checks guard development; write so they pass. `opening-undeveloped` fires when nothing behind an `opening` is a `synthesis`, `aufhebung` or `negation-of-negation`. `thesis-restates-pole` fires when an opened thesis, with case, punctuation and spacing folded, equals a pole text behind its opening, or contains it, or is contained in it (containment counts when the shorter text has at least three words). T095 rejects an `aufhebung` whose `lifted` repeats its `preserved`, its `cancelled` or a pole of a contradiction it cites. A thesis that passes these can still be weak; the author judges that.

## After the order

1. Run `python3 -m scripts.article theses lint`; fix your own items until it passes.
2. Run `python3 -m scripts.article theses gaps` and `theses dialectic`.
3. Run `python3 -m scripts.article flow done <order-id>`. If it fails, read the output, fix your own items, run it again.
4. Stop. Report the order id, the ids you added, which move type you could not ground and why, and the gaps left. Ask a person to accept the items and attest the stage.

## Never

- Set `status` to anything but `proposed`, or write `accepted-by`.
- Edit, retire or delete an item you did not write; edit `theses.yaml` by hand.
- Put source text in a pole or `text` beyond one line.
- Fetch, OCR or reread a source that is already read.
- Take a second order in the same pass.
