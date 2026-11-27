#!/usr/bin/env python3
"""Deposit a companion snapshot on Zenodo as separate, uncompressed files.

Zenodo's GitHub integration archives only the repository's source zip, so the PDF and
the DOCX of a release end up inside it. This script deposits through Zenodo's REST API
instead: the PDF and the DOCX as their own files, plus one source archive of the rest
of the snapshot, with the metadata of the snapshot's `.zenodo.json`.

Standard library only, so the publish job installs nothing. The token comes from the
environment, travels only in the Authorization header to an allowlisted Zenodo host,
and is never printed. Redirects are refused so the header cannot be forwarded.

    ZENODO_TOKEN=... python3 scripts/zenodo_deposit.py \
        --snapshot snapshot --tag v1.2.3 --companion OWNER/NAME [--previous-record ID]

With `--previous-record` the deposit becomes a new version of that record's concept;
without it a new concept is created. `--dry-run` builds and prints the plan and makes
no request. The last stdout line is a JSON object with the record id and DOIs.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

ALLOWED_API_HOSTS = ("zenodo.org", "sandbox.zenodo.org")
DEFAULT_API = "https://zenodo.org/api"

# The release artifacts of an article repo; kept equal to ARTIFACT_FILES in the
# template's scripts/article/companion.py (a test compares them).
ARTIFACT_FILES = ("manuscript.pdf", "manuscript.docx")

# Metadata keys passed from .zenodo.json; anything else is dropped, not forwarded.
METADATA_KEYS = (
    "title",
    "upload_type",
    "publication_type",
    "description",
    "creators",
    "contributors",
    "keywords",
    "license",
    "access_right",
    "language",
    "notes",
    "references",
    "related_identifiers",
    "communities",
    "version",
    "subjects",
    "grants",
)

_ZIP_TIME = (2020, 1, 1, 0, 0, 0)  # fixed so the archive is reproducible


class ZenodoError(RuntimeError):
    """A failed request or an unusable input. Never carries the token."""


class Transport(Protocol):
    def __call__(
        self, method: str, url: str, *, headers: dict[str, str], body: bytes | None
    ) -> tuple[int, bytes]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        return None


def https_transport(
    method: str, url: str, *, headers: dict[str, str], body: bytes | None
) -> tuple[int, bytes]:
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with opener.open(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def check_base_url(base: str) -> str:
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_API_HOSTS:
        raise ZenodoError(f"API host is not allowed: {parsed.hostname or '(none)'}")
    if parsed.port not in (None, 443) or parsed.username or parsed.password:
        raise ZenodoError("API URL must be a plain https URL on port 443")
    return base.rstrip("/")


class Client:
    def __init__(self, base: str, token: str, transport: Transport = https_transport):
        self.base = check_base_url(base)
        self._token = token
        self._transport = transport

    def call(
        self,
        method: str,
        url: str,
        *,
        payload: Any = None,
        raw: bytes | None = None,
        expect: tuple[int, ...] = (200, 201, 202, 204),
    ) -> Any:
        if not url.startswith(self.base + "/") and not url.startswith(
            self.base.rsplit("/api", 1)[0] + "/"
        ):
            raise ZenodoError("refusing a request outside the Zenodo API")
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        body = raw
        if payload is not None:
            body = json.dumps(payload).encode()
            headers["Content-Type"] = "application/json"
        elif raw is not None:
            headers["Content-Type"] = "application/octet-stream"
        status, data = self._transport(method, url, headers=headers, body=body)
        if status not in expect:
            detail = data[:300].decode("utf-8", "replace").replace(self._token, "***")
            raise ZenodoError(f"{method} {url.split('?')[0]} -> HTTP {status}: {detail}")
        if not data:
            return {}
        try:
            return json.loads(data)
        except ValueError:
            return {}


def build_metadata(snapshot: Path, tag: str, companion: str) -> dict[str, Any]:
    src = snapshot / ".zenodo.json"
    if not src.is_file():
        raise ZenodoError(".zenodo.json not found in the snapshot")
    data = json.loads(src.read_text(encoding="utf-8"))
    meta = {k: data[k] for k in METADATA_KEYS if k in data}
    for required in ("title", "upload_type", "description", "creators"):
        if not meta.get(required):
            raise ZenodoError(f".zenodo.json has no {required}")
    meta["version"] = tag[1:] if tag.startswith("v") else tag
    release_url = f"https://github.com/{companion}/tree/{tag}"
    related = [
        r for r in meta.get("related_identifiers", []) if r.get("identifier") != release_url
    ]
    related.append({"identifier": release_url, "relation": "isSupplementTo", "scheme": "url"})
    meta["related_identifiers"] = related
    return meta


def source_archive(snapshot: Path, name: str) -> bytes:
    """One reproducible zip of the snapshot without the artifacts deposited separately."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in snapshot.rglob("*") if p.is_file()):
            rel = path.relative_to(snapshot)
            if len(rel.parts) == 1 and rel.name in ARTIFACT_FILES:
                continue
            info = zipfile.ZipInfo(f"{name}/{rel.as_posix()}", _ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
    return buf.getvalue()


def collect_files(snapshot: Path, name: str) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for artifact in ARTIFACT_FILES:
        path = snapshot / artifact
        if path.is_file():
            files.append((artifact, path.read_bytes()))
    if not any(n == "manuscript.pdf" for n, _ in files):
        raise ZenodoError("manuscript.pdf not found in the snapshot")
    files.append((f"{name}-source.zip", source_archive(snapshot, name)))
    return files


def deposit(
    client: Client,
    metadata: dict[str, Any],
    files: list[tuple[str, bytes]],
    previous_record: str | None,
) -> dict[str, str]:
    base = client.base
    if previous_record:
        created = client.call(
            "POST", f"{base}/deposit/depositions/{previous_record}/actions/newversion"
        )
        draft_url = created.get("links", {}).get("latest_draft")
        if not draft_url:
            raise ZenodoError("newversion returned no draft")
        draft = client.call("GET", draft_url)
        for old in draft.get("files", []):
            client.call("DELETE", f"{draft['links']['self']}/files/{old['id']}")
    else:
        draft = client.call("POST", f"{base}/deposit/depositions", payload={})
    bucket = draft["links"]["bucket"]
    for filename, content in files:
        client.call("PUT", f"{bucket}/{urllib.parse.quote(filename)}", raw=content)
    client.call("PUT", draft["links"]["self"], payload={"metadata": metadata})
    done = client.call("POST", f"{draft['links']['self']}/actions/publish", expect=(200, 201, 202))
    html = done.get("links", {}).get("record_html") or done.get("links", {}).get("html", "")
    return {
        "record_id": str(done.get("id", "")),
        "doi": str(done.get("doi", "")),
        "concept_doi": str(done.get("conceptdoi", "")),
        "html": html,
    }


def run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    transport: Transport = https_transport,
    out: Callable[[str], None] = print,
) -> int:
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--snapshot", required=True, type=Path)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--companion", required=True, help="OWNER/NAME of the public companion")
    ap.add_argument("--previous-record", help="record id of an earlier version")
    ap.add_argument("--base-url", default=env.get("ZENODO_API", DEFAULT_API))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", args.tag):
        raise ZenodoError("only a final vX.Y.Z tag is deposited")
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", args.companion):
        raise ZenodoError("bad companion name")
    if args.previous_record and not re.fullmatch(r"[0-9]+", args.previous_record):
        raise ZenodoError("bad record id")
    base = check_base_url(args.base_url)

    name = args.companion.split("/", 1)[1].removesuffix(".public")
    metadata = build_metadata(args.snapshot, args.tag, args.companion)
    files = collect_files(args.snapshot, f"{name}-{args.tag}")
    plan = {
        "api": base,
        "mode": "new version" if args.previous_record else "new concept",
        "files": [{"name": n, "bytes": len(c)} for n, c in files],
        "version": metadata["version"],
    }
    out(json.dumps(plan, indent=2))
    if args.dry_run:
        return 0
    token = env.get("ZENODO_TOKEN", "")
    if not token:
        raise ZenodoError("ZENODO_TOKEN is not set")
    result = deposit(Client(base, token, transport), metadata, files, args.previous_record)
    out(json.dumps(result))
    return 0


def main() -> int:
    try:
        return run(sys.argv[1:])
    except ZenodoError as exc:
        print(f"::error title=Zenodo deposit::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
