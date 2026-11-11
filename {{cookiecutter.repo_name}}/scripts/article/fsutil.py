"""Small filesystem helpers shared by the stores that must not be left half written."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def _umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def atomic_write(path: Path, data: bytes | str) -> None:
    """Write ``data`` to ``path`` through a temp file and ``os.replace``.

    A crash or interrupt leaves either the old file or the new one, never a truncated file.
    Text is written as UTF-8. Parent directories are created.
    """
    raw = data.encode("utf-8") if isinstance(data, str) else data
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
        os.chmod(tmp, path.stat().st_mode & 0o7777 if path.exists() else 0o666 & ~_umask())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
