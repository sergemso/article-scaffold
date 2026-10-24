"""post_gen_project.py — runs after cookiecutter renders the template.

Creates a nested git repository when the generated project is inside another
repo, installs the pre-push hook via ``core.hooksPath``, and makes scripts
executable so the new repo is ready to commit.
"""

import json
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML
    print(
        "ERROR: PyYAML is required to install the selected license and "
        "generate derived metadata; install it with `pip install pyyaml`.",
        file=sys.stderr,
    )
    sys.exit(1)


def _git_top_level(project_dir: Path, git: str) -> Path | None:
    result = subprocess.run(
        [git, "rev-parse", "--show-toplevel"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return Path(result.stdout.strip()).resolve()
    except OSError:
        return None


def _ensure_git_repo(project_dir: Path, git: str) -> bool:
    """Create .git unless the generated project is already a repo root."""
    if _git_top_level(project_dir, git) == project_dir.resolve():
        return True
    default_branch = "{{ cookiecutter.default_branch }}"
    result = subprocess.run(
        [git, "init", f"--initial-branch={default_branch}"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        print(
            f"WARNING: git init failed ({detail}); run `git init` and "
            "`make hooks` manually.",
            file=sys.stderr,
        )
        return False
    print("Initialized git repository")
    return True


def _install_pre_push_hook(project_dir: Path, git: str) -> None:
    src = project_dir / "scripts" / "pre-push"
    if not src.is_file():
        print("WARNING: scripts/pre-push not found; skipping hook install.")
        return

    hooks_dir = project_dir / "scripts" / "githooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    dst = hooks_dir / "pre-push"
    shutil.copy2(src, dst)
    mode = dst.stat().st_mode
    dst.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    configured = subprocess.run(
        [git, "config", "--local", "core.hooksPath", "scripts/githooks"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if configured.returncode == 0:
        print("Installed pre-push hook -> scripts/githooks/pre-push (core.hooksPath)")
        return

    # Fallback for unusual git configurations: copy into .git/hooks.
    git_dir = project_dir / ".git"
    if git_dir.is_dir():
        fallback_dir = git_dir / "hooks"
        fallback_dir.mkdir(exist_ok=True)
        fallback = fallback_dir / "pre-push"
        shutil.copy2(src, fallback)
        fallback_mode = fallback.stat().st_mode
        fallback.chmod(fallback_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("Installed pre-push hook -> .git/hooks/pre-push (fallback)")
    else:
        print(
            "WARNING: could not enable the pre-push hook; run `make hooks` "
            "after initializing git.",
            file=sys.stderr,
        )


def _replace_default_branch_placeholder(project_dir: Path, default_branch: str) -> None:
    """Replace the __DEFAULT_BRANCH__ placeholder with the chosen default branch.

    Workflow files are copied without rendering, and GitHub Actions does not
    evaluate expressions in ``on.push.branches``, so the filter must be a literal.
    """
    workflow_dir = project_dir / ".github" / "workflows"
    if not workflow_dir.is_dir():
        return
    for workflow_file in workflow_dir.glob("*.yml"):
        try:
            content = workflow_file.read_text(encoding="utf-8")
            if "__DEFAULT_BRANCH__" in content:
                new_content = content.replace("__DEFAULT_BRANCH__", default_branch)
                workflow_file.write_text(new_content, encoding="utf-8")
                print(
                    f"  updated {workflow_file.relative_to(project_dir)} "
                    f"with default branch {default_branch}"
                )
        except (OSError, UnicodeDecodeError) as exc:
            print(
                f"WARNING: could not update {workflow_file}: {exc}",
                file=sys.stderr,
            )


def _template_version(template_dir: Path) -> str:
    """Read the template's own version from its pyproject.toml ("" if unknown)."""
    try:
        text = (template_dir / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else ""


def _template_commit(template_dir: Path, git: str | None) -> str | None:
    """Commit of the template checkout, or None when it is not a git checkout."""
    if git is None:
        return None
    result = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=template_dir,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    return commit if result.returncode == 0 and commit else None


def _stamp_template_version(project_dir: Path, git: str | None) -> None:
    """Record which template version produced this repo in template.json."""
    stamp_path = project_dir / "template.json"
    if not stamp_path.is_file():
        return
    template_dir = Path(r"{{ cookiecutter._repo_dir }}")
    try:
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        stamp["template_version"] = _template_version(template_dir)
        stamp["template_commit"] = _template_commit(template_dir, git)
        stamp_path.write_text(
            json.dumps(stamp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except (OSError, ValueError) as exc:
        print(f"WARNING: could not stamp template.json: {exc}", file=sys.stderr)
        return
    print(f"Stamped template.json (template {stamp['template_version'] or 'unknown'})")


def main() -> None:
    project_dir = Path.cwd()

    # 1. Ensure scripts are executable.
    scripts_dir = project_dir / "scripts"
    if scripts_dir.is_dir():
        for script in scripts_dir.iterdir():
            if script.is_file():
                mode = script.stat().st_mode
                script.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # 2. Create a nested repo unless the project is already a repo root, then
    #    install the pre-push hook. Missing git is a warning, not a render
    #    failure: the scaffold remains usable and `make hooks` can finish later.
    git = shutil.which("git")
    if git is None:
        print(
            "WARNING: git not found; skipping repository initialization and "
            "pre-push hook installation. Install git, then run `git init` and "
            "`make hooks`.",
            file=sys.stderr,
        )
    elif _ensure_git_repo(project_dir, git):
        _install_pre_push_hook(project_dir, git)

    # 3. Install the selected paper license and the MIT code license.
    metadata_path = project_dir / "metadata.yaml"
    licenses_dir = project_dir / "licenses"
    if not metadata_path.is_file():
        print("ERROR: metadata.yaml not found; cannot select a license.", file=sys.stderr)
        sys.exit(1)
    try:
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"ERROR: metadata.yaml is not valid YAML: {exc}", file=sys.stderr)
        sys.exit(1)
    paper_license = str((metadata or {}).get("license", "")).strip()
    if paper_license == "CC-BY-4.0":
        paper_source = licenses_dir / "CC-BY-4.0.txt"
        code_source = licenses_dir / "MIT.txt"
    elif paper_license == "MIT":
        paper_source = licenses_dir / "MIT.txt"
        code_source = None
    else:
        print(
            "ERROR: unsupported license "
            f"{paper_license!r}; expected CC-BY-4.0 or MIT.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not paper_source.is_file():
        print(f"ERROR: vendored license text missing: {paper_source}", file=sys.stderr)
        sys.exit(1)
    shutil.copyfile(paper_source, project_dir / "LICENSE")
    if code_source is not None:
        shutil.copyfile(code_source, project_dir / "LICENSE-CODE")
    else:
        (project_dir / "LICENSE-CODE").unlink(missing_ok=True)
    if code_source is not None:
        print(f"Installed {paper_license} paper license and MIT code license")
    else:
        print(f"Installed {paper_license} paper and code license")

    # 4. Generate derived metadata from metadata.yaml.
    generator = project_dir / "scripts" / "generate-metadata.py"
    if generator.is_file():
        print("Generating derived metadata from metadata.yaml...")
        result = subprocess.run(
            [sys.executable, str(generator)],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(
                "ERROR: could not generate derived metadata. "
                "PyYAML is required; install it with `pip install pyyaml`.",
                file=sys.stderr,
            )
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(1)
        print("  generated CITATION.cff, .zenodo.json, README and article.tex metadata")
    else:
        print("WARNING: scripts/generate-metadata.py not found; skipping metadata generation.")

    # 4b. Replace __DEFAULT_BRANCH__ in workflow files with the chosen default branch.
    # Workflow files are copied without rendering (to keep Jinja2 away from Actions
    # expressions), and Actions does not evaluate expressions in on.push.branches.
    _replace_default_branch_placeholder(project_dir, "{{ cookiecutter.default_branch }}")

    # 4c. Stamp the template version so the repo can be upgraded later.
    _stamp_template_version(project_dir, git)

    # 5. Friendly next-steps banner.
    print()
    print("────────────────────────────────────────────────────────────")
    print(" Scaffolding complete.")
    print("────────────────────────────────────────────────────────────")
    print()
    print("Next steps:")
    print()
    print("  1. Edit metadata.yaml to refine title/author/version/doi.")
    print("     (You already entered these as cookiecutter prompts;")
    print("      metadata.yaml is now the single source of truth.)")
    print()
    print("  2. Review metadata.yaml (derived files are already generated):")
    print("       make metadata   # rerun after editing metadata.yaml")
    print()
    print("  3. Open paper/sections/00_abstract.tex and start writing.")
    print()
    print("  4. Validate locally (the pre-push hook runs this automatically):")
    print("       make validate")
    print()
    print("  5. Build the PDF:")
    print("       make pdf")
    print()
    print("  6. Commit:")
    print("       git add .")
    print("       git commit -m 'initial scaffold'")
    default_branch = "{{ cookiecutter.default_branch }}"
    print(f"       git branch -M {default_branch}")
    print("       git remote add origin git@github.com:<user>/<repo>.git")
    print(f"       git push -u origin {default_branch}")
    print()
    print("When you're ready to cut a release:")
    print("       git tag v1.0.0")
    print("       git push origin v1.0.0   # triggers release.yml")
    print()


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print(f"post_gen_project.py: command failed: {e}", file=sys.stderr)
        sys.exit(1)
