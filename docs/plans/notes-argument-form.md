# Argument form in the theses map: premise-conclusion nodes and what a check can do

Status: proposal for the owner to accept as a decision. It extends decision 0065 (nodes and edges) and feeds step 2.1 (schema) and steps 3.2 to 3.4 (procedures). No code changes.

## Problem

Decision 0065 holds an argument as nodes joined by `supports`, `attacks` and `rebuts` edges. An edge says "this bears on that" but not how. A reader cannot tell whether several supporting nodes are independent reasons or jointly needed premises, nor which step is an inference and which is an assumption left unsaid. Reviewers attack exactly those gaps (the hidden premise, the weak inference), so the map should make them explicit and give the linter something to hold on to.

## Proposal: an `argument` node type

Add one node type, `argument`, beside `thesis`, `hypothesis`, `objection`, `defense`, `source-claim`. An argument is a small structured unit tied to one conclusion:

```yaml
- id: arg-key-exhaustion-not-q
  type: argument
  status: proposed            # proposed | accepted | retired (as other nodes)
  anchor: sec:key-exhaustion  # LaTeX \label, as other nodes
  conclusion: thesis-key-exhaustion-separate   # id of a thesis/hypothesis node
  inference: modus-tollens    # closed list below
  premises:
    - n: 1
      text: Rule Q is for storage corruption or log tampering, where the cause is not the client.
      ref: src-contract-rule-q          # optional id of a source-claim node
    - n: 2
      text: Key exhaustion is a deliberate act of an authorised party.
    - n: 3
      text: A deliberate authorised act is not storage corruption or tampering.
      kind: implicit                    # explicit | implicit (hidden premise made visible)
      status: proposed                  # implicit premises need author acceptance
    - n: 4
      text: Rule Q has no recovery path inside the contract; key exhaustion has one.
      role: supports-conclusion         # extra reason, not needed for validity
  steps:                                # optional, only for chains
    - from: [1, 2, 3]
      to: c1
      rule: modus-tollens
```

Fields:

- `conclusion`: one node id. The conclusion keeps its own node, so objections and defenses attach to it with existing edges.
- `premises`: numbered, one line each. `kind: implicit` marks a hidden premise that the author or an agent has written out; `ref` links a premise to a `source-claim` node, which is how claim checks (decision 0067) reach premises. `role` separates premises the conclusion needs (`required`, the default) from extra reasons (`supports-conclusion`), so linked and convergent support are not conflated.
- `inference`: a closed list: `deduction`, `modus-ponens`, `modus-tollens`, `disjunctive-syllogism`, `induction`, `abduction`, `analogy`, `authority`. The first four are checkable in form; the rest are labels that tell the reader and the red-team skill which attack applies (counterexample for induction, disanalogy for analogy, a rival explanation for abduction).
- `steps`: only for chains where an intermediate conclusion (`c1`) feeds a later argument. Most arguments need none.
- No new edge kinds. An argument node `supports` its conclusion; an `objection` may `attacks` the argument (its inference), a numbered premise (`target: arg-id#3`) or the conclusion. Telling the three targets apart is the point: undermining a premise, undercutting the inference and rebutting the conclusion need different defenses.

## Deterministic checks

Structural lint (no solver, always on, part of `theses lint`):

1. Every argument has an existing conclusion, at least one premise, and a known `inference`.
2. Premise numbers are unique and consecutive; every `steps.from` number exists.
3. `ref` points to a `source-claim` node.
4. A `deduction`, `modus-ponens` or `modus-tollens` argument with a single premise is flagged (a hidden premise is likely).
5. An implicit premise still `proposed` blocks the argument being `accepted` (decision 0066: agents propose, humans promote).
6. An accepted argument whose conclusion or required premise is retired is flagged.

Optional formal check (a named flow check, off by default): the author supplies a formula for each premise in an optional `formal:` field using a tiny syntax (`A`, `not A`, `A -> B`, `A and B`, `A or B`). A SAT solver answers whether the premises together with the negated conclusion are satisfiable. Unsatisfiable means the form is valid; satisfiable yields a countermodel, reported as the missing premise to add. A second query tests whether the premises are jointly consistent.

## Worked example

Source: the key-lifecycle design note in the article repo, decision K-D2, "Why NOT rule Q". The prose argues that exhaustion of all keys should be a side predicate, not rule Q. Formal fields would be:

- P1 `Q -> corruption_or_tamper` (rule Q applies only where storage or log is the cause)
- P2 `exhausted -> deliberate_authorised`
- P3 `deliberate_authorised -> not corruption_or_tamper` (the hidden premise)
- Conclusion `exhausted -> not Q`

Without P3 the solver finds a countermodel (exhaustion with Q and corruption both true; nothing in P1 or P2 forbids it) and the tool reports "add a premise linking deliberate acts to non-corruption". With P3 the form is valid. The prose note never states P3; a reviewer reading "conflating the two is a semantic error" would probe exactly there. P4 (recovery path) is a `supports-conclusion` premise: not needed for validity and ignored by the solver, but visible to the red-team skill as a separate, attackable reason.

## Limits, in plain terms

- A validity check says the conclusion follows if the premises are true. It says nothing about whether they are true. Truth of premises is source checking (claim checks) or human judgment.
- Translating prose into formulas is itself an interpretive act. A wrong or too coarse formalisation gives a false "valid". The `formal:` text is author-written or agent-proposed and human-accepted, never silently derived.
- Propositional encoding cannot see quantifiers, modality, probability or degrees. Arguments from induction, analogy, abduction and authority are not checkable by it; only their structure is linted. Predicate or modal encodings cost more than they return for most papers; defer them.
- A consistency check finds contradictions among stated premises only, not against the rest of the paper or the literature.
- Validity can be bought cheaply by adding a premise that already contains the conclusion. The lint cannot see that; the red-team skill should look for question-begging premises, and the human accepts implicit premises one by one.
- Most of an article's argument will be informal. The value is not proof but making premises, inference kind and hidden premises visible and attackable, at a token cost small enough to read in slices.

## Open choices for the owner

1. Is `argument` a node type or a field block on `thesis`? A node type keeps slicing by id simple and lets objections target an argument; a field block keeps the file shorter.
2. Is the formal check worth a solver dependency in the vendored CLI? Proposed: not in the first version; keep it a documented extension and a named flow check supplied by the article repo.
3. Confirm or trim the closed `inference` list.
