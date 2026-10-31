"""An already-scaffolded repo adopts the companion feature through ``upgrade``."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from conftest import DEFAULT_CONTEXT, ROOT, _tpl_git, commit_all, run
from cookiecutter.main import cookiecutter

BEFORE_COMPANION = "5811a06"  # the last template commit without companion.yaml

ADDED = (
    "companion.yaml",
    "schemas/companion.schema.json",
    "scripts/article/companion.py",
)
PUBLISH = ".github/workflows/publish-companion.yml"
WITH_PUBLISH = "d1bc736"  # the last template commit that shipped the article-side workflow


def _call(project: Path, call: str) -> dict:
    code = (
        "import json\nfrom pathlib import Path\nfrom scripts.article import upgrade\n"
        f"try:\n    out = {call}\nexcept upgrade.UpgradeError as exc:\n"
        "    out = {'error': exc.code, 'message': exc.message}\nprint(json.dumps(out))\n"
    )
    result = run(project, "python3", "-c", code)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _template_from(tmp_path_factory: pytest.TempPathFactory, base: str) -> dict[str, str]:
    """A clone at template commit ``base``, plus one commit holding this working tree."""
    if run(ROOT, "git", "cat-file", "-e", f"{base}^{{commit}}").returncode != 0:
        pytest.skip(f"template history lacks {base} (shallow checkout)")
    tpl = tmp_path_factory.mktemp("tpl") / "template"
    _tpl_git(ROOT, "clone", "--quiet", str(ROOT), str(tpl))
    _tpl_git(tpl, "checkout", "--quiet", base)
    old = _tpl_git(tpl, "rev-parse", "HEAD")
    old_source = tmp_path_factory.mktemp("old") / "src"
    shutil.copytree(tpl, old_source, ignore=shutil.ignore_patterns(".git"))
    for tracked in _tpl_git(tpl, "ls-files").splitlines():
        (tpl / tracked).unlink()
    listing = _tpl_git(ROOT, "ls-files", "-co", "--exclude-standard", "-z").split("\0")
    for name in filter(None, listing):
        if (ROOT / name).is_file():
            (tpl / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, tpl / name)
    _tpl_git(tpl, "add", "-A")
    _tpl_git(tpl, "commit", "--quiet", "-m", "working tree")
    return {"path": str(tpl), "old": old, "old_source": str(old_source),
            "new": _tpl_git(tpl, "rev-parse", "HEAD")}


def _repo_from(tmp_path: Path, template: dict[str, str]) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    project = Path(cookiecutter(
        template["old_source"], no_input=True, output_dir=str(out),
        extra_context=dict(DEFAULT_CONTEXT),
    ))
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=template["path"], template_commit=template["old"])
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    commit_all(project)
    return project


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """The last pre-companion template commit, upgraded to this working tree."""
    return _template_from(tmp_path_factory, BEFORE_COMPANION)


@pytest.fixture(scope="module")
def publish_template(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """The last template commit that shipped publish-companion.yml, upgraded to this tree."""
    return _template_from(tmp_path_factory, WITH_PUBLISH)


@pytest.fixture()
def old_repo(tmp_path: Path, template: dict[str, str]) -> Path:
    """A repo generated before companion.yaml existed."""
    project = _repo_from(tmp_path, template)
    assert not (project / "companion.yaml").exists()
    return project


def _apply(project: Path, template: dict[str, str]) -> dict:
    return _call(
        project, f"upgrade.apply(Path('.'), {template['new']!r}, python={sys.executable!r})"
    )


def _upgrade(project: Path, template: dict[str, str]) -> None:
    applied = _apply(project, template)
    assert applied.get("conflicted") == [], applied
    finished = _call(project, "upgrade.finish(Path('.'))")
    assert finished.get("ok"), finished
    run(project, "git", "commit", "--quiet", "-m", "chore: upgrade")


def test_upgrade_delivers_the_companion_feature(
    old_repo: Path, template: dict[str, str]
) -> None:
    before = (old_repo / "CITATION.cff").read_text(encoding="utf-8")
    assert "github.com/test-user/articles.test_topic.public" not in before
    _upgrade(old_repo, template)

    for name in ADDED:
        assert (old_repo / name).is_file(), name
    config = yaml.safe_load((old_repo / "companion.yaml").read_text(encoding="utf-8"))
    assert config["repo"] == "test-user/articles.test_topic.public"
    cff = (old_repo / "CITATION.cff").read_text(encoding="utf-8")
    assert "github.com/test-user/articles.test_topic.public" in cff
    assert run(old_repo, "python3", "-m", "scripts.article", "companion", "--plan").returncode == 0


def test_upgrade_never_adds_the_article_side_publish_workflow(
    old_repo: Path, template: dict[str, str]
) -> None:
    _upgrade(old_repo, template)
    assert not (old_repo / PUBLISH).exists()


def test_upgrade_removes_the_article_side_publish_workflow(
    tmp_path: Path, publish_template: dict[str, str]
) -> None:
    project = _repo_from(tmp_path, publish_template)
    assert (project / PUBLISH).is_file()
    applied = _apply(project, publish_template)
    assert PUBLISH in applied["applied"], applied
    assert applied["conflicted"] == [], applied
    assert not (project / PUBLISH).exists()
    finished = _call(project, "upgrade.finish(Path('.'))")
    assert finished.get("ok"), finished
    run(project, "git", "commit", "--quiet", "-m", "chore: upgrade")
    assert PUBLISH not in run(project, "git", "ls-files").stdout.split()


def test_upgrade_flags_an_edited_publish_workflow_instead_of_deleting_it(
    tmp_path: Path, publish_template: dict[str, str]
) -> None:
    project = _repo_from(tmp_path, publish_template)
    workflow = project / PUBLISH
    workflow.write_text(workflow.read_text(encoding="utf-8") + "# local edit\n", encoding="utf-8")
    commit_all(project)
    applied = _apply(project, publish_template)
    assert PUBLISH in applied["conflicted"] or any(
        entry["path"] == PUBLISH for entry in applied["skipped"]
    ), applied


def test_second_upgrade_is_a_no_op(old_repo: Path, template: dict[str, str]) -> None:
    _upgrade(old_repo, template)
    snapshot = {p: p.read_bytes() for p in old_repo.rglob("*")
                if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts}
    plan = _call(old_repo, f"upgrade.plan(Path('.'), {template['new']!r})")
    assert plan["plan"]["up_to_date"] is True
    again = _apply(old_repo, template)
    assert not again.get("conflicted"), again
    after = {p: p.read_bytes() for p in old_repo.rglob("*")
             if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts}
    assert after == snapshot
    assert run(old_repo, "git", "status", "--porcelain").stdout.strip() == ""


def test_regenerated_citation_does_not_trip_the_drift_check(
    old_repo: Path, template: dict[str, str]
) -> None:
    applied = _apply(old_repo, template)
    assert applied.get("conflicted") == [], applied
    finished = _call(old_repo, "upgrade.finish(Path('.'))")
    assert finished.get("error") != "U019", finished
    assert finished.get("ok"), finished


def test_hand_edited_companion_yaml_survives_a_later_upgrade(
    old_repo: Path, template: dict[str, str]
) -> None:
    _upgrade(old_repo, template)
    path = old_repo / "companion.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "# author note\n", encoding="utf-8")
    run(old_repo, "git", "commit", "--quiet", "-am", "docs: tune companion")
    edited = path.read_bytes()

    # A later template commit that also changes companion.yaml.
    tpl = Path(template["path"])
    shipped = tpl / "{{cookiecutter.repo_name}}" / "companion.yaml"
    shipped.write_text(shipped.read_text(encoding="utf-8") + "# template note\n",
                       encoding="utf-8")
    _tpl_git(tpl, "add", "-A")
    _tpl_git(tpl, "commit", "--quiet", "-m", "later")
    later = _tpl_git(tpl, "rev-parse", "HEAD")
    try:
        out = _call(
            old_repo, f"upgrade.apply(Path('.'), {later!r}, python={sys.executable!r})"
        )
        assert "companion.yaml" not in out.get("conflicted", []), out
        assert path.read_bytes() == edited
    finally:
        _tpl_git(tpl, "reset", "--quiet", "--hard", template["new"])


def test_upgrade_does_not_launder_a_private_related_link(
    old_repo: Path, template: dict[str, str]
) -> None:
    """upgrade never rewrites metadata.yaml, so the new validator must catch the link."""
    path = old_repo / "metadata.yaml"
    private = "https://github.com/test-user/articles.test_topic"
    path.write_text(
        path.read_text(encoding="utf-8")
        + f"related_identifiers:\n  - identifier: {private}\n"
        "    relation: isSupplementTo\n    scheme: url\n",
        encoding="utf-8",
    )
    assert run(old_repo, "make", "metadata").returncode == 0
    run(old_repo, "git", "commit", "--quiet", "-am", "docs: link")
    applied = _apply(old_repo, template)
    assert applied.get("conflicted") == [], applied

    finished = _call(old_repo, "upgrade.finish(Path('.'))")
    assert finished.get("error") == "U016", finished
    assert "E034" in finished["message"] and private in finished["message"]
    assert private in path.read_text(encoding="utf-8")
    assert run(old_repo, "python3", "scripts/validate-paper.py").returncode == 1
