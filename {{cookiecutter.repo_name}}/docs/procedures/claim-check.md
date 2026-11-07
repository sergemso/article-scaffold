# Claim check (tier 2): does the excerpt support the claim?

Use this after the quote check, for `source-claim` nodes whose quote was found in the local source text. A small, cheap model is enough: you judge one short excerpt against one sentence, which is the only step in the flow that asks a model for judgment about a source.

## What you may read

- The output of `python3 -m scripts.article claims quote-check --all`: verdicts and locators, no text.
- For one node at a time, the output of `python3 -m scripts.article claims excerpt <id>` and the node's one-line `text` (the paper's claim wording) from `theses.yaml`.

Nothing else. Do not open the source file, the section, or any other part of the paper. Do not send the excerpt or the claim anywhere; judge it yourself in this session.

## Steps

1. Run `python3 -m scripts.article claims quote-check --all`.
2. List the nodes with verdict `not-found` or `no-local-text`, and those marked `stale` (their source address names a superseded edition; `claims rebase <id>` proposes a new address for the author, you do not apply it). Do not judge them: a quote that is not in the text, or a source with no local text, cannot be checked here. Report them for the author.
3. For each node with verdict `found` and `cached` empty (a recorded verdict is fresh only while the claim wording and the excerpt are unchanged), do:
   1. Run `python3 -m scripts.article claims excerpt <id>`.
   2. Compare the excerpt with the claim wording and answer with exactly one of:
      - `supports`: the excerpt says what the claim says, no more;
      - `overstates`: the claim is stronger, broader or more certain than the excerpt;
      - `contradicts`: the excerpt says the opposite or rules the claim out.
   3. Record it: `python3 -m scripts.article claims record <id> --set <verdict>`. The verdict is stored in the committed ledger (`docs/ledger/claim-verdict/`), keyed by a hash of the claim wording, the excerpt and the procedure version; it holds the verdict and the hashes, never text. A different verdict for the same inputs is refused; to re-judge, a person runs the `ledger evict` command that the error names. (`claims cache <id> --set <verdict>` still works as the same command.)
4. Skip nodes whose `cached` verdict is present; the ledger already holds an answer for exactly these inputs.
5. Report, as ids with one line each: every `overstates` and `contradicts`, then every `not-found` and `no-local-text`. The author decides what to change.

## Judging

- Judge only the words in front of you. If the excerpt is too short to decide, choose `overstates` and say what is missing; do not guess at the rest of the source.
- Quantifiers, hedges, scope and modality count: "may" versus "does", "some" versus "all", "in this case" versus "in general".
- A claim that adds a causal or normative step the excerpt does not contain is `overstates`.

## Never

- Read outside the excerpt, or fetch the source from anywhere.
- Edit `theses.yaml`, the paper or the source texts.
- Record `supports` for a node you did not judge.
- Replace the author's attestation. A human reading the source (tier 3) is recorded by the author, not by you; leave `theses accept` and any attestation to them.
