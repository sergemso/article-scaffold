"""Stable diagnostic records shared by the validator, CLI, and MCP adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Diagnostic:
    """One error or warning with a stable, JSON-friendly shape."""

    path: str
    line: int
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "line": self.line,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class Diagnostics:
    """A collection that serializes to the documented diagnostics schema."""

    items: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        path: str | object,
        line: int,
        code: str,
        message: str,
        *,
        severity: Literal["error", "warning"] = "error",
    ) -> None:
        self.items.append(
            Diagnostic(
                path=str(path),
                line=line,
                code=code,
                message=message,
                severity=severity,
            )
        )

    def error(
        self, path: str | object, line: int, code: str, message: str
    ) -> None:
        self.add(path, line, code, message, severity="error")

    def warning(
        self, path: str | object, line: int, code: str, message: str
    ) -> None:
        self.add(path, line, code, message, severity="warning")

    @property
    def errors(self) -> list[Diagnostic]:
        return [item for item in self.items if item.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [item for item in self.items if item.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: Diagnostics) -> None:
        self.items.extend(other.items)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": self.ok,
            "diagnostics": [item.to_dict() for item in self.items],
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
        }

    def format_text(self) -> str:
        """Human-readable output matching the legacy validator format."""
        lines: list[str] = []
        for item in self.items:
            prefix = "WARNING: " if item.severity == "warning" else ""
            lines.append(f"{prefix}{item.path}:{item.line}: {item.code}: {item.message}")
        return "\n".join(lines)
