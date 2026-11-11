---
id: 0083-dialectic-stage-maps-contradictions-and-typed-moves
title: A dialectic stage maps contradictions and typed moves before the thesis is fixed
status: active
date: 2026-11-11
tags: [theses-map, lifecycle, dialectic, triz]
track: product
accepted-by: Sergey Strebulaev
---

## Decision

The lifecycle (0070) gains an advisory stage `dialectic` between `frame` and `map`. The theses map gains two optional sections.

`contradictions`: id, two `poles` (each anchored to a `source-claim` or a niche statement), `kind` (`dialectical`, `technical`, `physical`), `status`, `author`. A TRIZ contradiction may add `improving` and `worsening` (free-text parameters), `principle` (optional tag from a shipped closed list of the 40 inventive principles), `ideal-result` and `resources`. No parameter or principle matrix lookup in the first version.

`moves`: typed steps over contradictions, with a closed `type` list: `negation`, `negation-of-negation`, `synthesis`, `aufhebung`, `new-beginning`. `aufhebung` is first-class and must record `preserved`, `cancelled` and `lifted`. A `synthesis` or `aufhebung` cites at least two contradictions or moves; a `negation-of-negation` cites a prior `negation`; a `new-beginning` names the thesis or question node it opens. A `development` view (the chain of moves in order) is derived by `theses`, not stored.

`theses lint` checks structure only: references resolve, poles are anchored, move types carry their required fields, no cycles in the move chain. `theses gaps` adds kinds `contradiction-unmoved`, `move-without-opening` and `thesis-untraced` (a thesis with no `new-beginning` or recorded reason). The gate of the stage passes when there are no such gaps and a human has attested the stage (`flow attest`); soundness of a synthesis is judged by a person. A procedure in `docs/procedures/` and a `dialectic` skill adapter have an agent run niche and topic analysis over sources already in `paper/sources/` and propose contradictions and moves as `proposed` nodes.

## Why

A thesis chosen before the niche's tensions are mapped tends to restate one pole. Keeping the moves as typed nodes lets objections and arguments (0073, 0074) target them and lets `theses gaps` show what is still unresolved. Making the stage advisory and opt-in keeps existing article repos passing. Free-text TRIZ parameters were chosen over the full matrix because the matrix is large and mostly useful in technical domains; a tagged principle can be added later without a schema break. `aufhebung` as a mere tag on `synthesis` was rejected: the three required fields are the point of the concept and only a first-class type can be linted.

## Consequence

Schema, linter, gap kinds, the shipped principle list, one procedure, one skill adapter and an upgrade/adoption note are needed. A repo that never declares a contradiction sees no change. Whether a synthesis is philosophically sound stays a human judgment.
