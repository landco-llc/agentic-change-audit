#!/usr/bin/env python3
"""Validate an Agent Skills package without modifying it."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by user environments
    raise SystemExit(
        "PyYAML is required. Install a compatible version with: "
        "python -m pip install 'PyYAML>=6,<7'"
    ) from exc

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
KNOWN_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate SKILL.md frontmatter, package naming, and relative links."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Skill package root containing SKILL.md (default: current directory).",
    )
    parser.add_argument(
        "--expected-name",
        help="Expected skill name. Defaults to the package root directory name.",
    )
    return parser.parse_args()


def split_frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("SKILL.md must start with a YAML frontmatter delimiter (---).")

    try:
        closing_index = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValueError("SKILL.md is missing the closing frontmatter delimiter (---).") from exc

    frontmatter = "\n".join(lines[1:closing_index])
    body = "\n".join(lines[closing_index + 1 :]).strip()
    return frontmatter, body


def validate_relative_links(root: Path, source: Path, text: str) -> list[str]:
    errors: list[str] = []
    root_resolved = root.resolve()

    for raw_target in LINK_PATTERN.findall(text):
        target = raw_target.strip().strip("<>")
        parsed = urlparse(target)

        if parsed.scheme or target.startswith("#") or target.startswith("//"):
            continue

        path_text = unquote(parsed.path)
        if not path_text:
            continue

        candidate = (source.parent / path_text).resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            errors.append(f"{source.relative_to(root)}: link escapes the skill root: {raw_target}")
            continue

        if not candidate.exists():
            errors.append(f"{source.relative_to(root)}: referenced file does not exist: {raw_target}")

    return errors


def validate_project_documentation(root: Path) -> list[str]:
    """Validate project-specific English/Japanese document pairs and README basics."""
    errors: list[str] = []
    pairs = [
        ("README.md", "README.ja.md"),
        ("docs/product-definition.md", "docs/product-definition.ja.md"),
        ("standard/change-audit-standard.md", "standard/change-audit-standard.ja.md"),
        ("standard/verdict-criteria.md", "standard/verdict-criteria.ja.md"),
        ("standard/evidence-requirements.md", "standard/evidence-requirements.ja.md"),
        ("standard/audit-invalidation.md", "standard/audit-invalidation.ja.md"),
        ("standard/human-check-boundary.md", "standard/human-check-boundary.ja.md"),
    ]

    for english, japanese in pairs:
        if not (root / english).is_file():
            errors.append(f"Missing canonical English document: {english}")
        if not (root / japanese).is_file():
            errors.append(f"Missing official Japanese document: {japanese}")

    readme = root / "README.md"
    readme_ja = root / "README.ja.md"
    if readme.is_file() and readme_ja.is_file():
        english_text = readme.read_text(encoding="utf-8")
        japanese_text = readme_ja.read_text(encoding="utf-8")
        if "[日本語](README.ja.md)" not in english_text:
            errors.append("README.md must link to README.ja.md.")
        if "[English](README.md)" not in japanese_text:
            errors.append("README.ja.md must link to README.md.")

        verdicts = [
            "PASS",
            "PASS WITH COMMENTS",
            "CHANGES REQUESTED",
            "BLOCKED",
            "NOT AUDITABLE",
        ]
        for verdict in verdicts:
            if verdict not in english_text:
                errors.append(f"README.md is missing verdict: {verdict}")
            if verdict not in japanese_text:
                errors.append(f"README.ja.md is missing verdict: {verdict}")

    return errors


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().absolute()
    skill_path = root / "SKILL.md"
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        print(f"ERROR: Skill root is not a directory: {root}", file=sys.stderr)
        return 1
    if not skill_path.is_file():
        print(f"ERROR: Missing SKILL.md at: {skill_path}", file=sys.stderr)
        return 1

    text = skill_path.read_text(encoding="utf-8")

    try:
        frontmatter_text, body = split_frontmatter(text)
        metadata = yaml.safe_load(frontmatter_text)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not isinstance(metadata, dict):
        errors.append("YAML frontmatter must parse to a mapping.")
        metadata = {}

    unknown_fields = sorted(set(metadata) - KNOWN_FIELDS)
    if unknown_fields:
        warnings.append(
            "Unknown frontmatter field(s) are not validated by this script: "
            + ", ".join(unknown_fields)
        )

    name = metadata.get("name")
    if not isinstance(name, str):
        errors.append("Frontmatter 'name' must be a string.")
    else:
        if not 1 <= len(name) <= 64:
            errors.append("Frontmatter 'name' must be 1-64 characters.")
        if not NAME_PATTERN.fullmatch(name):
            errors.append(
                "Frontmatter 'name' must use lowercase letters, numbers, and single "
                "hyphens only; it must not start or end with a hyphen."
            )
        expected_name = args.expected_name or root.name
        if name != expected_name:
            errors.append(
                f"Frontmatter name '{name}' does not match package directory "
                f"name '{expected_name}'."
            )

    description = metadata.get("description")
    if not isinstance(description, str):
        errors.append("Frontmatter 'description' must be a string.")
    elif not 1 <= len(description.strip()) <= 1024:
        errors.append("Frontmatter 'description' must be 1-1024 characters.")

    license_value = metadata.get("license")
    if license_value is not None and (
        not isinstance(license_value, str) or not license_value.strip()
    ):
        errors.append("Optional frontmatter 'license' must be a non-empty string.")

    compatibility = metadata.get("compatibility")
    if compatibility is not None:
        if not isinstance(compatibility, str):
            errors.append("Optional frontmatter 'compatibility' must be a string.")
        elif not 1 <= len(compatibility.strip()) <= 500:
            errors.append("Frontmatter 'compatibility' must be 1-500 characters.")

    metadata_value = metadata.get("metadata")
    if metadata_value is not None:
        if not isinstance(metadata_value, dict):
            errors.append("Optional frontmatter 'metadata' must be a mapping.")
        else:
            for key, value in metadata_value.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    errors.append("All 'metadata' keys and values must be strings.")
                    break

    allowed_tools = metadata.get("allowed-tools")
    if allowed_tools is not None and not isinstance(allowed_tools, str):
        errors.append("Optional frontmatter 'allowed-tools' must be a string.")

    if not body:
        errors.append("SKILL.md must contain a non-empty Markdown body.")

    line_count = len(text.splitlines())
    if line_count > 500:
        errors.append(f"SKILL.md has {line_count} lines; keep it at or below 500 lines.")

    for markdown_path in sorted(root.rglob("*.md")):
        if ".git" in markdown_path.parts:
            continue
        markdown_text = markdown_path.read_text(encoding="utf-8")
        errors.extend(validate_relative_links(root, markdown_path, markdown_text))

    errors.extend(validate_project_documentation(root))

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Skill validation: FAIL ({len(errors)} error(s))", file=sys.stderr)
        return 1

    print(f"Skill validation: PASS ({skill_path})")
    print(f"- name: {name}")
    print(f"- description length: {len(description.strip())}")
    print(f"- SKILL.md lines: {line_count}")
    print("- repository Markdown links: PASS")
    print("- English/Japanese document pairs: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
