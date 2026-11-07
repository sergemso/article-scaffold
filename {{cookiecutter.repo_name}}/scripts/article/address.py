"""Source addresses: ``source-key@hash#locator`` (decision 0080).

Pure parsing, no file or network access. ``hash`` is a prefix of at least
12 hex characters of the normalized-text hash; ``locator`` is a stable id that the
locator index resolves to lines, never a raw line number.
"""

from __future__ import annotations

import re
from typing import NamedTuple

MIN_HASH = 12
KEYWORDS = (
    "MUST", "MUST_NOT", "REQUIRED", "SHALL", "SHALL_NOT", "SHOULD", "SHOULD_NOT",
    "RECOMMENDED", "NOT_RECOMMENDED", "MAY", "OPTIONAL",
)  # fmt: skip
_ADDRESS = re.compile(r"^(?P<key>[A-Za-z0-9][A-Za-z0-9._-]*)@(?P<hash>[0-9a-f]+)#(?P<locator>.+)$")
_SECTION = re.compile(r"^sec:(?P<path>[^/\s][^/]*(?:/[^/\s][^/]*)*)$")
_PARA = re.compile(r"^para:(?P<n>[1-9][0-9]*)$")
_REQ = re.compile(r"^req:(?P<keyword>[A-Z_]+):(?P<n>[1-9][0-9]*)$")


_LOOKS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*@[0-9a-fA-F]+#")


def looks_like(text: str) -> bool:
    """True when *text* is written in the address form (it may still be malformed)."""
    return bool(_LOOKS.match(text.strip()))


class Address(NamedTuple):
    key: str
    hash: str
    locator: str
    kind: str  # sec, para or req


class AddressError(ValueError):
    """The text is not a well-formed address."""


def parse(text: str) -> Address:
    match = _ADDRESS.match(text)
    if not match:
        raise AddressError(f"not an address: {text!r}")
    digest = match["hash"]
    if len(digest) < MIN_HASH or len(digest) > 64:
        raise AddressError(f"hash must be {MIN_HASH} to 64 hex characters: {text!r}")
    locator = match["locator"]
    for kind, pattern in (("sec", _SECTION), ("para", _PARA), ("req", _REQ)):
        found = pattern.match(locator)
        if found:
            if kind == "req" and found["keyword"] not in KEYWORDS:
                raise AddressError(f"unknown requirement keyword in {text!r}")
            return Address(match["key"], digest, locator, kind)
    raise AddressError(f"locator must be sec:, para: or req: form: {text!r}")


def resolve_prefix(prefix: str, hashes: list[str]) -> str:
    """Full hash for *prefix* among the stored *hashes*; ambiguous or unknown raises."""
    found = sorted({h for h in hashes if h.startswith(prefix)})
    if not found:
        raise AddressError(f"no stored hash starts with {prefix}")
    if len(found) > 1:
        raise AddressError(f"ambiguous hash prefix {prefix}: {', '.join(found)}")
    return found[0]
