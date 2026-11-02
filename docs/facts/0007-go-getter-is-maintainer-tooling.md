---
id: 0007-go-getter-is-maintainer-tooling
title: go-getter develops the scaffold and scholar-mcp; it is not part of what an article repo ships
status: active
date: 2026-11-02
tags: [go-getter, template, host-neutral]
---

## Fact

go-getter is the maintainer's own plugin. It manages the knowledge base, guardrails and plans of this repository and of `scholar-mcp` (their `.go-getter/` directories, `docs/guardrails/` and generated `AGENTS.md` blocks). The cookiecutter template ships none of it: on 2026-11-02 `grep -rIli go-getter` over `{{cookiecutter.repo_name}}`, `cookiecutter.json` and `hooks/` found nothing, and the template has no `.go-getter/` or `.claude/` directory. It has no `.mcp.json` either; the article repo `articles.bridge_contract_for_agent_session_governance` has a hand-made one.

Article-side tooling therefore cannot assume go-getter plans, routing classes, runner or checkpoints. It may assume a shell, Python, `make`, and, optionally, an agent host and MCP.
