"""Step 0.1 contracts: ledger entry and source manifest schemas, address grammar, fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import sys

import jsonschema
import pytest
from conftest import ROOT

TEMPLATE = ROOT / "{{cookiecutter.repo_name}}"
FIXTURES = ROOT / "tests" / "fixtures" / "contracts"
sys.path.insert(0, str(TEMPLATE))

from scripts.article import address  # noqa: E402


def _schema(name: str) -> dict:
    return json.loads((TEMPLATE / "schemas" / name).read_text())


def _fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


LEDGER = _schema("ledger-entry.schema.json")
MANIFEST = _schema("sources-manifest.schema.json")


def test_fixtures_match_recorded_hashes():
    """scholar-mcp keeps byte-equal copies; this file is what both repos compare."""
    for line in (FIXTURES / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split()
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest, name


def test_schemas_are_valid_schemas():
    jsonschema.Draft7Validator.check_schema(LEDGER)
    jsonschema.Draft7Validator.check_schema(MANIFEST)


def test_ledger_entry_fixture_validates():
    jsonschema.validate(_fixture("ledger-entry.json"), LEDGER)


@pytest.mark.parametrize(
    "field", ["kind", "key", "key_version", "version", "tier", "tools", "inputs", "status"]
)
def test_ledger_entry_requires_field(field):
    entry = _fixture("ledger-entry.json")
    del entry[field]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entry, LEDGER)


@pytest.mark.parametrize("status", ["error", "unavailable", "stale"])
def test_ledger_entry_rejects_non_result_status(status):
    entry = _fixture("ledger-entry.json")
    entry["status"] = status
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entry, LEDGER)


def test_ledger_entry_rejects_timestamp_and_empty_inputs():
    entry = _fixture("ledger-entry.json")
    with_time = {**entry, "recorded": "2026-11-07T00:00:00Z"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(with_time, LEDGER)
    entry["inputs"] = {}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entry, LEDGER)


def test_manifest_fixture_validates():
    jsonschema.validate(_fixture("manifest.json"), MANIFEST)


@pytest.mark.parametrize(
    "field", ["key", "origin", "retrieved", "raw_hash", "media_type", "edition"]
)
def test_manifest_entry_requires_field(field):
    data = _fixture("manifest.json")
    del data["sources"][0][field]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, MANIFEST)


def test_manifest_normalized_hash_and_normalizer_go_together():
    data = _fixture("manifest.json")
    broken = copy.deepcopy(data)
    del broken["sources"][0]["normalizer"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(broken, MANIFEST)
    # An unreadable source has neither, and is still a valid entry.
    assert "normalized_hash" not in data["sources"][1]
    jsonschema.validate(data, MANIFEST)


# ---------------------------------------------------------------- address grammar


@pytest.mark.parametrize("case", _fixture("addresses.json")["valid"], ids=lambda c: c["kind"])
def test_valid_addresses_parse(case):
    parsed = address.parse(case["text"])
    assert parsed.kind == case["kind"]
    assert f"{parsed.key}@{parsed.hash}#{parsed.locator}" == case["text"]


@pytest.mark.parametrize("text", _fixture("addresses.json")["invalid"])
def test_invalid_addresses_are_rejected(text):
    with pytest.raises(address.AddressError):
        address.parse(text)


def test_section_locator_keeps_heading_path():
    parsed = address.parse(_fixture("addresses.json")["valid"][0]["text"])
    assert parsed.locator == "sec:Security Considerations/Threats"


def test_prefix_resolution():
    data = _fixture("addresses.json")["prefixes"]
    assert address.resolve_prefix(data["ok"], data["stored"]) == data["stored"][2]
    with pytest.raises(address.AddressError, match="ambiguous"):
        address.resolve_prefix(data["ambiguous"], data["stored"])
    with pytest.raises(address.AddressError, match="no stored hash"):
        address.resolve_prefix(data["unknown"], data["stored"])
