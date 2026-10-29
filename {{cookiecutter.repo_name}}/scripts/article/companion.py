"""Public companion repo: configuration, snapshot build, gate and leak scan."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
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


# ── Snapshot ────────────────────────────────────────────────────────────────

FINAL_TAG = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
ARTIFACT_FILES = ("manuscript.pdf", "manuscript.docx")
SECRET_PATTERNS = (
    re.compile(rb"ghp_[A-Za-z0-9]{10,}"),
    re.compile(rb"github_pat_[A-Za-z0-9_]{10,}"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"xox[bp]-[A-Za-z0-9-]{4,}"),
)


class CompanionError(ValueError):
    """A snapshot cannot be built; the message says why."""


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a path glob: ``**`` crosses directories, ``*`` and ``?`` do not."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _matcher(patterns: list[str]):
    compiled = [_glob_regex(p) for p in patterns]
    return lambda path: any(rx.match(path) for rx in compiled)


def _walk(root: Path, prune: set[str]) -> list[str]:
    """Relative POSIX paths of regular files; symlinks are never followed."""
    found: list[str] = []
    for base, dirs, files in os.walk(root, followlinks=False):
        rel_base = Path(base).relative_to(root).as_posix()
        rel_base = "" if rel_base == "." else rel_base
        dirs[:] = sorted(
            d for d in dirs if (f"{rel_base}/{d}" if rel_base else d) not in prune
        )
        for name in files:
            full = Path(base) / name
            if full.is_symlink() or not full.is_file():
                continue
            found.append(f"{rel_base}/{name}" if rel_base else name)
    return sorted(found)


def resolve(root: Path, config: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (included, dropped): allowlisted files, and those a deny pattern removed."""
    root = Path(root)
    prune = {
        p[:-3]
        for p in config["exclude"]
        if p.endswith("/**") and not re.search(r"[*?]", p[:-3])
    }
    allowed = _matcher(config["include"])
    denied = _matcher(config["exclude"])
    included: list[str] = []
    dropped: list[str] = []
    for path in _walk(root, prune):
        if not allowed(path):
            continue
        (dropped if denied(path) else included).append(path)
    return included, dropped


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe(base: Path, paths: list[str]) -> dict[str, Any]:
    """Sorted file records and a tree hash over the sorted path and hash pairs."""
    files = [{"path": p, "sha256": _sha256(Path(base) / p)} for p in sorted(paths)]
    tree = hashlib.sha256()
    for item in files:
        tree.update(f"{item['path']}\0{item['sha256']}\n".encode())
    return {"files": files, "tree_sha256": tree.hexdigest()}


def _private_name(root: Path, config: dict[str, Any]) -> re.Pattern[bytes] | None:
    """Pattern matching the private repo's name, but not the companion's."""
    try:
        data = yaml.safe_load((Path(root) / "metadata.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict) or not data.get("github_user") or not data.get("repo_name"):
        return None
    private = f"{data['github_user']}/{data['repo_name']}"
    pattern = re.escape(private)
    companion = config["repo"]
    if companion.lower().startswith(private.lower()) and companion.lower() != private.lower():
        pattern += f"(?!{re.escape(companion[len(private):])})"
    return re.compile(pattern.encode(), re.IGNORECASE)


def _point_metadata_at_companion(root: Path, config: dict[str, Any], target: Path) -> None:
    """Rewrite the private repo name in the snapshot's metadata.yaml.

    ``repo_url`` there names the private repo; the snapshot describes the public one.
    """
    private = _private_name(root, config)
    if private is None or not target.is_file():
        return
    text = target.read_bytes()
    target.write_bytes(private.sub(config["repo"].encode(), text))


def leak_scan(
    root: Path, snapshot: Path, config: dict[str, Any], paths: list[str]
) -> list[str]:
    """Problems found in the snapshot; empty means it is safe to publish."""
    problems: list[str] = []
    denied = _matcher(config["exclude"])
    private = _private_name(root, config)
    for path in paths:
        if denied(path):
            problems.append(f"{path}: excluded path is in the snapshot")
        data = (Path(snapshot) / path).read_bytes()
        if private and private.search(data):
            problems.append(f"{path}: names the private repository")
        for rx in SECRET_PATTERNS:
            if rx.search(data):
                problems.append(f"{path}: matches secret pattern {rx.pattern.decode()}")
    return problems


def _collect_artifacts(artifacts: Path) -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    for name in ARTIFACT_FILES:
        if (artifacts / name).is_file():
            pairs.append((name, artifacts / name))
    if not (artifacts / "manuscript.pdf").is_file():
        raise CompanionError(f"{artifacts}: manuscript.pdf not found")
    supp = artifacts / "supp"
    if supp.is_dir():
        pairs += [(f"supp/{p.name}", p) for p in sorted(supp.glob("*.pdf"))]
    return pairs


def plan(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    included, dropped = resolve(root, config)
    return {
        "repo": config["repo"],
        "branch": config["branch"],
        "excluded": dropped,
        **describe(root, included),
    }


def build(
    root: Path, config: dict[str, Any], out: Path, artifacts: Path | None = None
) -> dict[str, Any]:
    """Write the snapshot to *out*; on any problem remove it and raise."""
    root, out = Path(root), Path(out)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise CompanionError(f"{out}: output directory must be empty or absent")
    included, dropped = resolve(root, config)
    extra = _collect_artifacts(Path(artifacts)) if artifacts else []
    clash = sorted(set(included) & {name for name, _ in extra})
    if clash:
        raise CompanionError(f"artifact would overwrite allowlisted file: {clash[0]}")
    out.mkdir(parents=True, exist_ok=True)
    try:
        for path in included:
            target = out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / path, target)
        if "metadata.yaml" in included:
            _point_metadata_at_companion(root, config, out / "metadata.yaml")
        for name, source in extra:
            target = out / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        paths = included + [name for name, _ in extra]
        problems = leak_scan(root, out, config, paths)
        if problems:
            raise CompanionError("leak scan failed: " + "; ".join(problems))
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise
    return {
        "repo": config["repo"],
        "branch": config["branch"],
        "excluded": dropped,
        **describe(out, paths),
    }


def gate(root: Path, tag: str) -> dict[str, Any]:
    """Whether *tag* may produce a public Release."""
    reasons: list[str] = []
    if not FINAL_TAG.match(tag):
        reasons.append(f"{tag!r} is not a final vX.Y.Z tag")
    version = None
    try:
        data = yaml.safe_load((Path(root) / "metadata.yaml").read_text(encoding="utf-8"))
        version = str(data.get("version", "")) if isinstance(data, dict) else ""
    except (OSError, yaml.YAMLError):
        pass
    if not version:
        reasons.append("metadata.yaml has no readable version")
    elif tag != f"v{version}":
        reasons.append(f"tag {tag!r} does not equal v{version} from metadata.yaml")
    return {"tag": tag, "version": version, "allowed": not reasons, "reasons": reasons}
