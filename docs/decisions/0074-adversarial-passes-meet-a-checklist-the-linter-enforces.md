---
id: 0074-adversarial-passes-meet-a-checklist-the-linter-enforces
title: Red-team and blue-team proposals must meet a checklist, and the linter enforces its form
status: active
date: 2026-11-03
tags: [theses-map, agents, argument]
track: product
accepted-by: Sergey Strebulaev
---

## Decision

An objection or defense proposed under 0066 must meet a fixed checklist. An objection names its target, its `kind` (`counterexample`, `undercut`, `rebuttal`, `scope`, `hidden-premise`, `evidence`) and its `tradition` (`internal`, `rival`, `adjacent`, `none`); a premise target uses `premise-ref: {argument, n}` (0073). An objection marked `form: strongest` cites its source and a one-sentence restatement its proponent would accept as fair; otherwise it is `standard`. A `counterexample` states the case and which premise or definition it breaks. A defense names the objection it `answers`, one `move` from a closed list (`concede-scope`, `distinguish`, `deny-premise`, `accept-cost`, `cite-evidence`, `reformulate`), an `anchor` in the paper, and a `cost` for moves that give something up. New factual claims in a defense need their own `source-claim`; retiring an objection stays a human act.

`theses lint` enforces the form: missing source, restatement, case, target, answers, anchor, cost or evidence reference is an error or a gap; an unanswered `fatal` objection is listed first; duplicate objections warn. Content (fairness of a restatement, whether a counterexample bites, whether a defense is adequate) is left to tier 2 as advice or to the reviewer.

Choices: an agent may propose `severity` (`fatal`, `serious`, `minor`) and a human confirms it. The gap "an accepted thesis has no rival-tradition objection" is opt-in per thesis. A `weak` objection is reported once and not stored, so `form` is `strongest` or `standard`.

## Why

Without a standard, red-team output is vague or strawman and blue-team output restates the thesis. The linter cannot make an objection strong, only costly to fake: a proposal that passes arrives with a source, a restatement and a target, so the reviewer judges substance, not completeness. Default-on rival gaps were rejected because not every thesis has a real rival school. Storing weak objections was rejected because it grows the review queue without adding objections worth answering.

## Consequence

The schema gains the optional objection and defense fields, and the red-team and blue-team skills carry the checklist. Severity grading by an agent can be wrong or uniform; a pass that marks everything `minor` or everything `fatal` is a signal to recheck.
