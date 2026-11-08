"""Step C.1: the code index maps supplementary Python and Rust symbols to line ranges."""

from __future__ import annotations

import json
import os
import shutil
import sys

import jsonschema
import pytest
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
FIXTURES = ROOT / "tests" / "fixtures" / "code"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import cli  # noqa: E402

RESULT = json.loads((TEMPLATE / "schemas" / "index-result.schema.json").read_text())
INDEX = "paper/build/code-index.json"


def run(capsys, root, *argv):
    code = cli.main(["--root", str(root), "index", *argv, "--json"] if "slice" not in argv
                    else ["--root", str(root), "index", *argv])  # fmt: skip
    out = json.loads(capsys.readouterr().out)
    jsonschema.validate(out, RESULT)
    return code, out


@pytest.fixture
def repo(tmp_path):
    target = tmp_path / "paper" / "supplementary" / "tools"
    target.mkdir(parents=True)
    for name in ("sample.py", "sample.rs"):
        shutil.copy(FIXTURES / name, target / name)
    shutil.copy(FIXTURES / "broken.py.txt", target / "broken.py")  # not valid Python
    return tmp_path


def symbols(root):
    data = json.loads((root / INDEX).read_text())
    return {(s["file"].rsplit("/", 1)[-1], s["name"]): s for s in data["symbols"]}


def test_python_symbols_are_qualified_with_stable_ranges(repo, capsys):
    code, out = run(capsys, repo)
    assert code == 0 and out["symbols"] > 0
    found = symbols(repo)
    assert found["sample.py", "top"]["lines"] == [4, 5]
    assert found["sample.py", "Suite"]["lines"] == [8, 23]
    assert found["sample.py", "Suite.build"]["lines"] == [11, 13]  # decorator included
    assert found["sample.py", "Suite.Nested.run"]["kind"] == "method"
    assert found["sample.py", "fetch"]["kind"] == "function"
    assert found["sample.py", "test_top"]["kind"] == "test"
    assert ("sample.py", "inner") not in found and ("sample.py", "Suite.run.inner") not in found
    first = (repo / INDEX).read_bytes()
    run(capsys, repo)
    assert (repo / INDEX).read_bytes() == first


def test_rust_symbols_cover_impls_traits_and_tests(repo, capsys):
    run(capsys, repo)
    found = symbols(repo)
    expected = {
        "Point": ("struct", [5, 7]),
        "Unit": ("struct", [9, 9]),
        "Shape": ("enum", [11, 14]),
        "Area": ("trait", [16, 21]),
        "Area::area": ("method", [17, 17]),
        "Point::new": ("method", [24, 27]),
        "Point::load": ("method", [29, 34]),  # multi-line signature
        "fmt::Display for Wrapper::fmt": ("method", [41, 43]),  # generics and where stripped
        "Area for Point::area": ("method", [47, 49]),
        "impl Area for Point": ("impl", [46, 50]),
        "free": ("function", [52, 55]),  # char literal '{' does not unbalance
        "tests": ("mod", [57, 67]),
        "tests::it_works": ("test", [61, 64]),
        "tests::on_one_line": ("test", [66, 66]),
    }
    for name, (kind, lines) in expected.items():
        symbol = found["sample.rs", name]
        assert (symbol["kind"], symbol["lines"]) == (kind, lines), name
    assert ("sample.rs", "fake") not in found and ("sample.rs", "not_a_fn") not in found


def test_a_file_with_a_syntax_error_is_listed_not_fatal(repo, capsys):
    code, out = run(capsys, repo)
    assert code == 0
    assert [u["file"].rsplit("/", 1)[-1] for u in out["unparsed"]] == ["broken.py"]
    listed = json.loads((repo / INDEX).read_text())["files"]
    files = {f["file"].rsplit("/", 1)[-1]: f for f in listed}
    assert files["broken.py"]["status"] == "syntax-error"
    assert files["sample.py"]["status"] == "ok"


def test_slice_by_qualified_name_and_ambiguity(repo, capsys):
    run(capsys, repo)
    code, out = run(capsys, repo, "slice", "Suite.build")
    assert code == 0
    assert out["text"].splitlines()[0] == "    @staticmethod" and out["lines"] == [11, 13]
    code, out = run(capsys, repo, "slice", "Point::load")
    assert code == 0 and out["text"].startswith("    pub async fn load(")
    code, out = run(capsys, repo, "slice", "run")  # Suite.run and Suite.Nested.run
    assert code == 1 and {c["name"] for c in out["candidates"]} == {"Suite.run", "Suite.Nested.run"}
    code, out = run(capsys, repo, "slice", "area")  # trait method and impl method
    assert code == 1 and len(out["candidates"]) == 2
    code, out = run(capsys, repo, "slice", "top", "--file", "paper/supplementary/tools/sample.py")
    assert code == 0 and out["name"] == "top"
    code, out = run(capsys, repo, "slice", "nope")
    assert code == 1 and "no symbol" in out["error"]


def test_check_reports_missing_stale_added_and_removed(repo, capsys):
    code, out = run(capsys, repo, "--check")
    assert code == 1 and any("code-index.json is missing" in r for r in out["stale"])
    run(capsys, repo)
    assert run(capsys, repo, "--check")[0] == 0
    sample = repo / "paper/supplementary/tools/sample.py"
    later = (repo / INDEX).stat().st_mtime + 10
    sample.write_text(sample.read_text() + "\n\ndef added():\n    pass\n")
    os.utime(sample, (later, later))
    code, out = run(capsys, repo, "--check")
    assert code == 1 and any("sample.py is newer" in r for r in out["stale"])
    code, out = run(capsys, repo, "slice", "top")  # changed file, old index
    run(capsys, repo)
    future = sample.stat().st_mtime + 10
    os.utime(repo / INDEX, (future, future))
    assert run(capsys, repo, "--check")[0] == 0
    (repo / "paper/supplementary/tools/new.py").write_text("def n():\n    pass\n")
    new = (repo / INDEX).stat().st_mtime - 10
    os.utime(repo / "paper/supplementary/tools/new.py", (new, new))
    code, out = run(capsys, repo, "--check")
    assert code == 1 and any("new.py is not in" in r for r in out["stale"])
    run(capsys, repo)
    (repo / "paper/supplementary/tools/new.py").unlink()
    code, out = run(capsys, repo, "--check")
    assert code == 1 and any("new.py was removed" in r for r in out["stale"])


def test_slice_refuses_a_changed_file(repo, capsys):
    run(capsys, repo)
    sample = repo / "paper/supplementary/tools/sample.py"
    sample.write_text(sample.read_text().replace("return x", "return x + 1"))
    code, out = run(capsys, repo, "slice", "top")
    assert code == 1 and "changed since" in out["error"]


def test_no_code_means_no_code_index(tmp_path, capsys):
    code, out = run(capsys, tmp_path)
    assert code == 0 and "code_path" not in out and not (tmp_path / INDEX).exists()
    assert run(capsys, tmp_path, "--check")[0] == 0
    code, out = run(capsys, tmp_path, "slice", "x")
    assert code == 1 and "missing" in out["error"]
