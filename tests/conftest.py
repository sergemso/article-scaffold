"""Shared fixtures for template regression tests."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from cookiecutter.main import cookiecutter

ROOT = Path(__file__).resolve().parents[1]

# A complete, deterministic context. Tests override only the fields they care
# about; passing the whole context keeps the render independent of the current
# cookiecutter.json defaults.
DEFAULT_CONTEXT: dict[str, str] = {
    "topic": "test_topic",
    "github_user": "test-user",
    "title": "A Test Manuscript",
    "subtitle": "",
    "manuscript_type": "Perspective / Review Essay",
    "author_name": "Ada Lovelace",
    "author_orcid": "0000-0002-1825-0097",
    "author_affiliation": "Analytical Engine Institute",
    "version": "1.0.0",
    "version_label": "v1 preprint",
    "date": "2026-01-02",
    "license": "CC-BY-4.0",
    "target_deposit": "Zenodo",
    "doi": "",
    "keywords": "testing, metadata",
    "abstract": "A short abstract used by the render tests.",
}

SPECIAL_TITLE = 'He said "hello" & 100% _ok — ünïcode'
SPECIAL_ABSTRACT = 'A "quoted" abstract with 100% & # and — unicode.'


def render(
    context: dict[str, str] | None = None,
    tmp_path: Path | None = None,
    **overrides: str,
) -> Path:
    """Render the template with no prompts and return the generated project."""
    if tmp_path is None:
        raise TypeError("render() requires tmp_path")
    ctx = dict(DEFAULT_CONTEXT)
    if context:
        ctx.update(context)
    ctx.update(overrides)

    output_dir = Path(tmp_path) / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    project = cookiecutter(
        str(ROOT),
        no_input=True,
        output_dir=str(output_dir),
        extra_context=ctx,
    )
    return Path(project)


def run(project: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Run a command inside a rendered project, with a deterministic git identity."""
    return subprocess.run(
        list(args),
        cwd=project,
        text=True,
        capture_output=True,
        check=check,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(project.parent),
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        },
    )


def commit_all(project: Path) -> None:
    """Create an initial commit so later diffs are meaningful."""
    run(project, "git", "add", "-A", check=True)
    run(project, "git", "commit", "-qm", "initial", check=True)


@pytest.fixture()
def default_project(tmp_path: Path) -> Path:
    return render(tmp_path=tmp_path)


@pytest.fixture()
def special_project(tmp_path: Path) -> Path:
    return render(
        tmp_path=tmp_path,
        title=SPECIAL_TITLE,
        abstract=SPECIAL_ABSTRACT,
        keywords="quotes, 100%, #hashtag",
    )


@pytest.fixture()
def doi_project(tmp_path: Path) -> Path:
    return render(tmp_path=tmp_path, doi="10.5281/zenodo.1234567")


def _tpl_git(path: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@invalid",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@invalid",
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(path),
    }
    return subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


@pytest.fixture(scope="session")
def upgrade_template(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """A throwaway clone of the template with commit A, then B (one edit, one new file)."""
    probe = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    if probe.returncode != 0:
        pytest.skip("the template is not a git checkout")
    tpl = tmp_path_factory.mktemp("tpl") / "template"
    _tpl_git(ROOT, "clone", "--quiet", str(ROOT), str(tpl))
    a = _tpl_git(tpl, "rev-parse", "HEAD")
    status = tpl / "{{cookiecutter.repo_name}}" / "scripts" / "article" / "status.py"
    status.write_text(
        status.read_text(encoding="utf-8") + "\n# template change B\n", encoding="utf-8"
    )
    (tpl / "{{cookiecutter.repo_name}}" / "docs" / "NEW.md").write_text(
        "added in B\n", encoding="utf-8"
    )
    _tpl_git(tpl, "add", "-A")
    _tpl_git(tpl, "commit", "--quiet", "-m", "B")
    return {"path": str(tpl), "a": a, "b": _tpl_git(tpl, "rev-parse", "HEAD")}


@pytest.fixture()
def upgrade_project(tmp_path: Path, upgrade_template: dict[str, str]) -> Path:
    """A committed repo stamped as generated from template commit A."""
    project = render(tmp_path=tmp_path)
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=upgrade_template["path"], template_commit=upgrade_template["a"])
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    commit_all(project)
    return project


@pytest.fixture(scope="session")
def flow_base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return render(tmp_path=tmp_path_factory.mktemp("flowbase"))


@pytest.fixture()
def flow_project(flow_base: Path, tmp_path: Path) -> Path:
    """A rendered repo with the dialectic stage advisory (the pre-0084 default), so the
    stage tests opt in with ``required_stages`` and every other flow test starts at frame.
    ``fresh_project`` keeps the template's shipped flow.yaml."""
    target = tmp_path / "repo"
    shutil.copytree(flow_base, target)
    flow = target / "flow.yaml"
    lines = [ln for ln in flow.read_text(encoding="utf-8").splitlines(keepends=True)
             if not ln.startswith("required_stages:")]
    flow.write_text("".join(lines), encoding="utf-8")
    return target


@pytest.fixture()
def fresh_project(flow_base: Path, tmp_path: Path) -> Path:
    """A rendered repo exactly as the template ships it."""
    target = tmp_path / "fresh"
    shutil.copytree(flow_base, target)
    return target


# Upgrade tests render old and new template trees through cookiecutter (~8s each), about a
# third of the suite's CPU time. `make test-fast` deselects them with `-m "not slow"`.
SLOW_MODULES = {
    "test_upgrade_apply.py",
    "test_upgrade_cli.py",
    "test_upgrade_companion.py",
    "test_upgrade_review_fixes.py",
    "test_upgrade_theses.py",
    "test_upgrade_user_owned.py",
    "test_upgrade_workflow.py",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if Path(str(item.fspath)).name in SLOW_MODULES:
            item.add_marker(pytest.mark.slow)
