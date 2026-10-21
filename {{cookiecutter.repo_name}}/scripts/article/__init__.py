"""Vendored article core package.

Importing this package is side-effect free. PyYAML is needed only for metadata
generation and parsing; validation and build planning are stdlib-only.
"""

from __future__ import annotations

from .core import *  # noqa: F403
from .core import CORE_VERSION, ExitCode, RepoPaths

__version__ = CORE_VERSION

__all__ = [
    "CORE_VERSION",
    "ExitCode",
    "RepoPaths",
    "__version__",
]
