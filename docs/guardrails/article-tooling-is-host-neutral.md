---
id: article-tooling-is-host-neutral
title: Nothing the template ships names go-getter or requires one agent host
status: draft
date: 2026-11-02
tags: [template, host-neutral, guardrail]
governed-by: 0071-flow-orders-are-host-neutral
grounded-in: [0071-flow-orders-are-host-neutral, 0007-go-getter-is-maintainer-tooling]
derivation-note: Given go-getter is maintainer tooling (fact 0007) and orders are meant for any host (0071), a shipped file that names go-getter or one host's directory as a requirement breaks both.
go-getter:
  enforcement:
    - tier: 1
      check: A test over the rendered template that fails on the string go-getter, on model names, and on any host-specific path outside a named adapter directory.
---

## Guardrail

Files under `{{cookiecutter.repo_name}}` do not mention go-getter and name no model. A host-specific file (for example a Claude Code skill or an AGENTS.md pointer) exists only as a thin adapter in a clearly named adapter location and contains no logic. Draft until the scan test exists.
