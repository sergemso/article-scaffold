# Decisions index (CSV)

id,title,tags,status
0001-instruction-file-cap,"The always-loaded instruction file is capped at 150 lines","practice-packs, harness, cost",active
0002-procedure-delivery,"Detailed procedures live in skills loaded on demand","practice-packs, harness, cost",active
0003-noisy-work-placement,"Noisy work is delegated only when the cost model says the handoff is cheaper","practice-packs, harness, cost",active
0004-cache-hygiene,"No mid-task model, effort or instruction-file change; switches are confirmed","practice-packs, harness, cost",active
0005-compaction-timing,"Context is compacted at task boundaries","practice-packs, harness, cost",active
0006-watcher-noise,"Watchers are quiet","practice-packs, harness, cost",active
0007-routing-classes,"Routing distinguishes explore, plan, implement, review and debug","practice-packs, model-routing, cost",active
0008-routing-start-tiers,"Classes start at balanced tiers and the lowest effort they allow","practice-packs, model-routing, cost",active
0009-routing-max-escalations,"A failed step escalates at most 2 times, then a human decides","practice-packs, model-routing, cost",active
0010-routing-spend-cap,"Headless runs are capped at 1 USD where the host has a cap","practice-packs, model-routing, cost",active
0011-routing-cache-ttl,"The prompt cache lives one hour in the main session and five minutes in subagents","practice-packs, model-routing, cost",active
0012-internal-data-routing,"Internal data goes only to approved cloud providers on paid no-training terms","practice-packs, governance, model-routing",active
0013-confidential-data-routing,"Confidential data may go wherever internal data may","practice-packs, governance, security",active
0014-prompt-logging,"Host prompt logging is disabled on every host","practice-packs, governance, observability",active
0015-gated-actions,"Irreversible commands need a human","practice-packs, hooks, guardrail",active
0016-gated-extra-patterns,"Project-specific commands that also need a human are listed","practice-packs, hooks",active
0017-mcp-no-project-policy,"No project list of MCP servers","practice-packs, hooks",active
0018-checkpoint-before-gated-action,"Work is checkpointed before a gated action","practice-packs, hooks, guardrail",active
0019-checkpoint-trigger-gated-action,"A checkpoint is taken before a gated command","practice-packs, hooks",active
0020-checkpoint-retention,"The 10 newest checkpoints are kept","practice-packs, hooks",active
0021-agent-roster,"Work is delegated to implementer and reviewer agents","practice-packs, agent-roles, harness",active
0022-reviewer-access,"The reviewer reports findings and changes nothing","practice-packs, agent-roles, harness",active
0023-parallel-isolation,"Each parallel task runs in its own git worktree","practice-packs, agent-roles, harness",active
0024-worktree-location,"Task worktrees live in the gitignored .worktrees directory","practice-packs, agent-roles, harness",active
0025-max-concurrent-agents,"At most 1 agents run at once","practice-packs, agent-roles, harness",active
0026-human-escalation,"Agents hand over to a human only when blocked","practice-packs, agent-roles, harness",active
0027-handoff-contract,"Handoffs are a brief in, then a result and evidence out","practice-packs, agent-roles, harness",active
0028-restricted-paths,"Restricted data lives at a declared list of paths","practice-packs, governance, security",active
0029-restricted-path-modes,"Restricted paths have an access mode, deny unless listed","practice-packs, governance, security",active
0030-restricted-paths-enforcement,"Restricted paths are blocked in the host and never committed","practice-packs, governance, enforcement",active
0031-use-commands,"The commands approved to receive a use path are listed","practice-packs, governance, security",active
0032-sink-sources,"The sources allowed to fill a sink path are listed","practice-packs, governance, security",active
0033-restricted-data-hosts,"Restricted data is handled only on hosts with a blocking pre-tool hook","practice-packs, governance, security",active
0034-secret-scan,"Secrets in added lines are scanned before a commit and a push","practice-packs, governance, security",active
0035-scan-allow-paths,"The secret scan skips a declared list of paths","practice-packs, governance, security",active
0036-pii-masking,"Personal data in tool output is masked with per-session pseudonyms","practice-packs, governance, security",active
0037-pii-extra,"The locale-bound types masked in tool output are listed","practice-packs, governance, security",active
0038-mcp-arguments-scanned,"MCP call arguments are scanned for secrets","practice-packs, hooks",active
0039-telemetry-recording,"Steps are not recorded","practice-packs, observability, harness",active
0040-telemetry-export,"Telemetry is not exported","practice-packs, observability, harness",active
0041-verification-checks,"Implement and debug steps pass the project's detected check commands","practice-packs, verification, harness",active
0042-verification-test-command,"The verification test command is ""make test""","practice-packs, verification, harness",active
0043-verification-lint-command,"The verification lint command is ""make lint""","practice-packs, verification, harness",active
0044-verification-typecheck-command,"The verification typecheck command is """"","practice-packs, verification, harness",active
0045-verification-format-command,"The verification format command is ""ruff format --check .""","practice-packs, verification, harness",active
0046-verification-static-analysis-command,"The verification static-analysis command is """"","practice-packs, verification, harness",active
0047-verification-build-command,"The verification build command is ""python -m build""","practice-packs, verification, harness",active
0048-verification-unit-command,"The verification unit command is """"","practice-packs, verification, harness",active
0049-verification-integration-command,"The verification integration command is """"","practice-packs, verification, harness",active
0050-verification-e2e-command,"The verification e2e command is """"","practice-packs, verification, harness",active
0051-verification-coverage-command,"The verification coverage command is """"","practice-packs, verification, harness",active
0052-verification-coverage-bar,"Coverage must meet what the coverage command enforces","practice-packs, verification, harness",active
0053-verification-machine-profile,"Cheap checks run locally, slow checks only in CI (thin machine profile)","practice-packs, verification, harness, ci",active
0054-verification-review-bar,"Review steps pass a reviewer-agent verdict","practice-packs, verification, harness",active
0055-verification-gate,"""Done"" is blocked while the verification checks fail","practice-packs, verification, harness",active
0056-workflow-branch-from-cookiecutter,"Generated workflows filter pushes on the branch chosen at generation time","ci, workflows, template",active
0057-scholar-mcp-separate-repo-per-role,"Scholarly MCP servers live in a separate repository, one server per role","mcp, architecture, scope",active
0058-generated-ci-workflow-hardened,"The generated go-getter workflow follows the project's CI-hardening rules","ci, workflows, go-getter",active
