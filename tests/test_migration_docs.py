"""Tests for the v1-to-v2 migration documentation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DOC = ROOT / "{{cookiecutter.repo_name}}" / "docs" / "migrating-to-v2.md"


def test_migration_doc_exists() -> None:
    """The migration guide must exist."""
    assert MIGRATION_DOC.is_file(), f"Missing migration guide: {MIGRATION_DOC}"


def test_migration_doc_has_required_sections() -> None:
    """The migration guide must contain all required sections."""
    content = MIGRATION_DOC.read_text()

    required_sections = [
        "Overview of Changes",
        "Field-by-Field Mapping",
        "Complete Before/After Example",
        "Migration Steps",
        "Why No Automated Migration Tool",
        "Verification Checklist",
        "Rollback Procedure",
        "Support",
    ]

    for section in required_sections:
        assert section in content, f"Missing required section: {section}"


def test_migration_doc_has_field_mapping_table() -> None:
    """The migration guide must have field mapping tables."""
    _ = MIGRATION_DOC.read_text()

    # The doc should mention these mappings
    assert "author_name" in MIGRATION_DOC.read_text()
    assert "author_orcid" in MIGRATION_DOC.read_text()
    assert "author_affiliation" in MIGRATION_DOC.read_text()


def test_migration_doc_has_before_after_example() -> None:
    """The migration guide must have a complete before/after example."""
    content = MIGRATION_DOC.read_text()

    # Check for v1 example
    assert "v1" in content or "legacy" in content.lower()
    assert "author_name:" in content
    assert "author_orcid:" in content
    assert "author_affiliation:" in content

    # Check for v2 example
    assert "authors:" in content
    assert "affiliations:" in content
    assert "manuscript_kind:" in content
    assert "citation_style:" in content
    assert "manuscript_kind:" in content


def test_migration_doc_has_migration_steps() -> None:
    """The migration guide must list manual migration steps."""
    content = MIGRATION_DOC.read_text()

    required_steps = [
        "Backup",
        "Create a new v2",
        "Validate",
        "Regenerate",
        "Verify",
        "Commit",
    ]

    for step in required_steps:
        assert step.lower() in content.lower(), f"Missing migration step: {step}"


def test_migration_doc_explains_no_tool() -> None:
    """The guide must explain why no automated tool exists."""
    content = MIGRATION_DOC.read_text()

    assert "no automated migration tool" in content.lower()
    assert "manual" in content.lower()
    assert "human" in content.lower()


def test_migration_doc_has_verification_checklist() -> None:
    """The migration guide must include a verification checklist."""
    content = MIGRATION_DOC.read_text()

    for check in ["validate", "metadata --check", "make pdf", "CITATION.cff",
                  ".zenodo.json", "README", "make pdf"]:
        assert check.lower() in content.lower(), f"Missing verification step: {check}"


def test_migration_doc_has_rollback_procedure() -> None:
    """The migration guide must include a rollback procedure."""
    content = MIGRATION_DOC.read_text()

    assert "Rollback" in content or "rollback" in content.lower()
    assert "backup" in content.lower()
    assert "git checkout" in content.lower()


def test_migration_doc_explicitly_states_no_tool() -> None:
    """The guide must explicitly state no migration tool exists and none is planned."""
    content = MIGRATION_DOC.read_text()

    assert "no automated migration tool" in content.lower()
    assert "none is planned" in content.lower()


def test_migration_doc_has_complete_example() -> None:
    """The migration guide must have a complete before/after example."""
    content = MIGRATION_DOC.read_text()

    # v1 example fields
    v1_fields = [
        "topic:", "repo_name:", "github_user:", "title:", "subtitle:",
        "manuscript_type:", "author_name:", "author_orcid:", "author_affiliation:",
        "version:", "version_label:", "date:", "license:", "target_deposit:",
        "doi:", "keywords:", "abstract:"
    ]

    for field in v1_fields:
        assert field in content, f"Missing v1 field in example: {field}"

    # v2 fields
    v2_fields = [
        "manuscript_kind:", "citation_style:", "authors:", "affiliations:",
        "affiliations:", "given:", "family:", "orcid:", "affiliations:"
    ]

    for field in v2_fields:
        assert field in content, f"Missing v2 field in example: {field}"


def test_migration_doc_mentions_validation_commands() -> None:
    """The guide must reference the validation commands."""
    content = MIGRATION_DOC.read_text()

    commands = [
        "scripts.article validate",
        "scripts.article metadata --check",
        "make pdf",
        "make validate",
        "make metadata",
    ]

    for cmd in commands:
        assert cmd in content, f"Missing command reference: {cmd}"

