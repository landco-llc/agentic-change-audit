#!/usr/bin/env python3
"""Synchronize the bundled Codex Plugin Skill mirror with canonical sources."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path, PurePosixPath

CONFIG_RELATIVE = "release/distribution-files.json"
EXTRA_SOURCE = "guides/zh-Hant/installation.md"
PLUGIN_SKILL_RELATIVE = "plugins/agentic-change-audit/skills/agentic-change-audit"
EXPECTED_FILE_COUNT = 23


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize plugins/agentic-change-audit/skills/agentic-change-audit "
            "with the canonical repository-root Skill sources."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="Read-only: verify the mirror is an exact, byte-identical copy.",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="Recreate the mirror from canonical sources, then verify it.",
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--plugin-root",
        default=None,
        help="Plugin package root (default: <root>/plugins/agentic-change-audit).",
    )
    return parser.parse_args()


def validate_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Source file paths must be non-empty strings.")

    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Invalid source file path: {value}")
    if "\\" in value:
        raise ValueError(f"Source file paths must use POSIX separators: {value}")
    if any(part.startswith(".") for part in path.parts):
        raise ValueError(f"Hidden paths are not allowed in the Plugin mirror: {value}")
    return value


def load_source_list(root: Path) -> tuple[str, ...]:
    config_path = root / CONFIG_RELATIVE
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Distribution config does not exist: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {config_path}: {exc}") from exc

    files = data.get("files")
    if not isinstance(files, list):
        raise ValueError("Distribution config 'files' must be a list.")

    combined = [validate_relative_path(item) for item in files]
    combined.append(validate_relative_path(EXTRA_SOURCE))

    normalized = sorted(combined)
    if len(normalized) != len(set(normalized)):
        raise ValueError("Plugin source list contains duplicate paths.")
    if len(normalized) != EXPECTED_FILE_COUNT:
        raise ValueError(
            f"Plugin source list must contain exactly {EXPECTED_FILE_COUNT} paths; "
            f"found {len(normalized)}."
        )
    return tuple(normalized)


def resolve_plugin_skill_root(root: Path, plugin_root: Path | None) -> Path:
    if plugin_root is None:
        skill_root = root / PLUGIN_SKILL_RELATIVE
    else:
        skill_root = plugin_root / "skills" / "agentic-change-audit"

    resolved = skill_root.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"Plugin Skill mirror destination escapes the repository root: {resolved}"
        ) from exc

    if resolved.name != "agentic-change-audit" or resolved.parent.name != "skills":
        raise ValueError(
            "Plugin Skill mirror destination is not the expected "
            f".../skills/agentic-change-audit directory: {resolved}"
        )

    return resolved


def read_canonical_bytes(root: Path, relative: str) -> bytes:
    source = root / PurePosixPath(relative)
    if source.is_symlink():
        raise ValueError(f"Canonical source must not be a symlink: {relative}")
    if not source.is_file():
        raise ValueError(f"Canonical source file is missing: {relative}")

    root_resolved = root.resolve()
    resolved = source.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Canonical source escapes the repository root: {relative}") from exc

    data = source.read_bytes()
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Canonical source is not valid UTF-8: {relative}") from exc

    return data


def collect_mirror_entries(skill_root: Path) -> dict[str, Path]:
    entries: dict[str, Path] = {}
    if not skill_root.is_dir():
        return entries
    for path in sorted(skill_root.rglob("*")):
        if path.is_symlink():
            entries[path.relative_to(skill_root).as_posix()] = path
            continue
        if path.is_file():
            entries[path.relative_to(skill_root).as_posix()] = path
    return entries


def check_mirror(
    root: Path,
    skill_root: Path,
    sources: tuple[str, ...],
) -> list[str]:
    problems: list[str] = []
    actual = collect_mirror_entries(skill_root)
    expected = set(sources)

    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)

    for relative in missing:
        problems.append(f"missing: {relative}")
    for relative in extra:
        problems.append(f"extra: {relative}")

    for relative in sorted(expected & set(actual)):
        destination = actual[relative]
        if destination.is_symlink():
            problems.append(f"symlink not allowed: {relative}")
            continue
        canonical_bytes = read_canonical_bytes(root, relative)
        if destination.read_bytes() != canonical_bytes:
            problems.append(f"changed: {relative}")

    return problems


def write_mirror(root: Path, skill_root: Path, sources: tuple[str, ...]) -> None:
    if skill_root.exists() or skill_root.is_symlink():
        shutil.rmtree(skill_root)
    skill_root.mkdir(parents=True, exist_ok=False)

    for relative in sources:
        data = read_canonical_bytes(root, relative)
        destination = skill_root / PurePosixPath(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    plugin_root = (
        Path(args.plugin_root).expanduser().resolve() if args.plugin_root else None
    )

    try:
        sources = load_source_list(root)
        skill_root = resolve_plugin_skill_root(root, plugin_root)

        if args.write:
            write_mirror(root, skill_root, sources)

        problems = check_mirror(root, skill_root, sources)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        print(f"Plugin Skill mirror: FAIL ({len(problems)} issue(s))", file=sys.stderr)
        return 1

    mode = "write" if args.write else "check"
    print(f"Plugin Skill mirror ({mode}): PASS")
    print(f"- destination: {skill_root}")
    print(f"- files: {len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
