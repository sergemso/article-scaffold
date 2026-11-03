# Adversarial standards: what red-team and blue-team passes must produce

Status: proposal for the owner to accept as a decision. It extends decision 0066 (agents are gap-driven and propose-only) and feeds step 2.1 (schema), step 2.2 (linter) and steps 3.2 and 3.3 (red-team and blue-team skills). No code changes.

## Problem

Decision 0066 says agents propose objections and defenses but does not say what makes one worth proposing. Without a standard, a red-team pass yields vague or weak objections that are easy to answer, and a blue-team pass yields replies that restate the thesis. A checklist makes the output reviewable and lets the linter reject obviously empty proposals.

Evidence of what real objections look like is in `A/docs/notes/` (the competitor and predecessor list pairs each rival with its strong side, its weakness and a response) and in the article repo's review-response plans. The checklist below generalises that shape: strong side before weakness, response tied to a place in the paper.

## Node fields these standards need

Objections and defenses are existing node types (decision 0065). Add optional fields:

```yaml
- id: obj-example
  type: objection
  status: proposed
  author: agent            # agent | human; agent nodes need human promotion (guardrail agent-nodes-need-human-promotion)
  target: thesis-x         # node attacked
  form: strongest          # strongest | standard | weak (see below)
  strongest-form:
    source: src-rival-1    # a source-claim id or bib key; required when form is strongest
    restated: One-sentence version the rival would accept as fair.
  tradition: rival         # internal | rival | adjacent | none; which school or field it comes from
  kind: counterexample     # counterexample | undercut | rebuttal | scope | hidden-premise | evidence
  counterexample:          # only for kind: counterexample
    case: A concrete case, in one or two sentences.
    why-it-bites: Which premise or definition it breaks.
  premise-ref: {argument: arg-x, n: 3}   # optional, when the node targets a premise of an argument node
- id: def-example
  type: defense
  answers: obj-example
  move: distinguish        # concede-scope | distinguish | deny-premise | accept-cost | cite-evidence | reformulate
  anchor: sec:limitations  # where the paper carries this reply
  cost: What the paper gives up by this reply, in one line (required for accept-cost and concede-scope).
```

## Red-team checklist: what a pass must produce

A pass targets one thesis or argument (a slice, never the paper). For each target the pass proposes objections meeting these items.

1. **Strongest form.** State the objection as its best proponent would, not as a strawman. An objection marked `form: strongest` must cite its source (`strongest-form.source`) and a one-sentence restatement the proponent would accept as fair. If no source exists the form is `standard`, or `weak`, and the agent says so.
2. **Counterexample.** For every universal or necessary claim in the target, try at least one concrete counterexample (a case in which the premises hold and the conclusion fails). If none is found, say which search was tried; absence is a finding, not silence.
3. **Rival traditions.** At least one objection per target from a rival tradition (a school, field or community that would reject the framing), marked `tradition: rival`, and one from an adjacent field. A pass that stays inside the paper's own school is incomplete.
4. **Attack surface named.** Say which part is attacked: a premise (give `premise-ref`), the inference, a definition (give the term id), an empirical claim (give the source-claim), or the scope.
5. **Hidden premises.** List premises the argument needs but does not state (for argument nodes, these become `implicit` premises proposed for author acceptance, as in the argument-form note).
6. **Not already answered.** Check the existing defenses against the objection; an objection already covered by an accepted defense is reported as a duplicate, not proposed anew.
7. **Severity.** One of `fatal`, `serious`, `minor`, with one line why. A pass that marks every objection `minor` or every one `fatal` is a signal to recheck.
8. **No manuscript quoting beyond the slice.** The pass uses the slice it was given and the sources in the map.

## Blue-team checklist: what a defense must show

1. **Answers a specific objection** (`answers`), not the thesis in general.
2. **Chooses a move** from the closed list and does what it says: `deny-premise` names the premise and gives a reason; `distinguish` names the difference that matters; `concede-scope` states the narrower claim; `accept-cost` states the cost; `cite-evidence` points to a source-claim node, not a bare bib key; `reformulate` gives the new wording.
3. **Addresses the strongest form**, not a weaker version. A defense of an objection marked `strongest` that argues against a different formulation is rejected by review.
4. **Has an anchor**: the label of the paper's section that carries the reply. A defense with no anchor is an intention, not a defense, and appears as a gap.
5. **States its cost** for moves that give something up.
6. **Does not introduce new unsupported claims.** Any new factual claim in a defense needs its own `source-claim` node or is flagged as a new gap.
7. **Does not retire the objection.** Retirement is a human decision.
8. **Consistency.** The defense must not contradict an accepted thesis or another defense (checked by the argument-form consistency check where the nodes are arguments, otherwise by review).

## Which items the linter can enforce

Lintable (tier 0, deterministic, offline):

- `form: strongest` without `strongest-form.source` or `restated`: error.
- `strongest-form.source` that does not resolve to a source-claim node or bib key: error.
- `kind: counterexample` without `counterexample.case` and `why-it-bites`: error.
- Objection with no `target`, or `target` unknown: error.
- Defense with no `answers`, unknown objection, or no `anchor` resolving in the section index: gap.
- `move: accept-cost` or `concede-scope` without `cost`: error.
- `move: cite-evidence` without a resolving source-claim reference: error.
- A thesis in `accepted` status with no objection of `tradition: rival` linked to it: gap (advisory unless the author turns it on).
- An objection with `severity: fatal` and no answering defense: gap, listed first.
- Agent-authored node with status `accepted`: error (guardrail already planned).
- Duplicate objection: two objections on the same target with identical `kind` and `premise-ref`: warning.

Partly lintable (script can check shape, a model or a person judges content):

- Defense `distinguish` names a difference: the script checks the field is non-empty; whether it is a real difference is for tier 2 or review.
- Objection cites a rival tradition: the script checks `tradition`; whether the source belongs to that tradition is for review.
- Counterexample "bites": a tier-2 check can ask whether the case satisfies the premises and fails the conclusion; its answer is advice.

Not lintable (human judgment):

- Whether a restated objection is fair to its proponent.
- Whether a counterexample is a genuine case or a contrivance.
- Whether the severity grading is right and whether a defense is adequate.
- Whether the set of rival traditions is complete.

## Limits

The linter can make the form of an objection costly to fake (it must cite something) but cannot make its content strong. A red-team agent can fill every field with plausible words. The standards therefore constrain what a human is asked to review: a proposal that passes the lint arrives with a source, a restatement and a target, so the reviewer judges substance, not completeness.

## Open choices for the owner

- Whether `severity` is author-set only, or may be proposed by the agent and confirmed.
- Whether the rival-tradition gap is on by default or opt-in per thesis.
- Whether `form: weak` objections are stored at all, or reported once and dropped.
