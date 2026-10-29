# Guardrails index (CSV)

id,title,tags,status
instruction-file-within-cap,"The instruction file must stay within 150 lines","practice-packs, harness, guardrail",active
procedure-delivery-rule,"Detailed procedures live in skills loaded on demand","practice-packs, harness, guardrail",active
noisy-work-rule,"Noisy work is delegated only when the cost model says the handoff is cheaper","practice-packs, harness, guardrail",active
cache-hygiene-rule,"No mid-task model, effort or instruction-file change; switches are confirmed","practice-packs, harness, guardrail",active
compaction-timing-rule,"Context is compacted at task boundaries","practice-packs, harness, guardrail",active
watches-use-the-wrapper,"Watches start through go-getter watch, --until done for CI runs and long commands","practice-packs, harness, guardrail",active
delegations-are-routed,"Delegations to a role are routed by expected total step cost","practice-packs, model-routing, guardrail",active
prompt-logging-disabled,"Host prompt logging must stay disabled","practice-packs, governance, guardrail",active
gated-actions-need-human-approval,"Irreversible commands need a human","practice-packs, hooks, guardrail",active
checkpoint-before-gated-action,"A gated action is preceded by a checkpoint","practice-packs, hooks, guardrail",active
reviewer-read-only,"The reviewer must not modify files","practice-packs, agent-roles, guardrail",active
parallel-tasks-use-worktrees,"Parallel tasks must each use their own worktree","practice-packs, agent-roles, guardrail",active
worktree-dir-is-gitignored,"The .worktrees directory must be gitignored","practice-packs, agent-roles, guardrail",active
max-concurrent-agents-rule,"No more than 1 agents run at once","practice-packs, agent-roles, guardrail",active
human-escalation-rule,"Agents hand over to a human only when blocked","practice-packs, agent-roles, guardrail",active
handoff-has-brief-result-evidence,"Handoffs must carry a brief, a result and evidence","practice-packs, agent-roles, guardrail",active
restricted-paths-denied,"Agents must not touch restricted paths and none may be committed","practice-packs, governance, guardrail",active
restricted-data-hosts-rule,"Restricted data is handled only on hosts with a blocking pre-tool hook","practice-packs, governance, guardrail",active
no-secrets-in-added-lines,"Added lines must not contain secrets","practice-packs, governance, security, guardrail",active
pii-masked-in-tool-output,"Personal data is masked in tool output","practice-packs, governance, security, guardrail",active
mcp-arguments-hold-no-secret,"MCP calls carry no secret","practice-packs, hooks, guardrail",active
verification-gate-blocks-done,"A step is not done while its verification checks fail","practice-packs, verification, guardrail",active
companion-publishes-allowlist-only,"Nothing outside the allowlist, or matching a deny pattern, reaches the companion","companion, privacy, guardrail",active
companion-release-final-tags-only,"No Release is created on the companion unless the tag is final and matches the version","companion, zenodo, release, guardrail",active
companion-token-least-privilege,"COMPANION_PAT is scoped to companions and GH_PAT never enters an article repo","companion, security, guardrail",active
