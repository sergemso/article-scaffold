---
id: 0001-actions-no-expressions-in-on
title: GitHub Actions does not evaluate expressions in on.push.branches
status: active
date: 2026-10-24
tags: [ci, workflows]
---

## Fact

`${{ ... }}` expressions are not evaluated inside the `on:` section of a workflow, including `on.push.branches`. A filter such as `'${{ github.event.repository.default_branch }}'` is matched as a literal branch name, so the workflow never triggers on push.

## Consequence

A branch filter must be a literal name. In this template the literal comes from `cookiecutter.default_branch` (decision 0056).
