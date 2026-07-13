#!/usr/bin/env python3
"""Validate an Agent Skills package without modifying it."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    import yaml
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
except ImportError as exc:  # pragma: no cover - exercised by user environments
    raise SystemExit(
        "PyYAML and markdown-it-py are required. Install validation "
        "dependencies with: python -m pip install -r requirements-validation.txt"
    ) from exc

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FULL_REFERENCE_PATTERN = re.compile(
    r"!?\[([^\]\n]+)\]\[([^\]\n]*)\]"
)
ASCII_PUNCTUATION = frozenset(
    "!\"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~"
)
KNOWN_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
MARKDOWN = MarkdownIt("commonmark")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate SKILL.md frontmatter, package naming, CommonMark file "
            "references, heading fragments, and project document pairs."
        )
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


def normalize_reference_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def iter_tokens(tokens: list[Token]):
    for token in tokens:
        yield token
        if token.children:
            yield from iter_tokens(token.children)


def inline_plain_text(token: Token) -> str:
    if not token.children:
        return token.content
    parts: list[str] = []
    for child in token.children:
        if child.type in {"text", "code_inline"}:
            parts.append(child.content)
        elif child.type == "image":
            parts.append(child.content)
    return "".join(parts)


def github_slug_base(text: str) -> str:
    value = html.unescape(text).strip().lower()
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"[^\w\-\s]", "", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "-", value)
    return value.strip("-")


def mask_non_live_inline_syntax(source: str) -> str:
    """Mask CommonMark code spans and backslash escapes in inline source."""
    masked = list(source)
    index = 0

    while index < len(source):
        if (
            source[index] == "\\"
            and index + 1 < len(source)
            and source[index + 1] in ASCII_PUNCTUATION
        ):
            masked[index] = " "
            masked[index + 1] = " "
            index += 2
            continue

        if source[index] != "`":
            index += 1
            continue

        opening_end = index
        while opening_end < len(source) and source[opening_end] == "`":
            opening_end += 1
        opening_length = opening_end - index

        cursor = opening_end
        closing_end: int | None = None
        while cursor < len(source):
            if source[cursor] != "`":
                cursor += 1
                continue

            run_end = cursor
            while run_end < len(source) and source[run_end] == "`":
                run_end += 1

            if run_end - cursor == opening_length:
                closing_end = run_end
                break
            cursor = run_end

        if closing_end is None:
            index = opening_end
            continue

        for position in range(index, closing_end):
            masked[position] = " "
        index = closing_end

    return "".join(masked)


def unresolved_reference_candidates(
    tokens: list[Token],
    reference_labels: set[str],
) -> list[str]:
    """Find unresolved full/collapsed references only in live inline source."""
    unresolved: list[str] = []

    for token in tokens:
        if token.type != "inline":
            continue

        live_source = mask_non_live_inline_syntax(token.content)
        for match in FULL_REFERENCE_PATTERN.finditer(live_source):
            visible_label, explicit_label = match.groups()
            lookup = explicit_label or visible_label
            if normalize_reference_label(lookup) not in reference_labels:
                start, end = match.span()
                unresolved.append(token.content[start:end])

    return unresolved


def markdown_analysis(text: str) -> tuple[list[str], set[str], list[str]]:
    env: dict[str, object] = {}
    tokens = MARKDOWN.parse(text, env)
    targets: list[str] = []
    anchors: set[str] = set()
    slug_counts: dict[str, int] = {}

    for token in iter_tokens(tokens):
        if token.type == "link_open":
            href = token.attrGet("href")
            if href:
                targets.append(href)
        elif token.type == "image":
            src = token.attrGet("src")
            if src:
                targets.append(src)

    for index, token in enumerate(tokens):
        if token.type != "heading_open" or index + 1 >= len(tokens):
            continue
        inline = tokens[index + 1]
        if inline.type != "inline":
            continue
        base = github_slug_base(inline_plain_text(inline))
        if not base:
            continue
        count = slug_counts.get(base, 0)
        slug_counts[base] = count + 1
        anchors.add(base if count == 0 else f"{base}-{count}")

    references = env.get("references")
    reference_labels = {
        normalize_reference_label(str(key))
        for key in references
    } if isinstance(references, dict) else set()

    unresolved = unresolved_reference_candidates(tokens, reference_labels)
    return targets, anchors, unresolved

def validate_markdown_references(
    root: Path,
    source: Path,
    text: str,
    anchor_cache: dict[Path, set[str]],
) -> list[str]:
    errors: list[str] = []
    root_resolved = root.resolve()
    targets, source_anchors, unresolved = markdown_analysis(text)
    anchor_cache[source.resolve()] = source_anchors

    for raw_reference in unresolved:
        errors.append(
            f"{source.relative_to(root)}: unresolved reference-style link: "
            f"{raw_reference}"
        )

    for raw_target in targets:
        target = raw_target.strip()
        parsed = urlparse(target)

        if parsed.scheme or parsed.netloc or target.startswith("//"):
            continue

        path_text = unquote(parsed.path)
        if path_text:
            candidate = (source.parent / path_text).resolve()
        else:
            candidate = source.resolve()

        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            errors.append(
                f"{source.relative_to(root)}: reference escapes the skill root: "
                f"{raw_target}"
            )
            continue

        if not candidate.exists():
            errors.append(
                f"{source.relative_to(root)}: referenced file does not exist: "
                f"{raw_target}"
            )
            continue

        fragment = unquote(parsed.fragment)
        if fragment and candidate.is_file() and candidate.suffix.lower() == ".md":
            target_anchors = anchor_cache.get(candidate)
            if target_anchors is None:
                target_text = candidate.read_text(encoding="utf-8")
                _, target_anchors, _ = markdown_analysis(target_text)
                anchor_cache[candidate] = target_anchors
            if fragment not in target_anchors:
                errors.append(
                    f"{source.relative_to(root)}: referenced Markdown heading "
                    f"does not exist: {raw_target}"
                )

    return errors


def validate_project_documentation(root: Path) -> list[str]:
    """Validate project-specific document pairs without claiming translation parity."""
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

    anchor_cache: dict[Path, set[str]] = {}
    for markdown_path in sorted(root.rglob("*.md")):
        if ".git" in markdown_path.parts:
            continue
        markdown_text = markdown_path.read_text(encoding="utf-8")
        errors.extend(
            validate_markdown_references(
                root,
                markdown_path,
                markdown_text,
                anchor_cache,
            )
        )

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
    print(
        "- CommonMark file/image/reference links and Markdown heading fragments: PASS"
    )
    print("- English/Japanese document pairs: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
