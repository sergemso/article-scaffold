"""post_gen_project.py — runs after cookiecutter renders the template.

Installs the pre-push hook and makes scripts executable so the new
repo is ready to `git init && git add . && git commit`.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_dir = Path.cwd()

    # 1. Ensure scripts are executable.
    scripts_dir = project_dir / "scripts"
    if scripts_dir.is_dir():
        for script in scripts_dir.iterdir():
            if script.is_file():
                mode = script.stat().st_mode
                script.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # 2. Initialise git repo if not already inside one.
    in_git_repo = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if in_git_repo.returncode != 0 or in_git_repo.stdout.strip() != "true":
        subprocess.run(["git", "init", "--initial-branch=master"], check=True)

    # 3. Install pre-push hook.
    git_dir = project_dir / ".git"
    if not git_dir.is_dir():
        # Shouldn't happen after step 2, but be defensive.
        print("WARNING: .git directory not found; skipping pre-push hook install.")
    else:
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir(exist_ok=True)
        src = project_dir / "scripts" / "pre-push"
        dst = hooks_dir / "pre-push"
        if src.is_file():
            shutil.copy2(src, dst)
            mode = dst.stat().st_mode
            dst.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print("Installed pre-push hook -> .git/hooks/pre-push")

    # 4. Friendly next-steps banner.
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
    print("  2. Regenerate derived metadata:")
    print("       make metadata")
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
    print("       git branch -M master")
    print("       git remote add origin git@github.com:<user>/<repo>.git")
    print("       git push -u origin master")
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
