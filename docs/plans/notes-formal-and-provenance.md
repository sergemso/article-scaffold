# Formal checks as flow checks, and an AI-use provenance log

Status: proposal for the owner to accept as a decision. It extends fact 0009 (stages, gates, check names) and decisions 0070 to 0072, and feeds steps 8.2 to 8.4 (flow schema, emitters, `flow done`). No code changes.

## Part 1. Formal checks become named flow checks

### What exists

The first adopter runs a model checker through `scripts/run-tlc-docker.sh LOGDIR [mutants]`: it copies the formal spec directory to a temp dir, downloads the checker jar, records an `environment.txt` (image digest, jar URL and sha256, cpu count, date), runs a syntax pass and one checker run per configuration, writes one log and one time file per configuration, and appends a line to `failures.txt` for any non-zero exit. A mutation pass is optional. Logs are kept under `docs/logs/`. The script needs docker and network on first run, so it is not a cheap gate.

### Constraint from fact 0009 and decision 0070

A gate must be a cheap deterministic predicate with no network and no model call. Running the checker is neither cheap nor offline. So the flow must separate two things:

- **Running** the checker: a gated, human-or-CI action that produces a log directory.
- **Reading** the result: a cheap predicate over the log directory that the gate evaluates.

### Proposal: declare formal checks in `flow.yaml`

Fixed check names stay fixed (guardrail `flow-checks-are-named-not-supplied`). A repo does not supply a command line; it declares a named formal check that selects from a closed template, and the template reads logs.

```yaml
formal:
  - name: formal-tlc                   # check name, must start with formal-
    kind: log-verdict                  # closed list: log-verdict
    log_dir: docs/logs/p6-tlc          # repo-relative, inside docs/logs
    inputs:                            # files the run depends on, hashed
      - paper/supplementary/formal-spec/BridgeContract.tla
      - paper/supplementary/formal-spec/*.cfg
    required_logs: [sany.log, BridgeContract.log, environment.txt]
    pass_when:
      absent: [failures.txt]           # file must not exist, or be empty
      no_line_matching: ["Error:", "Invariant .* is violated", "Deadlock reached"]
      some_line_matching: ["Model checking completed. No error has been found"]
    run_hint: scripts/run-tlc-docker.sh docs/logs/p6-tlc   # shown to the human, never executed by flow
```

Behaviour:

- `formal-tlc` is a name in the check table. `flow done` for a `formal-check` order runs the log-verdict reader (pure file reading) and reports `pass`, `fail` or `stale`.
- **Stale** means the recorded input hash (written by the human or CI when the run finished, in `environment.txt` or a sidecar) no longer matches the current hash of `inputs`. A changed spec makes the check stale without a state change, in the same way edits make earlier gates fail again (fact 0009, re-entry).
- If `log_dir` or a required log is missing, the check reports `unavailable`, never `pass`.
- The run itself is an order kind `run-formal` (gated, tier script) whose `needs_human` text shows `run_hint`. The flow never executes it: the script pulls an image and downloads a jar, which violates the no-network rule for gates and is an irreversible-looking external action for a host with approval hooks.
- Where a repo declares no `formal` entries, the stage's `formal-check` order is not emitted (fact 0009 already says "only where a repo declares one").
- Mutation passes are a second declared check (`formal-tlc-mutants`) with its own log; its pass rule can require the mutants log to report every mutant killed, as a regex the author supplies in the declaration.

### Limits

- A log-verdict check trusts the log. It cannot show the run was honest or that the model matches the prose. The environment file with the image digest and jar hash is what makes the run auditable; the check requires it present.
- Regexes on tool output are brittle across tool versions. The `pass_when` rules live in the repo's declaration so a tool change is a small edit, and the flow reports which rule failed.
- Whether the formal model corresponds to the paper's claims is human judgment and is not claimed by this check.

## Part 2. AI-use provenance log

### What the AI-use statement says today

