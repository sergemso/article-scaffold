"""Public companion repo: configuration reader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

CONFIG_NAME = "companion.yaml"
REPO_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_KEYS = {"version", "repo", "branch", "include", "exclude"}


def _string_list(data: dict[str, Any], key: str, *, non_empty: bool) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{CONFIG_NAME}: '{key}' must be a list of strings")
    if non_empty and not value:
        raise ValueError(f"{CONFIG_NAME}: '{key}' must not be empty")
    if not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{CONFIG_NAME}: '{key}' must contain non-empty strings")
    return list(value)


def read_config(root: Path) -> dict[str, Any] | None:
    """Return the validated companion config, or None when the file is absent."""
    path = Path(root) / CONFIG_NAME
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{CONFIG_NAME}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_NAME}: must be a mapping")
    unknown = sorted(set(data) - _KEYS)
    if unknown:
        raise ValueError(f"{CONFIG_NAME}: unknown keys: {', '.join(unknown)}")
    missing = sorted(_KEYS - set(data))
    if missing:
        raise ValueError(f"{CONFIG_NAME}: missing keys: {', '.join(missing)}")
    if data["version"] != 1 or isinstance(data["version"], bool):
        raise ValueError(f"{CONFIG_NAME}: 'version' must be 1")
    repo = data["repo"]
    if not isinstance(repo, str) or not REPO_PATTERN.match(repo):
        raise ValueError(f"{CONFIG_NAME}: 'repo' must look like OWNER/NAME")
    branch = data["branch"]
    if not isinstance(branch, str) or not branch:
        raise ValueError(f"{CONFIG_NAME}: 'branch' must be a non-empty string")
    return {
        "version": 1,
        "repo": repo,
        "branch": branch,
        "include": _string_list(data, "include", non_empty=True),
        "exclude": _string_list(data, "exclude", non_empty=False),
    }
