---
id: 0056-workflow-branch-from-cookiecutter
title: Generated workflows filter pushes on the branch chosen at generation time
status: active
date: 2026-10-24
tags: [ci, workflows, template]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

Template workflows keep a `__DEFAULT_BRANCH__` placeholder in `on.push.branches`, because `.github/workflows/*.yml` is copied without rendering. `hooks/post_gen_project.py` replaces it with the literal `cookiecutter.default_branch` value (`main` or `master`). No `${{ }}` expression appears in any `on:` filter.

## Why

Actions does not evaluate expressions in `on:` (fact 0001), so the previous dynamic filter never matched. Substituting the already-existing `default_branch` choice is the smallest working change. Rendering the workflows themselves was rejected: it needs `{% raw %}` around every Actions expression and is error-prone.

## Consequence

A repo whose default branch is renamed after generation needs a manual edit of its workflows. Tests assert on rendered output: a literal branch, no leftover placeholder, no `${{` in `on:`.
