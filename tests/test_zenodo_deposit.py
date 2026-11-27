"""The Zenodo deposit keeps the PDF and the DOCX as separate files (decision 0086)."""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "zenodo_deposit", ROOT / "scripts" / "zenodo_deposit.py"
)
zd = importlib.util.module_from_spec(spec)
sys.modules["zenodo_deposit"] = zd
spec.loader.exec_module(zd)

TOKEN = "tok-secret-123"
BASE = "https://zenodo.org/api"
ZENODO_JSON = {
    "title": "A paper",
    "upload_type": "publication",
    "publication_type": "preprint",
    "description": "Abstract.",
    "creators": [{"name": "Author, A."}],
    "license": "cc-by-4.0",
    "access_right": "open",
    "version": "1.2.3",
    "not_a_zenodo_key": "dropped",
}


def make_snapshot(tmp_path: Path) -> Path:
    snap = tmp_path / "snap"
    (snap / "paper").mkdir(parents=True)
    (snap / ".zenodo.json").write_text(json.dumps(ZENODO_JSON))
    (snap / "manuscript.pdf").write_bytes(b"%PDF-1.7 pdf bytes")
    (snap / "manuscript.docx").write_bytes(b"PK docx bytes")
    (snap / "README.md").write_text("readme")
    (snap / "paper" / "article.tex").write_text("tex")
    return snap


class FakeZenodo:
    """Just enough of the deposit API to see the calls in order."""

    def __init__(self, existing_files: tuple[str, ...] = ("old.pdf",)):
        self.calls: list[tuple[str, str]] = []
        self.uploads: dict[str, bytes] = {}
        self.metadata: dict | None = None
        self.headers: list[dict[str, str]] = []
        self.existing_files = existing_files

    def __call__(self, method, url, *, headers, body):
        self.calls.append((method, url))
        self.headers.append(headers)
        path = url.replace("https://zenodo.org", "")
        if method == "POST" and path == "/api/deposit/depositions":
            return 201, json.dumps(self._draft(7)).encode()
        if method == "POST" and path.endswith("/actions/newversion"):
            latest = f"{BASE}/deposit/depositions/9"
            return 201, json.dumps({"links": {"latest_draft": latest}}).encode()
        if method == "GET" and path == "/api/deposit/depositions/9":
            draft = self._draft(9)
            draft["files"] = [
                {"id": f"f{i}", "filename": n} for i, n in enumerate(self.existing_files)
            ]
            return 200, json.dumps(draft).encode()
        if method == "DELETE" and "/files/" in path:
            return 204, b""
        if method == "PUT" and path.startswith("/api/files/"):
            self.uploads[path.rsplit("/", 1)[1]] = body or b""
            return 201, b"{}"
        if method == "PUT" and path.startswith("/api/deposit/depositions/"):
            self.metadata = json.loads(body)["metadata"]
            return 200, b"{}"
        if method == "POST" and path.endswith("/actions/publish"):
            rid = path.split("/")[-3]
            return 202, json.dumps({
                "id": int(rid), "doi": f"10.5281/zenodo.{rid}", "conceptdoi": "10.5281/zenodo.1",
                "links": {"record_html": f"https://zenodo.org/records/{rid}"},
            }).encode()
        return 404, b'{"message": "unexpected"}'

    @staticmethod
    def _draft(rid: int) -> dict:
        return {
            "id": rid,
            "files": [],
            "links": {
                "self": f"{BASE}/deposit/depositions/{rid}",
                "bucket": f"{BASE}/files/bucket-{rid}",
            },
        }


def run_deposit(tmp_path, fake, *extra, token=TOKEN):
    out: list[str] = []
    env = {"ZENODO_TOKEN": token} if token else {}
    code = zd.run(
        ["--snapshot", str(make_snapshot(tmp_path)), "--tag", "v1.2.3",
         "--companion", "own/art.public", *extra],
        env=env, transport=fake, out=out.append,
    )
    return code, out


def test_artifacts_match_the_template() -> None:
    companion = ROOT / "{{cookiecutter.repo_name}}" / "scripts" / "article" / "companion.py"
    template = companion.read_text()
    m = re.search(r"^ARTIFACT_FILES = \(([^)]*)\)", template, re.M)
    assert tuple(re.findall(r'"([^"]+)"', m.group(1))) == zd.ARTIFACT_FILES


def test_new_concept_uploads_the_pdf_and_docx_as_separate_files(tmp_path) -> None:
    fake = FakeZenodo()
    code, out = run_deposit(tmp_path, fake)
    assert code == 0
    assert set(fake.uploads) == {"manuscript.pdf", "manuscript.docx", "art-v1.2.3-source.zip"}
    assert fake.uploads["manuscript.pdf"] == b"%PDF-1.7 pdf bytes"
    assert fake.uploads["manuscript.docx"] == b"PK docx bytes"
    assert [c[0] for c in fake.calls][:1] == ["POST"]
    assert fake.calls[-1][1].endswith("/actions/publish")
    result = json.loads(out[-1])
    assert result["doi"] == "10.5281/zenodo.7" and result["record_id"] == "7"


