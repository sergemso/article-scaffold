"""Atomic state writes, the template version report and an invalid theses.yaml."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import render, run


def _py(project: Path, code: str):
    return run(project, "python3", "-c", code)


def test_atomic_write_replaces_text_and_leaves_no_temp_file(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _py(
        project,
        "from pathlib import Path\n"
        "from scripts.article.fsutil import atomic_write\n"
        "p = Path('sub/x.txt'); atomic_write(p, 'one'); atomic_write(p, 'two')\n"
        "print(p.read_text(), [q.name for q in p.parent.iterdir()])",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "two ['x.txt']"


def test_atomic_write_keeps_the_mode_of_an_existing_file(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    result = _py(
        project,
        "import os\nfrom pathlib import Path\n"
        "from scripts.article.fsutil import atomic_write\n"
        "p = Path('m.txt'); p.write_text('a'); os.chmod(p, 0o640); atomic_write(p, b'b')\n"
        "print(oct(p.stat().st_mode & 0o777))",
    )
    assert result.stdout.strip() == "0o640", result.stderr


def test_status_reports_the_stamped_template_version(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    stamp = json.loads((project / "template.json").read_text(encoding="utf-8"))
    stamp["template_version"] = "7.8.9"
    (project / "template.json").write_text(json.dumps(stamp), encoding="utf-8")
    result = run(project, "python3", "-m", "scripts.article", "status", "--json")
    assert json.loads(result.stdout)["template_version"] == "7.8.9"


def test_load_map_wraps_invalid_yaml(tmp_path: Path) -> None:
    project = render(tmp_path=tmp_path)
    (project / "theses.yaml").write_text("nodes: [unclosed\n", encoding="utf-8")
    result = _py(
        project,
        "from pathlib import Path\nimport yaml\n"
        "from scripts.article import theses\n"
        "try:\n    theses.load_map(Path('.'))\n"
        "except theses.MapYamlError as e:\n    print(isinstance(e, (ValueError, yaml.YAMLError)))",
    )
    assert result.stdout.strip() == "True", result.stderr
