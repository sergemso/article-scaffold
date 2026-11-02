# Fix the default-branch filter in generated workflows

Repo: `/home/ubuntu/projects/sergemso/article-scaffold` (a cookiecutter template). Background: facts/0001 (Actions does not evaluate `${{ }}` in `on:`) and decisions/0056 (substitute `cookiecutter.default_branch` for a `__DEFAULT_BRANCH__` placeholder). The working tree already holds uncommitted work in `hooks/post_gen_project.py`, `tests/test_docs.py`, `.github/workflows/bootstrap-article.yml` and two template workflows, where the placeholder replaces the dead expression. Do not revert it; build on it. The repo is also governed by `AGENTS.md` and `plan/`; this plan is separate from that queue, and any commit should follow the repo's commit conventions.

Legend: `[ ]` pending, `[~]` in progress, `[x]` done, `[!]` blocked.

### 1.1 Substitute the branch name in the post-gen hook — [x]
Class: implement · Needs: none · Check: `python3 -I -c "import ast,sys;ast.parse(open('hooks/post_gen_project.py').read())" && ! grep -n "chr(36)" hooks/post_gen_project.py`
Context: `hooks/post_gen_project.py` function `_replace_default_branch_placeholder` currently replaces `__DEFAULT_BRANCH__` with the string `${{ github.event.repository.default_branch }}` built from `chr()` calls. That is invalid in `on:` (fact 0001). The file is rendered by cookiecutter, so `"{{ cookiecutter.default_branch }}"` is available as a literal, as already used near line 44.
Do: Make the function take the branch name (`"{{ cookiecutter.default_branch }}"`) and replace `__DEFAULT_BRANCH__` with it. Remove the `chr()` construction. Fix the misindented `print`. Narrow `except Exception` to `OSError` (and `UnicodeDecodeError`). Keep the call in `main()` step 4b and update its comment.
Done-when: `hooks/post_gen_project.py` contains no `chr(36)`, no `github.event.repository.default_branch`, and parses; the replacement value is the cookiecutter `default_branch`.

### 1.2 Update branch tests to assert on rendered output — [x]
Class: implement · Needs: 1.1 · Check: `python3 -m pytest tests/test_branch.py tests/test_docs.py -q`
Context: `tests/test_branch.py::test_template_workflows_use_dynamic_default_branch` reads the raw template under a wrong path (`cookiecutter.repo_name`, not `{{cookiecutter.repo_name}}`) and expects the old expression. `tests/test_docs.py::test_template_workflows_use_default_branch` was already switched to render via `tests.conftest.render(tmp_path=...)` with a hand-rolled `tempfile`; it still asserts the expression. Prefer pytest's `tmp_path` fixture over `tempfile`. Run pytest from the venv created by `make setup`; system python has no pytest.
Do: For both tests, render the project (for `main` and `master` via `render(default_branch=...)`) and assert that every workflow's parsed `on.push.branches` equals the chosen literal, that no `__DEFAULT_BRANCH__` remains in any workflow, and that no `${{` appears inside any `on:` block. Update the stale comment about the allowed form at the top of `tests/test_branch.py`.
Done-when: the Check passes and the tests fail if the placeholder or an expression is reintroduced.

### 1.3 Reconcile the cookiecutter version pin — [x]‖
Class: explore · Needs: none · Check: `grep -n "cookiecutter" pyproject.toml .github/workflows/bootstrap-article.yml`
Context: `.github/workflows/bootstrap-article.yml` now pins `cookiecutter==2.7.1` while `pyproject.toml` declares `cookiecutter>=2.6`. The CI render and the dev environment can differ.
Do: Decide whether to keep the exact pin in the bootstrap workflow (reproducibility for end users) and note the tested range in `docs/dev-setup.md`, or align both. Record the outcome in `plan/decisions.md` if it changes a decision. Make the smallest edit.
Done-when: the two pins are intentionally consistent or the difference is documented in one line.

### 1.4 Run the full suite and review the diff — [x]
Class: review · Needs: 1.2, 1.3 · Check: `make test`
Context: Prior to this work the suite was reported green (184 passed in `plan/journal.md`). Workflow YAML must still parse after substitution.
Do: Run `make test`, then `git diff` and confirm that only the intended files changed. Generate a project for `master` and `main` and run `python3 -c "import yaml,glob;[yaml.safe_load(open(f)) for f in glob.glob('<out>/.github/workflows/*.yml')]"`.
Done-when: `make test` exits 0 and the rendered workflows parse with the literal branch in `on.push.branches`.
