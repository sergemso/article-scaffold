---
id: 0057-scholar-mcp-separate-repo-per-role
title: Scholarly MCP servers live in a separate repository, one server per role
status: active
date: 2026-10-24
tags: [mcp, architecture, scope]
track: process
accepted-by: Sergey Strebulaev
---

## Decision

The MCP helper for researchers, authors and editors is built in a new repository, `scholar-mcp` (MIT), not in this template. It ships one server per role (authors, editors, reviewers) on top of a shared library for the security-critical code: path guard, audit log, confirmation tokens, output limits and the reference pipeline. The authors server is built first; the editors and reviewers servers follow once the shared library has been proven by it.

This narrows ADR-004 (`docs/improvement-plan.md`): this template ships at most a thin, optional adapter over a generated repo's own `--json` CLI, and nothing editorial. Steps 2.1 and 2.2 of `docs/plans/optional-extensions.md` are moved to the build plan, `docs/plans/scholar-mcp.md` in the `scholar-mcp` repository.

## Why

An editorial workflow server handles other people's unpublished work and reviewer identities, calls third-party registries and can mint a permanent DOI. That is a different product, threat model and release cycle from a cookiecutter template whose value is a self-contained repo with no runtime dependencies. Separate servers per role were chosen over launch-time profiles for hard isolation by process and install: an author's agent session cannot reach a tool that reads reviewer identities, because that tool is not installed.

## Consequence

Three packaging surfaces instead of one, and a shared library that must stay stable. The design records for the new repository live in its `docs/` (decisions 0056 to 0061, facts 0001 and 0002).
