"""post_gen_project.py — runs after cookiecutter renders the template.

Installs the pre-push hook and makes scripts executable so the new
repo is ready to `git init && git add . && git commit`.
"""

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

    # 4. Install the selected paper license and the MIT code license.
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

    # 5. Generate derived metadata from metadata.yaml.
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

    # 6. Friendly next-steps banner.
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
