---
id: 0058-generated-ci-workflow-hardened
title: The generated go-getter workflow follows the project's CI-hardening rules
status: active
date: 2026-10-24
tags: [ci, workflows, go-getter]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  ci-workflow:
    permissions: per-job
    concurrency:
      group: "go-getter-checks-${{ github.ref }}"
      cancel-in-progress: true
---

## Decision

`go-getter apply` generates `.github/workflows/go-getter-checks.yml` with `contents: read` on each job instead of at the top level, and with a concurrency group that cancels superseded runs. The action pins stay go-getter's own SHA pins.

## Why

Every other workflow in this repository is held to per-job permissions and a concurrency group by `tests/test_ci_hardening.py`. go-getter 0.3.6 (issue 227, PR 228) made both configurable, so the generated file no longer needs a test exemption (T45). Overriding the action pins was rejected: it would downgrade checkout to match an older pin list.

## Consequence

The tests keep one narrow allowance for the generated file: its action refs must be SHA-pinned but need not equal the list in `PINNED_ACTIONS`.
