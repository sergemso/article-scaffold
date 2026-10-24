# Draft upstream issue: generated workflow cannot satisfy CI-hardening rules

Filed: https://github.com/vivantel/go-getter/issues/227 (go-getter 0.3.5, `ciWorkflow()` in `compiler/src/apply.mjs`).

## Summary

`go-getter apply` writes `.github/workflows/go-getter-checks.yml` and marks it
"do not edit". The workflow cannot be adjusted, so projects that enforce
common CI-hardening rules on all workflows fail on a file they cannot change.

## Observed

A test that checks every workflow fails on the generated file:

- permissions are set once at the top level (`contents: read`), never per job;
- there is no `concurrency` group;
- `actions/checkout` is pinned to a fixed SHA (v7.0.1) and `actions/setup-node`
  is used; neither can be overridden to match the project's own pins.

## Expected

`ciWorkflow()` accepts options, or reads project config, for:

1. per-job `permissions` (for example `permissions: per-job`);
2. an optional `concurrency` block (`group`, `cancel-in-progress`);
3. overriding the `CHECKOUT` and `SETUP_NODE` action refs;
4. a stable marker (already present: the header comment) documented as the way
   for linters and tests to recognise generated workflows.

## Why it matters

The file is hash-tracked in `manifest.json`, so local edits are overwritten or
reported as drift. Projects are left with a test exemption as the only option.

## Workaround in use

Exempt `go-getter-checks.yml` in the project's workflow tests (plan task T45).
It will be removed when this is resolved.
