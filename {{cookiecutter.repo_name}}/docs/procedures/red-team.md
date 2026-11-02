# Red team: objections and hypotheses for one gap

Use this when a work order, or the author, names a gap in the theses map. Do one gap, then stop.

You propose. You never accept. Every node you write has `status: proposed`; promoting a node is the author's own command (`theses accept`), which you do not run.

## Inputs you may read

- The output of `python3 -m scripts.article theses gaps`.
- The output of `python3 -m scripts.article theses slice <id> --depth 2` for the one gap you take.
- At most the section lines named by the anchor, found through `paper/build/section-index.json` (write it with `python3 -m scripts.article index`). Read those lines only.
- Source text only through `source-claim` nodes already in the map.

Do not read `paper/article.tex`, whole section files or the bibliography.

## Steps

1. Run `python3 -m scripts.article theses lint`. If it fails, report the diagnostics and stop; do not edit around them.
2. Run `python3 -m scripts.article theses gaps`. Take one gap, preferring `thesis-unsupported`, then `objection-undefended`, then `single-source`, then `anchor-missing`. Note its id.
3. Run `python3 -m scripts.article theses slice <id> --depth 2`.
4. If the node has an anchor, run `python3 -m scripts.article index` if the index is missing or stale (`index --check`), look up the anchor's line range, and read only those lines.
5. Draft the smallest set of nodes that answers the gap:
   - for an unattacked thesis or a weak spot: one to three `objection` nodes;
   - for a thesis with no support: a `hypothesis` node naming what would have to hold, joined by a `supports` edge, or an `objection` saying why none can be found;
   - for a single-sourced claim: an `objection` that the claim rests on one source.
6. Write the nodes and edges into `theses.yaml` by editing the file. Each node needs `id` (lowercase, unique), `type`, a one-line `text`, `status: proposed`, and an `anchor` (an existing `\label`) or `bib_keys`. Edges run from the objection to the thing attacked (`attacks`), or from a hypothesis to the thing it supports (`supports`). Add no field the schema (`schemas/theses.schema.json`) does not list.
7. Run `python3 -m scripts.article theses lint`. Fix your own nodes until it passes.
8. Stop. Report the gap id and the ids you added. Do not take a second gap.

## What a good objection is

- It is the strongest form its best proponent would accept, not a strawman. If you know the source, say so in `text` and add a `source-claim` node for it with a verbatim `quote` and `locator`; if you do not, say in your report that the form is standard, not strongest.
- For a universal or necessary claim, try a concrete counterexample. Put the case in `text`. If none exists, say which search you tried in your report.
- Include at least one objection from a rival tradition (a school or field that would reject the framing) when the target is a thesis.
- Name what is attacked: a premise, the inference, a definition, an empirical claim or the scope.
- Skip an objection an existing defense already answers; report it as a duplicate.
- Say how serious it is (fatal, serious, minor) and why, in your report, not in the map.

## Never

- Set `status` to anything but `proposed`, or write `accepted-by`.
- Retire, edit or delete a node you did not write.
- Put manuscript or source text in `text` beyond one line; the `quote` of a `source-claim` is the only place source wording goes.
- Work on more than one gap.
