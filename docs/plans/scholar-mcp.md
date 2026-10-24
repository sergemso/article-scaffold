# scholar-mcp: MCP helper servers for authors, editors and reviewers

This plan is self-sufficient for a cold session. It builds a new repository, `scholar-mcp` (MIT), at `/home/ubuntu/projects/sergemso/scholar-mcp` (sibling of `/home/ubuntu/projects/sergemso/article-scaffold`, the cookiecutter template that owns this plan). It ships three separately installable servers on a shared library; **only the authors server is in scope here**. The editors and reviewers servers are separate later plans, started only after step 5.1 passes.

Decisions already made (this template's own record is `docs/decisions/0057-scholar-mcp-separate-repo-per-role.md`; the design records moved to `scholar-mcp/docs/` in step 1.2 as decisions 0056 to 0061 and facts 0001 and 0002):

- One server per role on a shared library `scholar_core`; packages `scholar_core`, `scholar_authors` (later `scholar_editors`, `scholar_reviewers`). Official MCP Python SDK, stdio transport only, no listener, pinned dependencies with hashes.
- **The model never writes bibliographic fields.** Tools take identifiers (DOI, arXiv id, PMID, ORCID; ISBN see step 2.5) and the server copies every field verbatim from the registry record, keeping source, retrieval time and a hash. Unfetchable means not added.
- The registry of record is authoritative (Crossref or DataCite via doi.org content negotiation, arXiv API, NCBI for PMIDs, ORCID public API). OpenAlex and publisher pages are cross-checks only. A disagreement blocks the entry for a human; the server never votes among sources. An unverifiable reference is stored `unverified` and blocks validation, release and deposit until the author supplies a resolving identifier or records an attestation (who, when, why).
- Only identifiers and typed bibliographic search strings leave the machine, over HTTPS to an allowlist of registry hosts. Search returns candidates only; a human picks one.
- Writes, candidate picks and attestations are confirmed out of band: the tool returns a plan id and content hash, the human runs `scholar-authors confirm <id>` in a terminal, which shows the exact content. Tokens are single-use, expire and are hash-bound. Zenodo publish is a tool behind that same confirm (the owner chose this over a human-only command); it defaults to the Zenodo sandbox.
- First release scope for the authors server, all four groups: (a) repo operations, a read-only wrap of the generated repo's own CLI; (b) reference and metadata verification; (c) submission documents (cover letter, response letter); (d) release and deposit.
- Assurance bar: a written threat model, and a golden corpus with a zero-tolerance gate (see 4.1 and 4.2). Fuzzing, signed releases and an independent review were not required for the first release.

How a generated article repo is driven: its own entry point is `python3 -m scripts.article <subcommand> [--json]` (see `{{cookiecutter.repo_name}}/Makefile` and `{{cookiecutter.repo_name}}/scripts/article/cli.py` in the template). The authors server shells out to that, never imports repo code, so it works across template versions. The template's `release` subcommand takes `--apply --yes`; the server must never forward `--yes` from a model; it passes it only after its own confirmation.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked. Python is 3.10+; the template repo's suite takes about two minutes, so run single test files while iterating. Nothing in the template repo's `docs/plans/archive/` or `docs/plans/optional-extensions.md` should be changed by this plan except as step 1.2 states.

## 1. Create the repository and move the design records

### 1.1 Create and bootstrap the repository — [x]
Class: implement · Effort: medium · Needs: none · Check: `test -f /home/ubuntu/projects/sergemso/scholar-mcp/LICENSE && git -C /home/ubuntu/projects/sergemso/scholar-mcp log --oneline | head -1 && test -d /home/ubuntu/projects/sergemso/scholar-mcp/docs/decisions`
Human: creating the GitHub remote (`github.com/sergemso/scholar-mcp`) and pushing is outward-facing; do it only with the owner's explicit go-ahead. A local repository is enough to continue.
Context: Sibling repositories live under `/home/ubuntu/projects/sergemso/`. The new repo must be governed by go-getter like this one (see `AGENTS.md` and `.go-getter/` here for the shape). Run the plugin's setup skill `go-getter:go-getter-init` (interactive; it records choices as decisions and guardrails) and give it the same answers as this repository unless the owner says otherwise.
Do: `git init` the directory on branch `master`. Add an MIT `LICENSE`, `README.md` (one paragraph: purpose, the four design rules above, "authors server first"), `.gitignore`, and a `pyproject.toml` with a `src/` layout and three packages `scholar_core`, `scholar_authors` (empty `__init__.py` for now), `requires-python >= 3.10`, a `dev` extra with pytest and ruff, and console script `scholar-authors = scholar_authors.cli:main`. Add `Makefile` targets `setup`, `test`, `lint`. Run the go-getter setup. Commit.
Done-when: the repository exists with a license, a first commit, `docs/{facts,decisions,guardrails,skills}/` created by the go-getter setup, and `make test` runs (even with zero tests).

### 1.2 Move the seed design records into the new repository — [x]
Class: implement · Effort: low · Needs: 1.1 · Check: `ls /home/ubuntu/projects/sergemso/scholar-mcp/docs/decisions/0061-assurance-bar-threat-model-and-golden-corpus.md /home/ubuntu/projects/sergemso/scholar-mcp/docs/guardrails/egress-allowlist.md && test ! -d /home/ubuntu/projects/sergemso/article-scaffold/docs/plans/scholar-mcp-seed`
Context: The records are staged in `docs/plans/scholar-mcp-seed/{decisions,facts,guardrails}/` in this (template) repo: decisions `0001`..`0006`, facts `0001`..`0002`, guardrails `bib-fields-from-records-only`, `egress-allowlist`, `publish-requires-out-of-band-confirm`, `no-unverified-reference-in-release`. They are already numbered for the new repo. If step 1.1's setup created decisions of its own, renumber the seed records after them and update every `0001`-style cross-reference and `governed-by`/`grounded-in`/`governed-facts` id.
Do: Copy the files into the matching `docs/` directories of the new repo, adjusting ids if renumbered. Add one row per artifact to each `INDEX.md` there (CSV: `id,title,tags,status`; quote cells with commas). Commit in the new repo. In this template repo, delete `docs/plans/scholar-mcp-seed/` and commit (`docs(plans): move the scholar-mcp design records to the new repository`).
Done-when: all 12 records exist in the new repo with working cross-references and index rows, and the seed folder is gone from this repo.

### 1.3 Write the threat model — [x]
Class: plan · Effort: high · Needs: 1.2 · Check: `test -s /home/ubuntu/projects/sergemso/scholar-mcp/docs/threat-model.md`
Context: Decision 0061 requires a written threat model, each abuse case mapped to a control and a test. Assets: unpublished manuscript text, the Zenodo API token, the bibliography's integrity, the permanent DOI. Trust boundaries: model/host, server process, the human's terminal, the generated repo's filesystem and CLI, each registry host.
Do: Write `docs/threat-model.md` with a table of abuse cases, each with a control and a named test file under `tests/`. It must cover at least: prompt injection through manuscript text and through fetched record fields (tool output is data, never instructions; fenced and length-capped); the model supplying bibliographic fields; path traversal and symlink escape from the repo root; SSRF and off-list redirects via lookups; manuscript text in an outbound request; secret leakage in logs, tool output or arguments; token replay, expiry and hash substitution on confirm; a model passing `--yes` through to the repo CLI; Zenodo publish to production by accident; a registry returning a wrong or changed record; dependency compromise; log injection. Mark which controls land in which step.
Done-when: every abuse case above has a control, a test file name and an owning step number, and the document is committed.

### 1.4 CI skeleton with pinned, hashed dependencies — [x]‖
Class: implement · Effort: medium · Needs: 1.1 · Check: `make -C /home/ubuntu/projects/sergemso/scholar-mcp lint test`
Context: Decision 0061 baseline: pinned dependencies with hashes, official MCP Python SDK. The template repo's workflows (`{{cookiecutter.repo_name}}/.github/workflows/`) show the house style: actions pinned to commit shas, minimal `permissions`. Network is needed once to resolve and hash the dependencies.
Do: Add `requirements.lock` (with hashes) generated by pip-compile or uv, and install from it in `make setup`. Add `.github/workflows/ci.yml` (lint, tests, `pip-audit`) with pinned actions and `permissions: contents: read`. Create `tests/guardrails/` with a placeholder test per guardrail from step 1.2 that `pytest.skip`s with the owning step number, so each guardrail's `run:` command already resolves. The guardrail `run:` commands say `python -m pytest`, but a bare `python` is not on PATH on this machine (only `python3`) and pytest lives in `.venv`: change them to `make test`-style commands or `.venv/bin/python -m pytest` and re-run `go-getter apply`.
Done-when: `make lint test` passes, the workflow parses, and every guardrail's `run:` command exists and exits 0 (skipped tests count).

## 2. The shared library `scholar_core`

### 2.1 Path guard and audit log — [ ]
Class: implement · Effort: medium · Needs: 1.3 · Check: `python -m pytest tests/core/test_pathguard.py tests/core/test_audit.py -q`
Context: Threat model rows for path escape, symlinks and log injection (step 1.3). Code goes in `src/scholar_core/`.
Do: `pathguard.py`: resolve every path with `Path.resolve(strict=False)`, require it to be inside one configured repo root, reject symlinks that leave it, null bytes and absolute-path tricks. `audit.py`: append-only JSON Lines, one record per tool call and per confirm (time, tool, argument hash, outcome), with control characters escaped, secrets never written, and a hash chain so deletion or edit is detectable.
Done-when: tests cover traversal, symlink escape, Windows-style separators, null bytes, and a tampered audit chain being detected.

### 2.2 Confirmation tokens and the `confirm` CLI — [ ]‖
Class: implement · Effort: high · Needs: 1.3 · Check: `python -m pytest tests/core/test_confirm.py tests/guardrails/test_confirmation.py -q`
Context: Decision 0060. The confirm path must be something the model cannot drive: a terminal command the human runs, not a tool.
Do: `confirm.py`: `create(plan) -> (plan_id, content_hash)` stores the plan under a per-user state dir with mode 0600; a token is single-use, expires (default 15 minutes), and is bound to the content hash. `confirm_cli`: shows the exact diff or record and asks y/N on a real TTY (refuse without a TTY and refuse `--yes`). Consuming the token marks it spent before the action runs. Replace the placeholder guardrail test with real tests.
Done-when: tests cover stale token, wrong hash, replay, missing TTY, concurrent double-confirm, tampered plan file, and the token never appearing in any tool result.

### 2.3 Egress client with host allowlist — [ ]‖
Class: implement · Effort: medium · Needs: 1.3 · Check: `python -m pytest tests/core/test_egress.py tests/guardrails/test_egress.py -q`
Context: Decision 0059. Hosts needed: `doi.org`, `api.crossref.org`, `api.datacite.org`, `export.arxiv.org`, `eutils.ncbi.nlm.nih.gov`, `pub.orcid.org`, `api.openalex.org` (cross-check only), `sandbox.zenodo.org` and `zenodo.org` (deposit only).
Do: `egress.py`: one HTTPS client (httpx or urllib) with the allowlist in code, redirects followed manually and refused if they leave the list, timeouts, response size cap, request payload cap (identifiers and short search strings only), polite User-Agent with a contact address, per-host rate limiting and retry with backoff. No other module may open a socket.
Done-when: tests cover non-allowlisted host, plain HTTP, redirect to an off-list host, oversize response, oversize payload, and rate-limit/backoff behavior with recorded responses.

### 2.4 Registry clients and the record store — [ ]
Class: implement · Effort: high · Needs: 2.3 · Check: `python -m pytest tests/core/test_registries.py tests/core/test_recordstore.py -q`
Context: Decisions 0057 and 0058 and fact 0001. A record is what the registry returned, kept byte-for-byte alongside a parsed form.
Do: Clients for Crossref and DataCite (via `doi.org` content negotiation to find the registration agency), arXiv, NCBI PMID and ORCID. `recordstore.py` stores, per identifier, the raw response, the parsed record, source, retrieval time and SHA-256, in a content-addressed directory inside the repo (`.scholar/records/`) so provenance is reviewable in git. Normalize identifiers deterministically (DOI case, `https://doi.org/` prefixes) without altering record content. Search returns candidate records only.
Done-when: tests replay recorded responses for each registry offline, and a changed live record is detected by hash comparison.

### 2.5 ISBN and books — [!]
Class: plan · Effort: medium · Needs: 2.4 · Check: `ls /home/ubuntu/projects/sergemso/scholar-mcp/docs/decisions/*isbn*.md && python -m pytest tests/core/test_isbn.py -q`
Human: decision needed. Decision 0058 lists the registries of record for DOI, arXiv, PMID and ORCID but names none for ISBN, and open ISBN sources (Open Library and similar) are crowd-sourced and not authoritative. Choose: (a) ISBN is candidate-only, so a book stays `unverified` until a human attests, or (b) name a source as authoritative with a cross-check. Record the answer as a new decision in the new repository whose file name contains `isbn`, then unblock.
Context: Without this decision a book can never be marked verified by the server.
Do: Write the decision, then implement the chosen behavior in `scholar_core` with golden-corpus entries for books.
Done-when: a decision on ISBN exists and a book citation behaves as that decision says, with tests.

### 2.6 Verification engine and attestations — [ ]
Class: implement · Effort: high · Needs: 2.2, 2.4 · Check: `python -m pytest tests/core/test_verify.py tests/guardrails/test_records_only.py tests/guardrails/test_release_gate.py -q`
Context: Decisions 0057 and 0058. Cross-check fields: title, authors, venue, year, DOI. Attestations live in the repository so they show up in review.
Do: `verify.py`: for each bibliography entry, compare it with its stored record and the cross-check records and return one of `verified`, `unverified`, `disagrees` with the exact differing fields. A BibTeX formatter turns a record into an entry deterministically (no model text, stable key, braces and diacritics handled), and verification fails if an entry differs from the formatter's output for its stored record. Attestations are a file (`.scholar/attestations.yaml`) whose entries require who, when and why; creating one is a confirmed write (2.2). Replace the placeholder guardrail tests.
Done-when: tests cover a verified entry, a hand-edited entry, an unresolvable DOI, a cross-check disagreement, an attestation missing a field, and byte-for-byte formatter output on the corpus.

## 3. The authors server

### 3.1 Server skeleton, tool registry and output hygiene — [ ]
Class: implement · Effort: medium · Needs: 2.1, 2.2 · Check: `python -m pytest tests/authors/test_server.py -q`
Context: Official MCP Python SDK, stdio only. Prompt injection through manuscript text or fetched fields is a threat-model row (step 1.3).
Do: `scholar_authors/server.py` registers tools from one table with typed argument schemas that reject unknown fields and any bibliographic-value field. All tool results are structured JSON with a size cap; free text from the repo or a registry is returned in a clearly marked data field and never concatenated into instructions. Every call is audit-logged (2.1). The `scholar-authors` CLI has two commands: `serve` and `confirm`. No environment variable or secret appears in any result.
Done-when: a protocol-level test lists tools over stdio, rejects an unknown argument and an over-long argument, and checks that a manuscript containing instruction-like text comes back only inside the data field.

### 3.2 Repo operation tools (read-only) — [ ]‖
Class: implement · Effort: medium · Needs: 3.1 · Check: `python -m pytest tests/authors/test_repo_tools.py -q`
Context: The generated repo's CLI is `python3 -m scripts.article <subcommand> --json`. Build a fixture repo by rendering the template: `cookiecutter /home/ubuntu/projects/sergemso/article-scaffold --no-input -o <tmp>`.
Do: Tools `validate`, `status`, `metadata_plan` (the CLI's `metadata --check`), `wordcount`, `figures` and `build` (build writes only under the repo's `build/`). Run the CLI as a subprocess with a fixed argument vector, a timeout, a scrubbed environment and the repo root as the working directory (path guard, 2.1). Return the CLI's JSON unchanged apart from size capping. Never forward `--yes`.
Done-when: parity test: tool output equals the CLI's `--json` output for the same fixture repo; a path outside the repo root is refused.

### 3.3 Reference tools — [ ]
Class: implement · Effort: high · Needs: 2.6, 3.1 · Check: `python -m pytest tests/authors/test_reference_tools.py -q`
Context: Decisions 0057, 0058 and 0059. The bibliography is the repo's `paper/refs.bib` (see the template's `paper/` directory).
Do: Tools `search_candidates` (search string in, candidate records out, nothing written), `plan_add_reference` (identifier in; the plan holds the exact entry the formatter will write and the record's provenance), `verify_bibliography` (2.6 over the whole file, structured result), `plan_attestation`. Writes happen only after `scholar-authors confirm`. A candidate is chosen by the human in the confirm CLI, not by a tool argument.
Done-when: tests show that no tool schema accepts a title, author, venue, year or DOI as a value, an add without confirm changes nothing, a candidate cannot be picked by the model, and an entry written after confirm equals the formatter's output.

### 3.4 Submission document tools — [ ]‖
Class: implement · Effort: medium · Needs: 3.1 · Check: `python -m pytest tests/authors/test_documents.py -q`
Context: Cover letters and response-to-reviewers letters are generated from the repo's `metadata.yaml`. The template's own optional plan step 1.2 in `docs/plans/optional-extensions.md` (reviewer mode and response letters) overlaps in intent: coordinate so the templates exist once.
Do: Tool `plan_cover_letter` and `plan_response_letter` render a Jinja template from `metadata.yaml` fields and author-supplied prose blocks, show the exact output in the plan, and write under `submission/` only after confirm. Bibliographic data in a letter, if any, comes from stored records, never from tool arguments.
Done-when: tests cover rendering from metadata, no write without confirm, and a path outside `submission/` being refused.

### 3.5 Release and deposit tools — [ ]
Class: implement · Effort: high · Needs: 3.2, 3.3 · Check: `python -m pytest tests/authors/test_release_tools.py tests/guardrails/test_confirmation.py -q`
Context: Decision 0060 and fact 0002 (publish mints a permanent DOI). The repo's `release` subcommand supports `--dry-run` and `--apply --yes`. The Zenodo token comes from the OS keyring (via `keyring`) or the `ZENODO_TOKEN` environment variable, never a tool argument or a log field.
Do: `plan_release` runs the repo's dry run and refuses while any reference is unverified or unattested (guardrail `no-unverified-reference-in-release`). `apply_release` runs the repo's `--apply --yes` only after confirm. `create_deposit_draft` creates a Zenodo draft on the sandbox by default. `publish_deposit` publishes only after confirm with the exact metadata and target (sandbox or production) shown; production needs a separately confirmed setting. Zenodo calls go through the egress client (2.3).
Done-when: tests against a fake Zenodo cover the refusal on an unverified reference, publish without confirm, a stale or replayed token, sandbox as the default, and the token absent from every result and log.

## 4. Correctness and security gates

### 4.1 Golden corpus and replay harness — [ ]
Class: implement · Effort: high · Needs: 2.6 · Check: `python -m pytest tests/corpus -q`
Context: Decision 0061. Record real registry responses once (network needed), commit them under `tests/corpus/records/`, and replay offline in CI.
Do: Build the corpus with real records for: diacritics and non-Latin names; corporate authors; very long author lists; retracted and corrected papers; preprint and published versions of one work; DOI case and URL variants; DataCite datasets; known wrong-metadata cases (a record whose registries disagree); books (per 2.5). For each, commit the expected entry. A harness replays them and asserts every written field equals the source record, and every mismatch is flagged. Add a nightly workflow `corpus-live.yml` that refetches live and fails on drift, with the diff in the log.
Done-when: `tests/corpus` passes offline, a deliberately altered field makes it fail, and the nightly workflow parses.

### 4.2 Threat-model coverage review — [ ]
Class: review · Effort: high · Needs: 3.2, 3.3, 3.4, 3.5, 4.1 · Check: `python -m pytest -q`
Context: Step 1.3's table names a control and a test for every abuse case.
Do: Check each row of `docs/threat-model.md` against the code and the named test file; run the full suite and the lint; run `pip-audit`. Try three live abuse attempts through a real stdio session: a manuscript with an injected instruction, a path traversal argument, a `--yes` smuggled into an argument. Record the results in the threat model. Do not fix findings in this step; open a plan step for each.
Done-when: every row maps to a passing test, the three live attempts were refused, and the full suite passes.

## 5. First release

### 5.1 End-to-end run and 0.1.0 — [ ]
Class: review · Effort: medium · Needs: 4.2 · Check: `python -m pytest -q`
Human: tagging and publishing `0.1.0` (and the GitHub remote, if not yet created) needs the owner's explicit go-ahead.
Context: Use a repository generated from the template with the owner's defaults (`~/.cookiecutterrc`).
Do: Generate an article repo, then through a real MCP client session: run `validate` and `status`, add three references (one DOI, one arXiv, one found by search), confirm each in the terminal, run `verify_bibliography`, add one unresolvable reference and show that release refuses, attest it, plan a release, create a sandbox Zenodo draft and confirm. Do not publish to production. Write the transcript to `docs/e2e-0.1.0.md`, update the README with install and the host's MCP config snippet, set the version to `0.1.0`, and prepare (do not push) a tag.
Done-when: the transcript shows every step above behaving as the decisions say, the suite passes, and the tag is prepared locally.
