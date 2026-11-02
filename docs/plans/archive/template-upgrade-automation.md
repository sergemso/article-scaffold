# Automate the generated-repo upgrade

Repo: `/home/ubuntu/projects/sergemso/article-scaffold` (a cookiecutter template). Today `docs/upgrading.md` describes a manual three-way merge: build a config from `template.json`, render OLD and NEW, diff, `git apply --3way`, resolve conflicts, `make metadata && make validate`, bump the stamp. This plan automates every step except resolving conflicts, as an `article upgrade` command that follows the same plan/apply shape as `article release`. Step 2.1 is the follow-up: a scheduled workflow that runs the plan and opens a PR.

Design constraints, all from existing decisions: a generated repo stays dependency-free at runtime (`cookiecutter` is needed only while upgrading and is imported lazily, with an install hint when missing); nothing merges silently; v1 to v2 stays manual (`docs/migrating-to-v2.md`); `template.json` keeps its cruft-compatible layout. Code lives in `{{cookiecutter.repo_name}}/scripts/article/` (new `upgrade.py`, wired in `cli.py`); tests live in `tests/`. Run Python from the venv created by `make setup`; system python has no pytest. The template's own test suite takes about two minutes, so run single files while iterating.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

## 1. The `article upgrade` command

### 1.1 Read the stamp and plan the upgrade — [x]
Class: implement · Effort: medium · Needs: none · Check: `python3 -m pytest tests/test_upgrade_plan.py -q`
Context: `{{cookiecutter.repo_name}}/template.json` is written by `hooks/post_gen_project.py`; `template_commit` is `null` for a non-git source and `template` is a path or URL. Read `tests/test_upgrade.py` for how the stamp is tested and `tests/conftest.py` for the `render` helper. Model the plan output on `scripts/article/release.py` (plan returns a JSON-serializable dict; apply consumes it).
Do: Add `scripts/article/upgrade.py` with `plan(repo, new_ref=None)`. It reads `template.json`, resolves OLD (`template_commit`) and NEW (`new_ref`, default the template's default branch head via `git ls-remote` or `git rev-parse` for a local path), and returns a dict with `template`, `old`, `new`, `up_to_date` and a list of refusals. Refuse, with a stable error code each: missing or malformed `template.json`, `template_commit` null, dirty working tree, OLD equal to NEW (report `up_to_date`, not an error), a repo whose `metadata.yaml` is still v1 (point at `docs/migrating-to-v2.md`). Do not import `cookiecutter` here.
Done-when: each refusal and the happy path are covered by a test using a throwaway git-backed template fixture; the plan does no writes.

### 1.2 Render OLD and NEW and compute the patch — [x]
Class: implement · Effort: medium · Needs: 1.1 · Check: `python3 -m pytest tests/test_upgrade_render.py -q`
Context: The doc's step 2 and 3 use `cookiecutter --checkout` with a config built from `context.cookiecutter` and `git diff --no-index`, then `git apply --3way -p3`. The `-p3` depends on temp-dir depth and is fragile.
Do: In `upgrade.py`, add `build_patch(plan, workdir)`. Import `cookiecutter` lazily and call its Python API with `checkout=`, `no_input=True`, `extra_context` from the stamp, into two temp dirs under `workdir`. Produce the patch with `git diff --no-index --binary` and rewrite the `a/` and `b/` prefixes so paths are repo-relative (no `-p` guessing). Exclude `.git`, `__pycache__` and `template.json`. Return the patch path and the list of changed files. Reuse `tests/test_upgrade.py::_files` ideas for comparing trees.
Done-when: against a fixture template with two commits, the patch touches exactly the files that differ between the two renders, and a missing `cookiecutter` yields the install hint instead of a traceback.

### 1.3 Apply on a branch and hand over conflicts — [x]
Class: implement · Effort: medium · Needs: 1.2 · Check: `python3 -m pytest tests/test_upgrade_apply.py -q`
Context: The doc's steps 3 to 6. Conflicts are expected where the author edited lines the template also changed. `make metadata` and `make validate` are the repo's own checks.
Do: Add `apply(repo, plan)` and `finish(repo)`. `apply` creates branch `upgrade/<new-short-sha>`, runs `git apply --3way`, and stops after reporting `applied`, `conflicted` (file list) and `skipped`. It never resolves a conflict and never commits. `finish` refuses while conflict markers or unmerged paths remain, then runs `make metadata` and `make validate`, bumps `template_version` and `template_commit` in `template.json` and leaves the result staged for the author to commit. If `apply` fails halfway, leave the branch and working tree as they are and print how to abandon (`git checkout - && git branch -D …`); do not run those commands.
Done-when: tests cover a clean apply, a conflicting apply (author edited a line the template changed), `finish` refusing on markers, `finish` succeeding after they are resolved, and the stamp unchanged until `finish` succeeds.

### 1.4 Wire the CLI, JSON contract and docs — [x]
Class: implement · Effort: medium · Needs: 1.3 · Check: `python3 -m pytest tests/test_cli.py tests/test_upgrade_cli.py tests/test_docs.py -q`
Context: `scripts/article/cli.py` registers subcommands (see `release`); the CLI is JSON-first with fixed exit codes, and JSON outputs have schemas in `{{cookiecutter.repo_name}}/schemas/` (`status.schema.json`, `diagnostics.schema.json`; see `tests/test_status.py` for how one is checked). The Makefile delegates to the CLI.
Do: Add `article upgrade` with `--plan` (default, writes nothing), `--apply`, `--finish`, `--to <ref>` and `--json`. Use the same exit-code scheme as `release` and add a `schemas/upgrade.schema.json` for the plan/apply output and test against it the way `tests/test_status.py` does. Add a `make upgrade` target that runs `--plan`. Rewrite `docs/upgrading.md` so the command is the recommended path and the manual merge is the fallback; keep the v1 to v2 note and the "never skip reviewing conflicts" warning.
Done-when: `--plan --json` output validates against the schema; the existing CLI tests still pass; `docs/upgrading.md` describes the command and still describes the manual fallback.

### 1.5 End-to-end check and full suite — [x]
Class: review · Effort: low · Needs: 1.4 · Check: `make test`
Context: Only the fixture template has been used so far.
Do: Generate a repo from this template at one commit, make a local edit to `paper/` and `metadata.yaml`, advance the template by one commit that changes a script and a workflow, then run `plan`, `apply` and `finish` and confirm the edits survive and the scripts update. Run `make test`, then `git diff` and confirm only intended files changed.
Done-when: `make test` exits 0 and the end-to-end run is recorded in the commit message of the closing commit.

## 2. Follow-up: scheduled upgrade PRs

### 2.1 Add a scheduled workflow that opens an upgrade PR — [x]
Class: implement · Effort: medium · Needs: 1.5 · Check: `python3 -m pytest tests/test_ci_hardening.py tests/test_upgrade_workflow.py -q`
Context: The workflows in `{{cookiecutter.repo_name}}/.github/workflows/` are hardened and tested by `tests/test_ci_hardening.py` (pinned actions, minimal `permissions`). `__DEFAULT_BRANCH__` is substituted by the post-gen hook; use the same mechanism if the workflow needs the branch name. A scheduled run can only fetch the template if `template` in `template.json` is a public HTTPS URL.
Do: Add `upgrade.yml` with a weekly `schedule` and `workflow_dispatch`. It runs `article upgrade --plan --json`; if there is something to apply it runs `--apply` on a branch, pushes it and opens a PR whose body lists applied, conflicted and skipped files from the JSON. When conflicts exist it still opens the PR as a draft with the conflicted files listed, and never runs `--finish`. Permissions: `contents: write` and `pull-requests: write` only, scoped to the job. Skip with a notice when `template` is not an HTTPS URL or `template_commit` is null. Pin every action to a commit sha like the other workflows.
Done-when: the workflow parses, passes the CI-hardening tests, is covered by a static test of its triggers, permissions and skip conditions, and the real run is documented as opt-in in `docs/upgrading.md`.
