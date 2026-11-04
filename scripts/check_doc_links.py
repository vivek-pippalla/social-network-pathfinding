"""Validate local markdown file links and section anchors.

Scans markdown documents for broken relative file links and internal headers
without performing network requests.
"""

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKDOWN_FILES = (
    "README.md",
    "SECURITY.md",
    "docs/API.md",
    "docs/DATABASE.md",
    "docs/DEPENDENCY_AUDIT.md",
    "docs/DEPLOYMENT.md",
    "docs/DEVELOPMENT.md",
    "docs/IMPLEMENTATION_STATUS.md",
    "docs/TESTING.md",
)

LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def slugify_heading(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[\s_]+", "-", cleaned)


def extract_headings(content: str) -> set[str]:
    headings = set()
    for match in HEADING_PATTERN.finditer(content):
        heading_text = match.group(2).strip()
        headings.add(slugify_heading(heading_text))
    return headings


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def check_file(file_path: Path, scanned_files: dict[Path, str]) -> list[str]:
    errors = []
    content = scanned_files.get(file_path)
    if content is None:
        content = file_path.read_text(encoding="utf-8")
        scanned_files[file_path] = content

    headings_cache: dict[Path, set[str]] = {}

    for line_no, line in enumerate(content.splitlines(), start=1):
        for match in LINK_PATTERN.finditer(line):
            link_target = match.group(2).strip()

            # Ignore external URLs, mailto, and javascript
            if (
                link_target.startswith(("http://", "https://", "mailto:", "tel:"))
                or link_target == ""
            ):
                continue

            # Separate path and anchor
            if "#" in link_target:
                target_path_str, anchor = link_target.split("#", 1)
            else:
                target_path_str, anchor = link_target, None

            # Determine target file
            if target_path_str:
                target_file = (file_path.parent / target_path_str).resolve()
            else:
                target_file = file_path.resolve()

            # Check target file existence
            if not target_file.exists():
                errors.append(
                    f"{display_path(file_path)}:{line_no}: Broken link '{link_target}' -> File not found: {display_path(target_file)}"
                )
                continue

            # Check anchor if target is a markdown file
            if anchor and target_file.suffix.lower() == ".md":
                if target_file not in headings_cache:
                    target_content = scanned_files.get(target_file)
                    if target_content is None:
                        target_content = target_file.read_text(encoding="utf-8")
                        scanned_files[target_file] = target_content
                    headings_cache[target_file] = extract_headings(target_content)

                expected_anchor = anchor.lower().strip()
                if expected_anchor not in headings_cache[target_file]:
                    errors.append(
                        f"{display_path(file_path)}:{line_no}: Broken anchor in '{link_target}' -> Anchor '#{anchor}' not found in {display_path(target_file)}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify local links and anchors in Markdown files."
    )
    parser.add_argument("files", nargs="*", type=Path, help="Markdown files to verify")
    args = parser.parse_args()

    if args.files:
        files = [p.resolve() for p in args.files if p.exists() and p.suffix == ".md"]
    else:
        files = [
            (ROOT / relative_path).resolve()
            for relative_path in DEFAULT_MARKDOWN_FILES
            if (ROOT / relative_path).is_file()
        ]

    scanned_files: dict[Path, str] = {}
    all_errors = []

    for file_path in files:
        if not file_path.exists():
            continue
        errors = check_file(file_path, scanned_files)
        all_errors.extend(errors)

    if all_errors:
        print("ERROR: Documentation link checker found broken links:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(
        f"Documentation link checker: verified local links across {len(files)} files successfully."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