def test_source_archive_has_the_rest_and_not_the_artifacts(tmp_path) -> None:
    fake = FakeZenodo()
    run_deposit(tmp_path, fake)
    names = zipfile.ZipFile(io.BytesIO(fake.uploads["art-v1.2.3-source.zip"])).namelist()
    assert "art-v1.2.3/paper/article.tex" in names and "art-v1.2.3/.zenodo.json" in names
    assert not any(n.endswith(("manuscript.pdf", "manuscript.docx")) for n in names)


def test_source_archive_is_reproducible(tmp_path) -> None:
    snap = make_snapshot(tmp_path)
    assert zd.source_archive(snap, "x") == zd.source_archive(snap, "x")


def test_metadata_is_filtered_and_linked_to_the_tag(tmp_path) -> None:
    fake = FakeZenodo()
    run_deposit(tmp_path, fake)
    assert "not_a_zenodo_key" not in fake.metadata
    assert fake.metadata["version"] == "1.2.3"
    assert {"identifier": "https://github.com/own/art.public/tree/v1.2.3",
            "relation": "isSupplementTo", "scheme": "url"} in fake.metadata["related_identifiers"]


def test_new_version_replaces_the_old_files(tmp_path) -> None:
    fake = FakeZenodo(existing_files=("old.pdf", "old.zip"))
    code, out = run_deposit(tmp_path, fake, "--previous-record", "5")
    assert code == 0
    assert fake.calls[0][1].endswith("/deposit/depositions/5/actions/newversion")
    assert sum(1 for m, _ in fake.calls if m == "DELETE") == 2
    assert json.loads(out[-1])["record_id"] == "9"


def test_token_is_only_in_the_authorization_header(tmp_path) -> None:
    fake = FakeZenodo()
    run_deposit(tmp_path, fake)
    assert all(TOKEN not in url for _, url in fake.calls)
    assert all(h["Authorization"] == f"Bearer {TOKEN}" for h in fake.headers)


def test_dry_run_makes_no_request_and_needs_no_token(tmp_path) -> None:
    fake = FakeZenodo()
    code, out = run_deposit(tmp_path, fake, "--dry-run", token="")
    assert code == 0 and fake.calls == []
    names = {f["name"] for f in json.loads("".join(out))["files"]}
    assert names >= {"manuscript.pdf", "manuscript.docx"}


def test_missing_token_fails_before_any_request(tmp_path) -> None:
    fake = FakeZenodo()
    with pytest.raises(zd.ZenodoError, match="ZENODO_TOKEN"):
        run_deposit(tmp_path, fake, token="")
    assert fake.calls == []


@pytest.mark.parametrize("base", [
    "http://zenodo.org/api", "https://evil.example/api", "https://zenodo.org.evil.example/api",
    "https://user:pw@zenodo.org/api", "https://zenodo.org:8443/api",
])
def test_only_zenodo_hosts_over_https_are_allowed(base) -> None:
    with pytest.raises(zd.ZenodoError):
        zd.check_base_url(base)


def test_sandbox_is_allowed() -> None:
    assert zd.check_base_url("https://sandbox.zenodo.org/api") == "https://sandbox.zenodo.org/api"


def test_requests_outside_the_api_are_refused() -> None:
    client = zd.Client(BASE, TOKEN, FakeZenodo())
    with pytest.raises(zd.ZenodoError, match="outside"):
        client.call("GET", "https://evil.example/x")


def test_error_text_never_holds_the_token() -> None:
    def failing(method, url, *, headers, body):
        return 500, f"boom {TOKEN}".encode()
    client = zd.Client(BASE, TOKEN, failing)
    with pytest.raises(zd.ZenodoError) as err:
        client.call("GET", f"{BASE}/x")
    assert TOKEN not in str(err.value)


@pytest.mark.parametrize("tag", ["v1.2", "1.2.3", "v1.2.3-rc1", "v1.2.3; rm -rf"])
def test_only_final_tags_are_deposited(tmp_path, tag) -> None:
    with pytest.raises(zd.ZenodoError, match="final"):
        zd.run(
            ["--snapshot", str(make_snapshot(tmp_path)), "--tag", tag,
             "--companion", "o/n", "--dry-run"],
            env={}, transport=FakeZenodo(), out=lambda s: None,
        )


def test_a_snapshot_without_a_pdf_is_refused(tmp_path) -> None:
    snap = make_snapshot(tmp_path)
    (snap / "manuscript.pdf").unlink()
    with pytest.raises(zd.ZenodoError, match="manuscript.pdf"):
        zd.collect_files(snap, "x")
