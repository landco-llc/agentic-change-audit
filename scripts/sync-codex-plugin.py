#!/usr/bin/env python3
"""Synchronize the bundled Codex Plugin Skill mirror with canonical sources."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath

CONFIG_RELATIVE = "release/distribution-files.json"
EXTRA_SOURCE = "guides/zh-Hant/installation.md"
PLUGIN_SKILL_RELATIVE = "plugins/agentic-change-audit/skills/agentic-change-audit"
EXPECTED_FILE_COUNT = 23

# The exact, non-configurable destination-chain components that must be
# real (non-symlink) directories before any destructive operation. Checked
# lexically, shallowest first, before any path is resolved, so a symlink at
# any level is rejected instead of silently followed.
DESTINATION_CHAIN_RELATIVE = (
    "plugins",
    "plugins/agentic-change-audit",
    "plugins/agentic-change-audit/skills",
    "plugins/agentic-change-audit/skills/agentic-change-audit",
)


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


def derive_skill_root(root: Path) -> Path:
    """Return the one permitted Plugin Skill mirror destination under root.

    This is the only way to obtain a destination for destructive operations:
    there is no caller-supplied override. Every destination-chain component
    is checked with a lexical, non-following symlink test before the final
    path is used, so a symlink anywhere in the chain is rejected rather than
    resolved and silently followed.
    """
    for relative in DESTINATION_CHAIN_RELATIVE:
        candidate = root / PurePosixPath(relative)
        if candidate.is_symlink():
            raise ValueError(
                f"Plugin destination component must not be a symlink: {candidate}"
            )

    skill_root = root / PurePosixPath(PLUGIN_SKILL_RELATIVE)
    if skill_root.exists() and not skill_root.is_dir():
        raise ValueError(
            f"Plugin Skill mirror destination exists and is not a directory: {skill_root}"
        )
    return skill_root


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


def collect_mirror_entries(skill_root: Path) -> tuple[dict[str, Path], list[str]]:
    """Walk the mirror without following symlinks.

    Returns the regular-file entries found, plus a separate problem list for
    any symlinked file or directory encountered. A symlinked directory is not
    descended into, so nothing reached only through it is ever compared.
    """
    entries: dict[str, Path] = {}
    problems: list[str] = []
    if not skill_root.is_dir():
        return entries, problems

    for current_dir, dir_names, file_names in os.walk(skill_root, followlinks=False):
        current = Path(current_dir)
        for name in sorted(dir_names):
            candidate = current / name
            if candidate.is_symlink():
                relative = candidate.relative_to(skill_root).as_posix()
                problems.append(f"symlink not allowed: {relative}")
        for name in sorted(file_names):
            candidate = current / name
            relative = candidate.relative_to(skill_root).as_posix()
            if candidate.is_symlink():
                problems.append(f"symlink not allowed: {relative}")
                continue
            entries[relative] = candidate

    return entries, problems


def check_mirror(root: Path, sources: tuple[str, ...]) -> list[str]:
    skill_root = derive_skill_root(root)
    actual, problems = collect_mirror_entries(skill_root)
    expected = set(sources)

    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)

    for relative in missing:
        problems.append(f"missing: {relative}")
    for relative in extra:
        problems.append(f"extra: {relative}")

    for relative in sorted(expected & set(actual)):
        destination = actual[relative]
        canonical_bytes = read_canonical_bytes(root, relative)
        if destination.read_bytes() != canonical_bytes:
            problems.append(f"changed: {relative}")

    return problems


def write_mirror(root: Path, sources: tuple[str, ...]) -> None:
    skill_root = derive_skill_root(root)

    if skill_root.exists():
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

    try:
        sources = load_source_list(root)

        if args.write:
            write_mirror(root, sources)

        problems = check_mirror(root, sources)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        print(f"Plugin Skill mirror: FAIL ({len(problems)} issue(s))", file=sys.stderr)
        return 1

    mode = "write" if args.write else "check"
    skill_root = root / PurePosixPath(PLUGIN_SKILL_RELATIVE)
    print(f"Plugin Skill mirror ({mode}): PASS")
    print(f"- destination: {skill_root}")
    print(f"- files: {len(sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
