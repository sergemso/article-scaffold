"""Documentation hygiene tests: no stale paths, no personal identity in defaults."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"


def test_no_personal_identity_in_cookiecutter_json() -> None:
    """cookiecutter.json must not contain personal names/ORCIDs/GitHub users."""
    data = yaml.safe_load((ROOT / "cookiecutter.json").read_text())
    # These are the OLD personal values that should NOT be in the template anymore
    forbidden = [
        "Ada Lovelace",
        "Analytical Engine Institute",
        "sergemso",
        "0000-0002-1825-0097",  # Ada Lovelace's ORCID
        "Independent Researcher",  # old affiliation default
        "research, methodology",  # old keywords default
    ]
    # Check string values
    for key, value in data.items():
        if isinstance(value, str):
            for bad in forbidden:
                assert bad not in value, (
                    f"cookiecutter.json[{key!r}] contains forbidden string {bad!r}"
                )
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    for bad in forbidden:
                        assert bad not in item, (
                            f"cookiecutter.json[{key!r}] contains forbidden string {bad!r}"
                        )
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, str):
                    for bad in forbidden:
                        assert bad not in v, (
                            f"cookiecutter.json[{key!r}][{k!r}] contains "
                            f"forbidden string {bad!r}"
                        )


def test_no_personal_identity_in_readme() -> None:
    """Root README must not contain personal identity placeholders."""
    text = (ROOT / "README.md").read_text()
    # The README should reference config file for personal defaults
    # Old personal values that should not appear
    forbidden = [
        "Ada Lovelace",
        "Analytical Engine Institute",
        "sergemso",
        "0000-0002-1825-0097",  # Ada's ORCID
        "Independent Researcher",
        "research, methodology",
    ]
    for bad in forbidden:
        assert bad not in text, f"README contains forbidden string {bad!r}"
    # Should mention config file
    assert "~/.config/article-scaffold/config.yaml" in text
    assert "ARTICLE_SCAFFOLD_CONFIG" in text


def test_template_readme_has_no_placeholder_secrets() -> None:
    """Template README must not contain literal personal placeholders."""
    text = (TEMPLATE / "README.md").read_text()
    forbidden = [
        "Ada Lovelace",
        "Analytical Engine Institute",
        "sergemso",
        "0000-0002-1825-0097",
        "Independent Researcher",
        "research, methodology",
    ]
    for bad in forbidden:
        assert bad not in text, f"Template README contains forbidden string {bad!r}"


def test_no_jinja2_time_extension() -> None:
    """cookiecutter.json must not use jinja2_time extension."""
    data = yaml.safe_load((ROOT / "cookiecutter.json").read_text())
    extensions = data.get("_extensions", [])
    assert "jinja2_time.TimeExtension" not in extensions
    # Date should be a placeholder
    assert data.get("date") == "YYYY-MM-DD"


def test_gitignore_has_required_entries() -> None:
    """Template .gitignore must cover build/, .venv, generated dirs, biblatex."""
    text = (TEMPLATE / ".gitignore").read_text()
    required = [
        "paper/build/",
        ".venv/",
        "venv/",
        "paper/figures/generated/",
        "paper/supplementary/build/",
        "paper/*.bcf",
        "paper/*.run.xml",
    ]
    for entry in required:
        assert entry in text, f".gitignore missing required entry: {entry}"


def test_no_stale_paths_in_readme() -> None:
    """README must not reference stale/removed paths."""
    text = (ROOT / "README.md").read_text()
    # The root README should mention the new structure
    assert "paper/tables/" in text
    assert "raw/observations.csv" in text
    assert "analyze.py" in text
    assert "pyproject.toml" in text


def test_template_readme_matches_actual_structure() -> None:
    """Template README tree should match actual generated structure."""
    text = (TEMPLATE / "README.md").read_text()
    required_dirs = [
        "tables/",  # appears in tree under paper/
        "raw/observations.csv",  # appears in tree under data/
        "checksums.sha256",  # appears in tree under data/
        "analyze.py",  # appears in tree under analysis/
        "pyproject.toml",  # appears in tree under analysis/
        "uv.lock",  # appears in tree under analysis/
        ".latexmkrc",  # appears in tree under paper/
    ]
    for entry in required_dirs:
        assert entry in text, f"Template README missing {entry}"


def test_badge_block_only_for_used_services() -> None:
    """Root README badge block should only reference services actually used."""
    text = (ROOT / "README.md").read_text()
    # We use GitHub Actions for CI, so a CI badge is OK.
    # We don't use Codecov, ReadTheDocs, PyPI, etc.
    # The README currently has no badge block, which is correct.
    assert "badge" not in text.lower() or "github" in text.lower()


def test_hooks_not_copied_to_generated_repo() -> None:
    """Hooks should be in _copy_without_render so they're not rendered."""
    data = yaml.safe_load((ROOT / "cookiecutter.json").read_text())
    copy_without_render = data.get("_copy_without_render", [])
    # hooks/ should be listed so they're copied without Jinja rendering
    assert any("hooks" in item for item in copy_without_render), (
        "hooks/ not in _copy_without_render"
    )


def test_bootstrap_workflow_uses_dynamic_branch() -> None:
    """Bootstrap workflow must not hardcode master/main."""
    text = (ROOT / ".github" / "workflows" / "bootstrap-article.yml").read_text()
    assert "origin master" not in text
    assert "origin main" not in text
    assert "rev-parse --abbrev-ref HEAD" in text


def test_template_workflows_use_default_branch(tmp_path: Path) -> None:
    """Rendered workflows carry a literal branch filter, never an Actions expression."""
    from tests.conftest import render

    project = render(tmp_path=tmp_path, default_branch="master")
    for wf in (project / ".github" / "workflows").glob("*.yml"):
        doc = yaml.safe_load(wf.read_text())
        on = doc.get("on", doc.get(True))
        assert "${{" not in str(on), f"{wf.name} has an expression inside on:"
        assert "__DEFAULT_BRANCH__" not in wf.read_text(), f"{wf.name} kept the placeholder"