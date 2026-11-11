---
id: 0073-arguments-are-nodes-with-numbered-premises
title: An argument is a node type with numbered premises, a closed inference label and structural lint
status: active
date: 2026-11-03
tags: [theses-map, argument]
track: product
accepted-by: Sergei Strebulaev
---

## Decision

The theses map (0065) gains one node type, `argument`, tied to one conclusion node. It holds numbered premises (each marked `explicit` or `implicit`, `required` or `supports-conclusion`, with an optional `ref` to a `source-claim`), an `inference` label from a closed list (`deduction`, `modus-ponens`, `modus-tollens`, `disjunctive-syllogism`, `induction`, `abduction`, `analogy`, `authority`) and optional `steps` for chains. No new edge kinds: an argument `supports` its conclusion. An objection reaches a premise through a `premise-ref: {argument, n}` field, so undermining a premise, undercutting the inference and rebutting the conclusion stay distinct.

`theses lint` checks structure only: conclusion, premises and inference exist; premise numbers are unique and consecutive; `ref` resolves to a `source-claim`; a deductive argument with one premise is flagged; an implicit premise still `proposed` blocks the argument being `accepted` (0066); an accepted argument over a retired conclusion or required premise is flagged. The optional SAT validity check is not in the first version; if built, it is a documented extension and a named flow check supplied by the article repo.

## Why

An edge says "this bears on that" but not how, and reviewers attack exactly the hidden premise and the weak inference. A node type keeps slicing by id simple and lets objections target an argument. A field block on `thesis` was rejected: it shortens the file but objections could not target an argument or its premises. A solver in the vendored CLI was rejected for now: validity says nothing about whether premises are true, formalising prose is itself interpretive, and most of an article's argument is informal.

## Consequence

The schema, the linter and the red-team and blue-team skills need extending, and article repos with an existing map need an upgrade path that leaves their map alone. Truth of premises stays with claim checks (0067) and human judgment.