The backmatter states, in prose, which tasks used AI (language correction, formatting, code generation, text and citation review), that supplementary code was written with assistance, how the bibliography was verified by the human, one limitation noted in the sources manifest, which tasks AI was not used for, and that the human author retains responsibility. All of that is written by hand and can drift from what actually happened.

### Proposal: `docs/provenance/ai-use.jsonl`

An append-only log, one JSON object per event, written by the `flow` tooling when an order is closed and by `theses accept`. It records who did what with which tier, never the content.

```json
{
  "ts": "2026-11-02T10:15:00Z",
  "order": "stage+kind+hash",
  "stage": "adversarial",
  "kind": "red-team",
  "tier": "small",
  "tool_class": "agent",
  "nodes": ["thesis-key-exhaustion-separate"],
  "outputs": ["theses.yaml"],
  "outcome": "proposed",
  "accepted_by": null,
  "accepted_at": null,
  "check": "theses-lint",
  "check_result": "pass"
}
```

Fields:

- `tool_class`: `script`, `agent` (model-assisted), or `human`. This is deliberately coarse. The log does not name a vendor, model or host: article repos are host-neutral and a model name is not a stable fact about the work.
- `tier`: `script`, `small`, `large`, as in decision 0072.
- `outcome`: `proposed`, `accepted`, `rejected`, `waived`, `failed`.
- `accepted_by`, `accepted_at`: filled by the human acceptance event (a separate line, `outcome: accepted`, referencing the same `order`). Agent-authored nodes remain `proposed` until such a line exists (guardrail `agent-nodes-need-human-promotion`).
- `outputs` are paths, `nodes` are ids. Both are names, not text.

The log is committed with the repo (it is the evidence) and is excluded from the companion like the map (guardrail `theses-map-never-reaches-companion`), since it lists internal node ids.

### Deriving the AI-use statement

A script `provenance report` reads the log and prints a draft paragraph for the human to edit; it never writes the backmatter itself. It groups events by `kind` and `tool_class` and reports, in plain words:

- which kinds of work agents performed (for example "objections were proposed with AI assistance and reviewed by the author");
- which outputs agents touched, by area (map, sections, code, bibliography) from `outputs` paths;
- that every agent-authored node in the final map was accepted by a named human, and how many were rejected, taken from the log (counts here are derived output for the author, not prose committed to the paper; the author decides the wording);
- what AI was not used for, as the absence of any `agent` event of that kind, so a sentence like "AI was not employed for literature synthesis" can be checked against the log rather than asserted.

The report flags mismatches between the current statement and the log (a task done by an agent but absent from the prose, or claimed absent but present in the log). The human decides what to publish.

The log covers only work done through the flow. Work done outside it (an editor assistant, a pasted conversation) is not captured; the report says so, and the statement must still ask the author about that.

### What the log must never contain

- Manuscript text, in any amount: no quotes, no excerpts, no section content, no diff hunks, no claim wording.
- Source text or quotes from sources, and any text from reviews.
- Prompts, model responses or reasoning, or file contents.
- Secrets, tokens, keys, credentials, personal data, or absolute local paths (paths are repo-relative).
- Model names, host names or vendor identifiers (host neutrality).
- Counts or enumerations written into the repo's prose (the report derives them on demand).

The writer enforces this structurally: the log writer accepts only the fields above, with `nodes` matching the id pattern and `outputs` matching a repo-relative path pattern; free-text fields do not exist. A lint (`provenance lint`) rejects any line with an unknown key or a value over a short length bound.

## Open choices for the owner

- Whether the log lives under `docs/provenance/` (committed, excluded from the companion) or is kept outside the repo. Committed gives an audit trail at the price of a file that grows; the proposal is committed.
- Whether `formal` declarations belong in `flow.yaml` or in the map file. The proposal keeps them in `flow.yaml` because they are about the lifecycle, not the argument.
- Whether `human` events (a person editing without tooling) should be loggable by a `provenance note` command, or stay outside the log.
