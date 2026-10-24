"""The one-file script that gives an older generated repo the upgrade command."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from conftest import render

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap-upgrader.py"


def _bootstrap(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--repo", str(project), *args],
        capture_output=True,
        text=True,
    )


def _old_repo(tmp_path: Path) -> Path:
    project = render(tmp_path=tmp_path)
    shutil.rmtree(project / "scripts" / "article")
    return project


def test_installs_the_command_into_an_older_repo(tmp_path: Path) -> None:
    project = _old_repo(tmp_path)
    metadata_before = (project / "metadata.yaml").read_bytes()

    result = _bootstrap(project, "--template", str(ROOT))

    assert result.returncode == 0, result.stderr
    assert (project / "scripts" / "article" / "upgrade.py").is_file()
    assert (project / "schemas" / "upgrade.schema.json").is_file()
    assert not list((project / "scripts" / "article").rglob("__pycache__"))
    assert (project / "metadata.yaml").read_bytes() == metadata_before

    plan = subprocess.run(
        [sys.executable, "-m", "scripts.article", "upgrade", "--plan", "--json"],
        cwd=project,
        capture_output=True,
        text=True,
    )
    assert '"mode": "plan"' in plan.stdout, plan.stderr


def test_reads_the_template_from_template_json(tmp_path: Path) -> None:
    project = _old_repo(tmp_path)

    result = _bootstrap(project)

    assert result.returncode == 0, result.stderr
    assert (project / "scripts" / "article" / "__main__.py").is_file()


def test_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    marker = project / "scripts" / "article" / "core.py"
    marker.write_text("# local edit\n", encoding="utf-8")

    refused = _bootstrap(project, "--template", str(ROOT))
    assert refused.returncode != 0 and "already exists" in refused.stderr
    assert marker.read_text(encoding="utf-8") == "# local edit\n"

    forced = _bootstrap(project, "--template", str(ROOT), "--force")
    assert forced.returncode == 0, forced.stderr
    assert marker.read_text(encoding="utf-8") != "# local edit\n"


def test_refuses_outside_a_generated_repo(tmp_path: Path) -> None:
    result = _bootstrap(tmp_path, "--template", str(ROOT))

    assert result.returncode != 0 and "metadata.yaml" in result.stderr
