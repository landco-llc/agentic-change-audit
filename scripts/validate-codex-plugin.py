#!/usr/bin/env python3
"""Validate the skills-only Codex Plugin foundation without modifying it."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_RELATIVE = "plugins/agentic-change-audit"
MANIFEST_RELATIVE = f"{PLUGIN_RELATIVE}/.codex-plugin/plugin.json"
CODEX_PLUGIN_DIR_RELATIVE = f"{PLUGIN_RELATIVE}/.codex-plugin"
MARKETPLACE_RELATIVE = ".agents/plugins/marketplace.json"
SKILL_RELATIVE = f"{PLUGIN_RELATIVE}/skills/agentic-change-audit"
SYNC_SCRIPT_RELATIVE = "scripts/sync-codex-plugin.py"
SKILL_VALIDATOR_RELATIVE = "scripts/validate-skill.py"
README_NAMES = ("README.md", "README.ja.md", "README.zh-Hant.md")
FORBIDDEN_MANIFEST_KEYS = ("mcpServers", "apps", "hooks")
FORBIDDEN_VISUAL_KEYS = (
    "icon",
    "icons",
    "logo",
    "logoUrl",
    "assets",
    "screenshots",
    "banner",
)
EXPECTED_NAME = "agentic-change-audit"
EXPECTED_VERSION = "0.1.0-dev.1"
EXPECTED_SKILLS_PATH = "./skills/"
EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_CAPABILITIES = ["Read"]
EXPECTED_MARKETPLACE_NAME = "landco-llc-open-source"
EXPECTED_MARKETPLACE_DISPLAY_NAME = "L&Co.LLC Open Source"
EXPECTED_MARKETPLACE_ENTRY_NAME = "agentic-change-audit"
EXPECTED_MARKETPLACE_SOURCE_TYPE = "local"
EXPECTED_MARKETPLACE_SOURCE_PATH = "./plugins/agentic-change-audit"
EXPECTED_MARKETPLACE_INSTALLATION_POLICY = "AVAILABLE"
EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY = "ON_INSTALL"
EXPECTED_MARKETPLACE_CATEGORY = "Productivity"

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the skills-only Codex Plugin foundation."
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"File does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def validate_semver(value: str) -> None:
    if not isinstance(value, str) or not SEMVER_PATTERN.fullmatch(value):
        raise ValueError(f"Version is not valid ASCII SemVer: {value!r}")


def contains_forbidden_keys(value: Any, forbidden: tuple[str, ...], path: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if key in forbidden:
                found.append(f"{path}.{key}" if path else key)
            found.extend(contains_forbidden_keys(sub_value, forbidden, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(contains_forbidden_keys(item, forbidden, f"{path}[{index}]"))
    return found


def validate_manifest(root: Path, errors: list[str]) -> None:
    manifest_path = root / MANIFEST_RELATIVE
    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(manifest, dict):
        errors.append("plugin.json must be a JSON object.")
        return

    if manifest.get("name") != EXPECTED_NAME:
        errors.append(f"plugin.json 'name' must be {EXPECTED_NAME!r}.")

    version = manifest.get("version")
    if version != EXPECTED_VERSION:
        errors.append(f"plugin.json 'version' must be {EXPECTED_VERSION!r}.")
    else:
        try:
            validate_semver(version)
        except ValueError as exc:
            errors.append(str(exc))

    for key in ("description", "homepage", "repository"):
        if not isinstance(manifest.get(key), str) or not manifest.get(key):
            errors.append(f"plugin.json {key!r} must be a non-empty string.")

    if manifest.get("license") != EXPECTED_LICENSE:
        errors.append(f"plugin.json 'license' must be {EXPECTED_LICENSE!r}.")

    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name") or not author.get("url"):
        errors.append("plugin.json 'author' must include non-empty 'name' and 'url'.")

    keywords = manifest.get("keywords")
    if not isinstance(keywords, list) or not keywords or not all(
        isinstance(item, str) and item for item in keywords
    ):
        errors.append("plugin.json 'keywords' must be a non-empty list of strings.")

    if manifest.get("skills") != EXPECTED_SKILLS_PATH:
        errors.append(f"plugin.json 'skills' must be {EXPECTED_SKILLS_PATH!r}.")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json 'interface' must be an object.")
    else:
        for key in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "websiteURL",
        ):
            if not isinstance(interface.get(key), str) or not interface.get(key):
                errors.append(f"plugin.json interface.{key} must be a non-empty string.")

        capabilities = interface.get("capabilities")
        if capabilities != EXPECTED_CAPABILITIES:
            errors.append(
                f"plugin.json interface.capabilities must equal {EXPECTED_CAPABILITIES!r}."
            )

        default_prompt = interface.get("defaultPrompt")
        if not isinstance(default_prompt, list) or not default_prompt or not all(
            isinstance(item, str) and item for item in default_prompt
        ):
            errors.append(
                "plugin.json interface.defaultPrompt must be a non-empty list of strings."
            )

    forbidden = contains_forbidden_keys(manifest, FORBIDDEN_MANIFEST_KEYS, "")
    for finding in forbidden:
        errors.append(f"plugin.json must not contain forbidden key: {finding}")

    visual = contains_forbidden_keys(manifest, FORBIDDEN_VISUAL_KEYS, "")
    for finding in visual:
        errors.append(f"plugin.json must not contain a visual asset field: {finding}")


def validate_codex_plugin_dir(root: Path, errors: list[str]) -> None:
    directory = root / CODEX_PLUGIN_DIR_RELATIVE
    if not directory.is_dir():
        errors.append(f".codex-plugin directory is missing: {directory}")
        return
    entries = sorted(entry.name for entry in directory.iterdir())
    if entries != ["plugin.json"]:
        errors.append(
            f".codex-plugin must contain only plugin.json; found: {entries}"
        )


def validate_marketplace(root: Path, errors: list[str]) -> None:
    marketplace_path = root / MARKETPLACE_RELATIVE
    try:
        marketplace = load_json(marketplace_path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(marketplace, dict):
        errors.append("marketplace.json must be a JSON object.")
        return

    if marketplace.get("name") != EXPECTED_MARKETPLACE_NAME:
        errors.append(
            f"marketplace.json 'name' must be {EXPECTED_MARKETPLACE_NAME!r}."
        )

    interface = marketplace.get("interface")
    if (
        not isinstance(interface, dict)
        or interface.get("displayName") != EXPECTED_MARKETPLACE_DISPLAY_NAME
    ):
        errors.append(
            "marketplace.json interface.displayName must be "
            f"{EXPECTED_MARKETPLACE_DISPLAY_NAME!r}."
        )

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        errors.append("marketplace.json 'plugins' must contain exactly one entry.")
        return

    entry = plugins[0]
    if not isinstance(entry, dict):
        errors.append("marketplace.json plugin entry must be an object.")
        return

    if entry.get("name") != EXPECTED_MARKETPLACE_ENTRY_NAME:
        errors.append(
            f"marketplace.json entry 'name' must be {EXPECTED_MARKETPLACE_ENTRY_NAME!r}."
        )

    source = entry.get("source")
    if not isinstance(source, dict):
        errors.append("marketplace.json entry 'source' must be an object.")
    else:
        if source.get("source") != EXPECTED_MARKETPLACE_SOURCE_TYPE:
            errors.append(
                "marketplace.json entry source.source must be "
                f"{EXPECTED_MARKETPLACE_SOURCE_TYPE!r}."
            )
        path_value = source.get("path")
        if path_value != EXPECTED_MARKETPLACE_SOURCE_PATH:
            errors.append(
                "marketplace.json entry source.path must be "
                f"{EXPECTED_MARKETPLACE_SOURCE_PATH!r}."
            )
        elif not path_value.startswith("./"):
            errors.append("marketplace.json entry source.path must begin with './'.")
        else:
            candidate = (root / path_value.removeprefix("./")).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    "marketplace.json entry source.path escapes the repository root."
                )

    policy = entry.get("policy")
    if not isinstance(policy, dict):
        errors.append("marketplace.json entry 'policy' must be an object.")
    else:
        if policy.get("installation") != EXPECTED_MARKETPLACE_INSTALLATION_POLICY:
            errors.append(
                "marketplace.json entry policy.installation must be "
                f"{EXPECTED_MARKETPLACE_INSTALLATION_POLICY!r}."
            )
        if policy.get("authentication") != EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY:
            errors.append(
                "marketplace.json entry policy.authentication must be "
                f"{EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY!r}."
            )

    if entry.get("category") != EXPECTED_MARKETPLACE_CATEGORY:
        errors.append(
            f"marketplace.json entry 'category' must be {EXPECTED_MARKETPLACE_CATEGORY!r}."
        )


def run_skill_validator(root: Path, errors: list[str]) -> None:
    skill_root = root / SKILL_RELATIVE
    validator = root / SKILL_VALIDATOR_RELATIVE
    if not validator.is_file():
        errors.append(f"Skill validator script is missing: {validator}")
        return

    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(skill_root),
            "--expected-name",
            EXPECTED_NAME,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("Bundled Plugin Skill failed validate-skill.py:")
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            errors.append(f"  {line}")


def run_mirror_check(root: Path, errors: list[str]) -> None:
    sync_script = root / SYNC_SCRIPT_RELATIVE
    if not sync_script.is_file():
        errors.append(f"Sync script is missing: {sync_script}")
        return

    result = subprocess.run(
        [sys.executable, str(sync_script), "--check", "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("Plugin Skill mirror check failed:")
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            errors.append(f"  {line}")


def validate_no_symlinks(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    if not plugin_root.is_dir():
        errors.append(f"Plugin root is missing: {plugin_root}")
        return

    for current_dir, dir_names, file_names in os.walk(plugin_root, followlinks=False):
        current = Path(current_dir)
        for name in dir_names + file_names:
            candidate = current / name
            if candidate.is_symlink():
                errors.append(
                    f"Symlink is not allowed in the Plugin directory: {candidate}"
                )


def validate_forbidden_components(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    for forbidden in (".app.json", ".mcp.json", "hooks"):
        candidate = plugin_root / forbidden
        if candidate.exists() or candidate.is_symlink():
            errors.append(f"Forbidden component present: {candidate}")


def validate_readmes(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    for name in README_NAMES:
        candidate = plugin_root / name
        if not candidate.is_file() or candidate.stat().st_size == 0:
            errors.append(f"Plugin README is missing or empty: {candidate}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    errors: list[str] = []

    validate_manifest(root, errors)
    validate_codex_plugin_dir(root, errors)
    validate_marketplace(root, errors)
    run_skill_validator(root, errors)
    run_mirror_check(root, errors)
    validate_no_symlinks(root, errors)
    validate_forbidden_components(root, errors)
    validate_readmes(root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Codex Plugin validation: FAIL ({len(errors)} issue(s))", file=sys.stderr)
        return 1

    print("Codex Plugin validation: PASS")
    print(f"- manifest: {root / MANIFEST_RELATIVE}")
    print(f"- marketplace: {root / MARKETPLACE_RELATIVE}")
    print(f"- bundled Skill: {root / SKILL_RELATIVE}")
    print("- MCP servers: none")
    print("- Apps: none")
    print("- Hooks: none")
    print("- capabilities: Read only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
