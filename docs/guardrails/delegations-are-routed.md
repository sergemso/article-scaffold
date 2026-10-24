---
id: delegations-are-routed
title: Delegations to a role are routed by expected total step cost
status: active
date: 2026-10-24
tags: [practice-packs, model-routing, guardrail]
governed-by: 0008-routing-start-tiers
grounded-in: [0008-routing-start-tiers]
derivation-note: Given routing picks the cheapest eligible tier by expected total step cost (0016), a delegation that bypasses the router can pick an ineligible or needlessly costly model, so the host must route it where it can.
go-getter:
  enforcement:
    - tier: 1
      check: Where no hook routes the delegation, run `go-getter route --class <class> --host <host id>` and delegate with the `delegateModel` it returns
    - tier: 2
      check: Pre-delegation hook sets the delegated model from the router, or denies when no model is eligible
      run: builtin:route-delegation
  generated-by: cost-routing@0.2.0
  pack-answer: tiers
  pack-option: balanced
---

## Guardrail

A delegation to a role uses the model `go-getter route` returns for its class, passed as its `delegateModel` (the value the host's delegation tool accepts): the host hook sets it where the host allows, otherwise ask the router before delegating. After the maximum number of escalations a step goes to a human.
