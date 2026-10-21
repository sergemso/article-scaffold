"""`generate-metadata.py --check` must detect drift without writing."""

from __future__ import annotations

from pathlib import Path

from conftest import commit_all, render, run


def _change_title(project: Path) -> None:
    path = project / "metadata.yaml"
    text = path.read_text()
    assert 'title: "A Test Manuscript"' in text
    path.write_text(text.replace('title: "A Test Manuscript"', 'title: "A Changed Title"'))


def test_clean_render_passes(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(project, "make", "metadata-check")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "up to date" in result.stdout


def test_drift_prints_diff_and_exits_one(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    _change_title(project)

    result = run(project, "python3", "scripts/generate-metadata.py", "--check")
    assert result.returncode == 1, result.stderr + result.stdout
    assert "drift: README.md" in result.stderr
    assert "---" in result.stderr
    assert "+++" in result.stderr
    assert "run `make metadata`" in result.stderr

    write = run(project, "make", "metadata")
    assert write.returncode == 0, write.stderr + write.stdout
    clean = run(project, "make", "metadata-check")
    assert clean.returncode == 0, clean.stderr + clean.stdout


def test_missing_generated_file_is_reported(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "CITATION.cff").unlink()

    result = run(project, "python3", "scripts/generate-metadata.py", "--check")
    assert result.returncode == 1, result.stderr + result.stdout
    assert "ERROR: missing CITATION.cff" in result.stderr

    # Write mode recreates a missing full-rewrite file.
    write = run(project, "make", "metadata")
    assert write.returncode == 0, write.stderr + write.stdout
    assert (project / "CITATION.cff").is_file()
    clean = run(project, "make", "metadata-check")
    assert clean.returncode == 0, clean.stderr + clean.stdout


def test_check_does_not_modify_the_tree(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    commit_all(project)
    result = run(project, "make", "metadata-check")
    assert result.returncode == 0, result.stderr + result.stdout
    status = run(project, "git", "status", "--porcelain")
    assert status.stdout.strip() == "", status.stdout


def test_pdf_target_does_not_write_metadata(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = run(project, "make", "-n", "pdf")
    assert result.returncode == 0, result.stderr + result.stdout
    assert "generate-metadata" not in result.stdout
