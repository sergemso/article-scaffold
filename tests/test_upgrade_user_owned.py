"""An upgrade must not conflict over files the author owns.

Upgrades the previous release (1.4.1) to the template in this working tree for a repo
whose ``metadata.yaml`` and abstract the author has edited. Release 1.5.0 removed
placeholder lines next to such values and every one of them conflicted.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml
from conftest import DEFAULT_CONTEXT, ROOT, _tpl_git, commit_all, run
from cookiecutter.main import cookiecutter

PREVIOUS_RELEASE = "754a4f3"  # template 1.4.1, before the placeholders were removed

PLACEHOLDER_LINES = ("Perez", "independent evaluators", "# subtitle", "# release_notes")


def _call(project: Path, call: str) -> dict:
    code = (
        "import json\nfrom pathlib import Path\nfrom scripts.article import upgrade\n"
        f"try:\n    out = {call}\nexcept upgrade.UpgradeError as exc:\n"
        "    out = {'error': exc.code, 'message': exc.message}\nprint(json.dumps(out))\n"
    )
    result = run(project, "python3", "-c", code)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """A clone at the previous release, plus one commit holding this working tree."""
    if run(ROOT, "git", "cat-file", "-e", f"{PREVIOUS_RELEASE}^{{commit}}").returncode != 0:
        pytest.skip(f"template history lacks {PREVIOUS_RELEASE} (shallow checkout)")
    tpl = tmp_path_factory.mktemp("tpl") / "template"
    _tpl_git(ROOT, "clone", "--quiet", str(ROOT), str(tpl))
    _tpl_git(tpl, "checkout", "--quiet", PREVIOUS_RELEASE)
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


def _install_engine(project: Path, *, stale: bool) -> None:
    """Give the repo this tree's upgrade code, or a copy that no longer scopes the diff."""
    src = ROOT / "{{cookiecutter.repo_name}}" / "scripts" / "article"
    dest = project / "scripts" / "article"
    shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__"))
    if stale:
        path = dest / "upgrade.py"
        text = path.read_text(encoding="utf-8")
        assert "def _scope_trees(*trees: Path) -> None:\n" in text
        path.write_text(
            text.replace("def _scope_trees(*trees: Path) -> None:\n",
                         "def _scope_trees(*trees: Path) -> None:\n    return\n", 1),
            encoding="utf-8",
        )


@pytest.fixture(params=["current", "stale"])
def edited_repo(tmp_path: Path, template: dict[str, str], request: pytest.FixtureRequest) -> Path:
    """A repo generated from the previous release, then edited the way authors do.

    ``current``: the repo already carries this tree's upgrade code (a bootstrapped repo).
    ``stale``: its upgrade code is an older one that text-merges everything; the apply
    must hand over to the target template's code.
    """
    out = tmp_path / "out"
    out.mkdir()
    project = Path(cookiecutter(
        template["old_source"], no_input=True, output_dir=str(out),
        extra_context=dict(DEFAULT_CONTEXT),
    ))
    path = project / "metadata.yaml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('# subtitle: ""  # optional; uncomment and fill if needed',
                        'subtitle: "draft-05"')
    text = text.replace('references: []\n#  - "Perez',
                        'references:\n  - "Hood, C. (2026). AGTP."\n#  - "Perez')
    text = text.replace("# release_notes: |\n#   First public version.",
                        "release_notes: |\n  Fifth draft.")
    # The author's evidence note replaces the placeholder note.
    text = text.replace(
        'abstract_note: "Replace this paragraph', 'abstract_note: "The author built Termenbox.'
        ' Replace this paragraph',
    )
    path.write_text(text, encoding="utf-8")
    assert run(project, "python3", "-m", "scripts.article", "metadata").returncode == 0
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=template["path"], template_commit=template["old"],
                 template_version="1.4.1")
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    _install_engine(project, stale=request.param == "stale")
    commit_all(project)
    return project


def test_upgrade_leaves_edited_metadata_and_abstract_conflict_free(
    edited_repo: Path, template: dict[str, str], request: pytest.FixtureRequest
) -> None:
    out = _call(
        edited_repo,
        f"upgrade.apply(Path('.'), {template['new']!r}, python={sys.executable!r})",
    )
    # A stale repo's own upgrade.py differs from the template's, so that file may conflict;
    # what the author owns must not.
    assert set(out.get("conflicted", ["?"])) <= {"scripts/article/upgrade.py"}, out
    assert "metadata.yaml" in out["applied"]

    data = yaml.safe_load((edited_repo / "metadata.yaml").read_text(encoding="utf-8"))
    assert data["subtitle"] == "draft-05"
    assert data["references"] == ["Hood, C. (2026). AGTP."]
    assert data["release_notes"].strip() == "Fifth draft."
    assert data["abstract_note"].startswith("The author built Termenbox.")
    text = (edited_repo / "metadata.yaml").read_text(encoding="utf-8")
    assert "#   make metadata\n" in text and "generate-metadata.py" not in text
    for leftover in ("Perez", "independent evaluators", "# subtitle", "# release_notes: |"):
        assert leftover not in text, leftover

    if request.node.callspec.params["edited_repo"] == "stale":
        return  # its own conflicted upgrade.py cannot even be imported to finish
    finished = _call(edited_repo, "upgrade.finish(Path('.'))")
    assert finished.get("ok"), finished
    abstract = (edited_repo / "paper/sections/00_abstract.tex").read_text(encoding="utf-8")
    assert "The author built Termenbox." in abstract
    assert "<<<<<<<" not in abstract


def test_migration_keeps_values_and_only_removes_shipped_lines() -> None:
    sys.path.insert(0, str(ROOT / "{{cookiecutter.repo_name}}"))
    try:
        from scripts.article.migrations import migrate_metadata
    finally:
        sys.path.pop(0)
    perez = "Perez, C. (2002). Technological Revolutions and Financial Capital."
    text = f'# my own comment\n#  - "{perez}"\nkeywords: "a"\n'
    assert migrate_metadata(text, "1.4.1", "1.5.0") == '# my own comment\nkeywords: "a"\n'
    assert migrate_metadata(text, "1.5.0", "1.5.0") == text
    assert migrate_metadata(text, "", "") == text


def test_finish_does_not_stage_unrelated_untracked_files(
    tmp_path: Path, template: dict[str, str]
) -> None:
    project = tmp_path / "p"
    out = tmp_path / "out"
    out.mkdir()
    project = Path(cookiecutter(
        template["old_source"], no_input=True, output_dir=str(out),
        extra_context=dict(DEFAULT_CONTEXT),
    ))
    _install_engine(project, stale=False)
    stamp_path = project / "template.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    stamp.update(template=template["path"], template_commit=template["old"],
                 template_version="1.4.1")
    stamp_path.write_text(json.dumps(stamp), encoding="utf-8")
    commit_all(project)
    applied = _call(
        project, f"upgrade.apply(Path('.'), {template['new']!r}, python={sys.executable!r})"
    )
    assert applied.get("conflicted") == [], applied
    (project / "paper" / "target").mkdir()
    (project / "paper" / "target" / "junk.bin").write_text("x", encoding="utf-8")
    assert _call(project, "upgrade.finish(Path('.'))").get("ok")
    staged = run(project, "git", "diff", "--cached", "--name-only").stdout.splitlines()
    assert "template.json" in staged
    assert not [p for p in staged if "target" in p], staged
