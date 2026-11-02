# Blue team: defenses for one gap

Use this when a work order, or the author, names a gap that is an objection with no defense, or a thesis with weak support. Do one gap, then stop.

You propose. You never accept. Every node you write has `status: proposed`; promoting a node is the author's own command (`theses accept`), which you do not run.

## Inputs you may read

- The output of `python3 -m scripts.article theses gaps`.
- The output of `python3 -m scripts.article theses slice <id> --depth 2` for the one gap you take.
- At most the section lines named by the anchor, found through `paper/build/section-index.json` (write it with `python3 -m scripts.article index`). Read those lines only.
- Evidence only through `source-claim` nodes already in the map.

Do not read `paper/article.tex`, whole section files or the bibliography.

## Steps

1. Run `python3 -m scripts.article theses lint`. If it fails, report the diagnostics and stop.
2. Run `python3 -m scripts.article theses gaps`. Take one gap, preferring `objection-undefended`, then `single-source`, then `thesis-unsupported`. Note its id.
3. Run `python3 -m scripts.article theses slice <id> --depth 2`.
4. If the node has an anchor, check the index (`index --check`, rewrite with `index`), look up the line range and read only those lines.
5. Choose one move and draft the node:
   - deny a premise: name the premise and give the reason;
   - distinguish: name the difference that matters;
   - narrow the claim: state the narrower claim and what it gives up;
   - accept the cost: state the cost;
   - cite evidence: point at a `source-claim` node;
   - reformulate: give the new wording.
6. Write one or two `defense` nodes into `theses.yaml` by editing the file: `id` (lowercase, unique), `type: defense`, a one-line `text` that states the move and its cost where it has one, `status: proposed`, an `anchor` naming the section that carries the reply (an existing `\label`), and `bib_keys` for the evidence. Add a `rebuts` edge from the defense to the objection it answers (for a weakly supported thesis, a `supports` edge to the thesis). Add no field the schema (`schemas/theses.schema.json`) does not list.
7. Every piece of evidence a defense relies on must be a `source-claim` node already in the map, joined by a `supports` edge to the defense. If there is none, do not cite the source. Write the defense without it, or stop and report that a `source-claim` node (verbatim `quote`, `locator`) is needed; the claim check (`docs/procedures/claim-check.md`) judges it afterwards.
8. Run `python3 -m scripts.article theses lint`. Fix your own nodes until it passes.
9. Stop. Report the gap id, the ids you added and the move you chose. Do not take a second gap.

## What a good defense is

- It answers one specific objection, not the thesis in general.
- It addresses the strongest form of the objection, not a weaker one. If it argues against a different wording, it fails.
- It carries an anchor: a defense with no place in the paper is an intention.
- It states what it costs when the move gives something up.
- It adds no new unsupported claim. A new factual claim needs its own `source-claim` node or is reported as a new gap.
- It does not contradict an accepted thesis or another defense; say in your report if you could not tell.

## Never

- Cite a source that has no `source-claim` node.
- Set `status` to anything but `proposed`, or write `accepted-by`.
- Retire an objection, or edit or delete a node you did not write. Retiring is the author's decision.
- Put manuscript or source text in `text` beyond one line.
- Work on more than one gap.
