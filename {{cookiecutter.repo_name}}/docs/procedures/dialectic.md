# Dialectic: map the niche's tensions and propose contradictions and moves

Use this when the author asks for a dialectic pass, or when `python3 -m scripts.article theses dialectic` shows gaps. Do one pass, then stop.

You propose. You never accept. Every contradiction and move you write has `status: proposed`; promoting one is the author's own decision, which you do not take. Ask a human to accept them when you finish.

## Inputs you may read

- `python3 -m scripts.article theses dialectic` and `theses gaps` (kinds `niche-unmapped`, `contradiction-unmoved`, `move-without-opening`, `opening-undeveloped`, `thesis-untraced`, `thesis-restates-pole`).
- `theses slice <id> --depth 2` for the nodes you cite.
- Sources already in `paper/sources/`, read once, by the `reading-a-source` procedure (`docs/procedures/reading-a-source.md`): `python3 -m scripts.article sources find <terms>` then `python3 -m scripts.article sources slice <key@hash#locator>`. Fetch nothing new; never open a whole source.
- `source-claim` nodes already in the map.

Do not read `paper/article.tex` or whole section files.

## Steps

1. Run `python3 -m scripts.article theses lint`. If it fails, report the diagnostics and stop.
2. Run `python3 -m scripts.article theses dialectic` to see what the map already holds.
3. Niche scan: from the source claims and the sources, list what the field already says and where two accounts pull apart. Each tension needs two poles.
4. Topic scan: do the same for the article's own topic, to find tensions the niche leaves open.
5. Propose contradictions. Each has two `poles`, and every pole is anchored: `claim: <source-claim id>` or `niche: <one line>`, exactly one of the two. Set `kind`:
   - `dialectical`: two positions that exclude each other;
   - `technical`: also `improving` and `worsening` (one line each), and optionally `principle`, a tag from `schemas/triz-principles.json`;
   - `physical`: one property needed both ways; optional `principle` tag.
   For technical and physical ones you may add `ideal-result` and `resources` (a list of one-line items).
6. Propose moves that cover each of the five types, where the material supports them. Do not invent a move to fill a type; say in your report which type you could not ground.
   - `negation`: cites a contradiction and rejects one pole.
   - `negation-of-negation`: cites a prior `negation` and rejects its rejection.
   - `synthesis`: cites at least two contradictions or moves and joins them. Use `aufhebung` instead when you can say what is kept, dropped and lifted.
   - `aufhebung`: cites at least two and records all three of `preserved`, `cancelled` and `lifted`: what is kept, what is dropped, what rises to a higher level.
   - `opening`: opens a thesis or hypothesis through `opens: <id>`, and cites the move it follows.
7. Write everything by hand into `theses.yaml` under `contradictions:` and `moves:`. `add_nodes` and `theses accept` do not handle these sections yet, so nothing else writes them. Each item needs an `id` (one namespace with all node ids), `text` as one line, `status: proposed`, `author`. Add no field the schema (`schemas/theses.schema.json`) does not list.
8. Run `python3 -m scripts.article theses lint` and fix your own items until it passes.
9. Run `python3 -m scripts.article theses gaps` and `theses dialectic`. An `opening` must cite the move it follows, or `move-without-opening` fires for that move. A thesis with no `opening` needs a one-line `untraced-reason`; do not write one for the author. Three checks guard development: `niche-unmapped` asks for a first contradiction when the map has source-claims and none; `opening-undeveloped` fires when nothing behind an `opening` is a `synthesis`, `aufhebung` or `negation-of-negation` (a thesis opened straight from a bare negation is the other pole); `thesis-restates-pole` fires when an opened thesis, with case, punctuation and spacing folded, equals or contains a pole text behind its opening (or is contained in one of at least three words). The lint error T095 rejects an `aufhebung` whose `lifted` repeats its `preserved`, its `cancelled` or a pole of a contradiction it cites.
10. Stop. Report the ids you added and the gaps left. Ask a human to accept them.

## Closing the stage

The stage is advisory unless `flow.yaml` lists it in `required_stages`. It closes when there are no gaps and a person runs `python3 -m scripts.article flow attest dialectic --by NAME --why TEXT`. You do not run that command.

## Never

- Set `status` to anything but `proposed`, or write `accepted-by`.
- Edit, retire or delete an item you did not write.
- Put source text in a pole or `text` beyond one line.
- Fetch, OCR or reread a source that is already read.
