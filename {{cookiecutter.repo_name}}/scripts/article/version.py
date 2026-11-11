"""Which template version a repository was generated from."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPLATE_VERSION = "1.5.1"  # fallback when neither metadata nor template.json names one


def installed_template_version(root: Path, metadata: dict[str, Any] | None = None) -> str:
    """Template version: a metadata override, else the template.json stamp, else the fallback."""
    if metadata and metadata.get("template_version"):
        return str(metadata["template_version"])
    try:
        stamp = json.loads((root / "template.json").read_text(encoding="utf-8"))
        version = stamp.get("template_version") if isinstance(stamp, dict) else None
    except (OSError, ValueError):
        version = None
    return str(version) if version else TEMPLATE_VERSION
