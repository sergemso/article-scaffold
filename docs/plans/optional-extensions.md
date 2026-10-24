# Optional extensions (ported from the archived T-queue)

Repo: `/home/ubuntu/projects/sergemso/article-scaffold` (a cookiecutter template). These are the six tasks left open when the T01–T45 queue was archived at `docs/plans/archive/t-queue/` (T38, T39, T40, T41, T43, T44). All are optional; none was started. Original cards: `docs/plans/archive/t-queue/tasks.json`. Background: `docs/improvement-plan.md` (section 5 and ADR-004). The T-queue's `touch` lists are carried over as the Scope line of each step; stay inside them.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

Preconditions the T-queue tasks depended on (T02, T14, T24, T27, T33) are all done. Run Python from the venv created by `make setup`; system python has no pytest.

## 1. Authoring extensions

### 1.1 Journal class adapters — [!]
Class: implement · Effort: medium · Needs: none · Check: `python3 -m pytest tests/test_journals.py -q`
Human: blocked by decision #6 (no journal classes now); do not start without a new decision recorded in `docs/decisions/`.
Context: Submission targets have different class files and front matter; guessing is worse than an explicit adapter. See `docs/improvement-plan.md#5-scientificstructural-extensions-v22-510-days-optional`. Scope: `cookiecutter.json`, `{{cookiecutter.repo_name}}/paper/preamble/**`, `tests/test_journals.py`.
Do: Add optional journal choices (elsarticle, acmart, IEEEtran) without making any the default. Vendor classes/templates only where licenses allow; otherwise document installation. Add a submission checklist per journal. Test the render matrix; skip PDF builds when the class is unavailable.
Done-when: Every adapter renders and documents its requirements; the default perspective output is unchanged.

### 1.2 Reviewer mode and response letters — [ ]‖
Class: implement · Effort: medium · Needs: none · Check: `python3 -m pytest tests/test_review_mode.py -q`
Context: Revision workflows are common and easy to standardize. Read `{{cookiecutter.repo_name}}/paper/article.tex`. Scope: that file, `{{cookiecutter.repo_name}}/templates/**`, `tests/test_review_mode.py`.
Do: Add a `review_mode` choice that enables line numbers, anonymization and a changed-text marker. Add response-letter and cover-letter templates with generated metadata. Ensure anonymous mode removes authors, acknowledgements and identifying links. Test both modes for leaked identity fields.
Done-when: Anonymous mode leaks no identity; review mode builds and is documented.

### 1.3 REUSE/SPDX compliance — [ ]‖
Class: implement · Effort: medium · Needs: none · Check: `python3 -m pytest tests/test_reuse.py -q`
Context: Per-file licensing is needed if the template is shared publicly. Keep in sync with the license selection work (T14, done). Scope: `LICENSES/**`, `REUSE.toml`, `{{cookiecutter.repo_name}}/LICENSES/**`, `tests/test_reuse.py`.
Do: Add SPDX headers or a `REUSE.toml` mapping for template files, scripts and paper content. Vendor license texts under `LICENSES/`. Add an opt-in reuse lint target; do not gate the default build on the reuse tool. Test that every tracked file is covered by a mapping or header.
Done-when: Every tracked file has a license mapping; reuse lint passes when the tool is installed.

### 1.4 Devcontainer — [ ]‖
Class: implement · Effort: medium · Needs: none · Check: `python3 -m pytest tests/test_devcontainer.py -q`
Context: A pinned environment removes the "works on my machine" TeX/Pandoc problem. Needs network only to look up image digests. Scope: `.devcontainer/**`, `Dockerfile`, `docs/devcontainer.md`, `tests/test_devcontainer.py`.
Do: Create a devcontainer with TeX Live, pandoc, Python 3.10+, git and the dev extras. Pin image digests and document the build; do not make it required for local builds. Add VS Code tasks for `make pdf`/`validate`/`test`. Add a static test for the config; the real docker build stays opt-in.
Done-when: The devcontainer config is valid and documented; normal builds do not depend on Docker.

## 2. MCP adapter

### 2.1 Read-only MCP adapter — [ ]
Class: implement · Effort: medium · Needs: none · Check: `python3 -m pytest tests/test_mcp_readonly.py -q`
Context: Agents can consume the CLI contract without making MCP part of the build. See `docs/improvement-plan.md#adr-004--mcp-is-optional-separate-and-gated`. Needs network to install the MCP SDK. Scope: `mcp/**`, `docs/mcp.md`, `tests/test_mcp_readonly.py`.
Do: Create a separate optional package under `mcp/` that imports the core or shells out to the CLI `--json`; never the inverse. Expose read-only tools/resources: validate, status, metadata plan, diagnostics, and repo-limited file reads. Add path allowlisting, output size limits and no secret/env leakage. Test parity between the MCP output and the CLI JSON for the same fixture.
Done-when: MCP is installable as an extra, read-only by default, with byte-parity with CLI JSON.

### 2.2 MCP mutating tools with confirmation — [ ]
Class: implement · Effort: medium · Needs: 2.1 · Check: `python3 -m pytest tests/test_mcp_mutations.py -q`
Context: Write operations are useful but dangerous; they need an explicit plan/confirm protocol. The release plan/apply work (T33) is done. Per the archived decisions, `migrate` is not an MCP mutation. Scope: `mcp/**`, `tests/test_mcp_mutations.py`.
Do: Add plan/confirm tokens for metadata writes and release apply; tokens expire and are single-use. Refuse writes outside the repo, enforce timeouts, and append an audit log. Never expose network or shell passthrough. Test refusal paths: stale token, path escape, missing confirmation.
Done-when: Every mutation requires a fresh confirmation and is confined to the repo.
