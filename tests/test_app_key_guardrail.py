"""Guardrail app-key-stays-in-scaffold: the App key never leaves the scaffold's workflows."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
WORKFLOWS = ROOT / ".github" / "workflows"
ACTION = ROOT / ".github" / "actions" / "app-token" / "action.yml"
APP_NAMES = ("APP_PRIVATE_KEY", "APP_ID")
RETIRED_NAMES = ("APP_PRIVATE_KEY", "GH_PAT", "COMPANION_PAT", "COMPANION_TOKEN")
MINT = "actions/create-github-app-token"
COMPOSITE = "./.github/actions/app-token"


def _files(*roots: Path) -> list[Path]:
    out = []
    for top in roots:
        paths = [top] if top.is_file() else sorted(top.rglob("*"))
        out += [p for p in paths if p.is_file() and "__pycache__" not in p.parts]
    return out


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def _steps(path: Path):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    for name, job in (doc.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            yield name, step


def _mints():
    """Every step that mints a token, directly or through the composite action."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for job, step in _steps(path):
            uses = step.get("uses", "")
            if uses.startswith(MINT) or uses == COMPOSITE:
                yield path.name, job, step
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    for step in action["runs"]["steps"]:
        if step.get("uses", "").startswith(MINT):
            yield ACTION.name, "composite", step


def test_app_credentials_are_read_only_by_scaffold_workflows() -> None:
    outside = [ROOT / "scripts", ROOT / "Makefile", ROOT / "cookiecutter.json", ROOT / "hooks"]
    for path in _files(*[p for p in outside if p.exists()]):
        text = _text(path)
        for name in APP_NAMES:
            assert not re.search(rf"\b{name}\b", text), f"{path.relative_to(ROOT)} names {name}"


def test_template_names_no_app_or_retired_credential() -> None:
    for path in _files(TEMPLATE):
        text = _text(path)
        for name in RETIRED_NAMES + ("APP_ID",):
            assert not re.search(rf"\b{name}\b", text), f"{path.relative_to(ROOT)} names {name}"


def test_secrets_are_read_only_where_the_key_is_passed() -> None:
    """secrets.APP_PRIVATE_KEY appears only as the private-key input of a mint step."""
    for path in sorted(WORKFLOWS.glob("*.yml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        uses = []
        for job in doc["jobs"].values():
            for step in job.get("steps") or []:
                for key, value in (step.get("with") or {}).items():
                    if "secrets.APP_PRIVATE_KEY" in str(value):
                        uses.append(key)
                assert "secrets.APP_PRIVATE_KEY" not in str(step.get("env", "")), path.name
                assert "secrets.APP_PRIVATE_KEY" not in str(step.get("run", "")), path.name
        assert set(uses) <= {"private-key"}, (path.name, uses)


def test_every_mint_passes_an_owner_and_narrows_permissions() -> None:
    mints = list(_mints())
    assert len(mints) >= 5
    for where, job, step in mints:
        with_ = step.get("with") or {}
        label = f"{where}:{job}"
        assert with_.get("owner"), f"{label} mints without `owner`"
        if where != ACTION.name:
            perms = [k for k in with_ if k.startswith("permission-")]
            assert perms, f"{label} mints with the App's whole grant"


def test_composite_action_checks_the_allowlist_before_minting() -> None:
    action = yaml.safe_load(ACTION.read_text(encoding="utf-8"))
    steps = action["runs"]["steps"]
    check = next(i for i, s in enumerate(steps) if "APP_OWNERS" in str(s.get("env", "")))
    mint = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith(MINT))
    assert check < mint


def test_no_workflow_or_script_echoes_a_token_or_sets_a_secret() -> None:
    sources = _files(WORKFLOWS, ACTION, ROOT / "scripts")
    for path in sources:
        text = _text(path)
        rel = path.relative_to(ROOT)
        for line in text.splitlines():
            code = line.split("#", 1)[0] if path.suffix == ".py" else line
            if re.search(r"\becho\b[^\n]*(\$\{?(GH_)?TOKEN|steps\.\w+\.outputs\.token)", code):
                raise AssertionError(f"{rel} echoes a token: {line.strip()}")
            assert not re.search(r"gh\s+secret\s+set", code), f"{rel} sets a secret"
            assert "--secret" not in code, f"{rel} passes a secret on a command line"
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for _, step in _steps(path):
            if "GH_TOKEN" in (step.get("env") or {}) and "run" in step:
                assert "set +x" in step["run"], f"{path.name}: token in env without `set +x`"


def test_retired_credentials_are_gone_from_the_scaffold() -> None:
    for path in _files(WORKFLOWS, ACTION, ROOT / "scripts"):
        text = _text(path)
        for name in ("GH_PAT", "COMPANION_PAT", "COMPANION_TOKEN"):
            assert name not in text, f"{path.relative_to(ROOT)} still names {name}"
