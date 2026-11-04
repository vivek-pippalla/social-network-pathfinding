"""Unit tests for the markdown documentation link checker."""

from pathlib import Path
import tempfile

from scripts.check_doc_links import (
    DEFAULT_MARKDOWN_FILES,
    check_file,
    extract_headings,
    slugify_heading,
)


def test_default_document_inventory_excludes_private_plan_and_agent_notes():
    assert "docs/BUILD_PLAN.md" not in DEFAULT_MARKDOWN_FILES
    assert "docs/AGENTS.md" not in DEFAULT_MARKDOWN_FILES
    assert "docs/ARCHITECTURE.md" not in DEFAULT_MARKDOWN_FILES
    assert "documentation/README.md" not in DEFAULT_MARKDOWN_FILES
    assert "docs/IMPLEMENTATION_STATUS.md" in DEFAULT_MARKDOWN_FILES


def test_slugify_heading():
    assert slugify_heading("Introduction & Overview") == "introduction-overview"
    assert slugify_heading("Quickstart: 5 Steps") == "quickstart-5-steps"
    assert slugify_heading("Section_With_Underscore") == "section-with-underscore"


def test_extract_headings():
    markdown = """# Title
## First Section
### Subsection A
## Second Section
"""
    headings = extract_headings(markdown)
    assert "title" in headings
    assert "first-section" in headings
    assert "subsection-a" in headings
    assert "second-section" in headings


def test_check_file_detects_broken_link_and_anchor():
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        doc_a = tmp_path / "doc_a.md"
        doc_b = tmp_path / "doc_b.md"

        doc_b.write_text("# Target Heading\n\nContent here.\n", encoding="utf-8")
        doc_a.write_text(
            "# Source\n\n"
            "[Valid](doc_b.md)\n"
            "[Valid with anchor](doc_b.md#target-heading)\n"
            "[Broken file](missing.md)\n"
            "[Broken anchor](doc_b.md#missing-heading)\n"
            "[External link](https://example.com/missing)\n",
            encoding="utf-8",
        )

        scanned = {}
        errors = check_file(doc_a, scanned)

        assert len(errors) == 2
        assert any("File not found" in err and "missing.md" in err for err in errors)
        assert any("Anchor '#missing-heading' not found" in err for err in errors)


def test_check_file_passes_when_all_links_valid():
    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        doc_a = tmp_path / "doc_a.md"
        doc_b = tmp_path / "doc_b.md"

        doc_b.write_text("# Heading One\n\n## Subheading\n", encoding="utf-8")
        doc_a.write_text(
            "# Source\n\n"
            "[To B](doc_b.md)\n"
            "[To Sub](doc_b.md#subheading)\n"
            "[To Self Anchor](#source)\n",
            encoding="utf-8",
        )

        scanned = {}
        errors = check_file(doc_a, scanned)
        assert not errors
