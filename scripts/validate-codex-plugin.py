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
FORBIDDEN_COMPONENT_BASENAMES = frozenset(
    {
        ".app.json",
        ".mcp.json",
        "mcp.json",
        "hooks",
        "hooks.json",
        "connector",
        "connectors",
        "server",
        "servers",
    }
)

EXPECTED_MANIFEST_KEYS = {
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "skills",
    "interface",
}
EXPECTED_AUTHOR_KEYS = {"name", "url"}
EXPECTED_INTERFACE_KEYS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "defaultPrompt",
}
EXPECTED_PLUGIN_TOP_LEVEL = {
    ".codex-plugin",
    "NOTICE",
    "README.md",
    "README.ja.md",
    "README.zh-Hant.md",
    "skills",
}

EXPECTED_NAME = "agentic-change-audit"
EXPECTED_VERSION = "0.1.0-dev.2"
EXPECTED_DESCRIPTION = (
    "Evidence-first audits for AI-generated and human software changes "
    "before merge, release, or deployment."
)
EXPECTED_AUTHOR_NAME = "L&Co.LLC"
EXPECTED_AUTHOR_URL = "https://github.com/landco-llc"
EXPECTED_HOMEPAGE = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_REPOSITORY = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_KEYWORDS = [
    "ai-agents",
    "agent-skills",
    "software-audit",
    "change-audit",
    "code-review",
    "release-readiness",
]
EXPECTED_SKILLS_PATH = "./skills/"

EXPECTED_DISPLAY_NAME = "Agentic Change Audit"
EXPECTED_SHORT_DESCRIPTION = "Audit software changes with evidence before merge or release."
EXPECTED_LONG_DESCRIPTION = (
    "Review fixed software changes, verification evidence, remaining risks, "
    "and required human checks before merge, release, or deployment."
)
EXPECTED_DEVELOPER_NAME = "L&Co.LLC"
EXPECTED_CATEGORY = "Productivity"
EXPECTED_CAPABILITIES = ["Read"]
EXPECTED_WEBSITE_URL = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_DEFAULT_PROMPT = [
    "Audit the current repository change without modifying files. Fix the "
    "result to the current base and target HEAD.",
    "Audit this AI-built application as a release candidate and identify "
    "missing evidence and required human checks.",
    "Re-audit the approved remediation against the previous findings and "
    "authorized scope.",
]

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


def check_exact(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"plugin.json {label} must equal {expected!r}; found {actual!r}.")


def check_key_set(errors: list[str], label: str, actual: set[str], expected: set[str]) -> None:
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        errors.append(f"{label} keys mismatch; missing={missing}, extra={extra}")


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

    check_key_set(errors, "plugin.json top-level", set(manifest), EXPECTED_MANIFEST_KEYS)

    check_exact(errors, "name", manifest.get("name"), EXPECTED_NAME)
    check_exact(errors, "version", manifest.get("version"), EXPECTED_VERSION)
    try:
        validate_semver(EXPECTED_VERSION)
    except ValueError as exc:
        errors.append(str(exc))
    check_exact(errors, "description", manifest.get("description"), EXPECTED_DESCRIPTION)
    check_exact(errors, "homepage", manifest.get("homepage"), EXPECTED_HOMEPAGE)
    check_exact(errors, "repository", manifest.get("repository"), EXPECTED_REPOSITORY)
    check_exact(errors, "license", manifest.get("license"), EXPECTED_LICENSE)
    check_exact(errors, "skills", manifest.get("skills"), EXPECTED_SKILLS_PATH)
    check_exact(errors, "keywords", manifest.get("keywords"), EXPECTED_KEYWORDS)

    author = manifest.get("author")
    if not isinstance(author, dict):
        errors.append("plugin.json 'author' must be an object.")
    else:
        check_key_set(errors, "plugin.json author", set(author), EXPECTED_AUTHOR_KEYS)
        check_exact(errors, "author.name", author.get("name"), EXPECTED_AUTHOR_NAME)
        check_exact(errors, "author.url", author.get("url"), EXPECTED_AUTHOR_URL)

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json 'interface' must be an object.")
    else:
        check_key_set(errors, "plugin.json interface", set(interface), EXPECTED_INTERFACE_KEYS)
        check_exact(
            errors, "interface.displayName", interface.get("displayName"), EXPECTED_DISPLAY_NAME
        )
        check_exact(
            errors,
            "interface.shortDescription",
            interface.get("shortDescription"),
            EXPECTED_SHORT_DESCRIPTION,
        )
        check_exact(
            errors,
            "interface.longDescription",
            interface.get("longDescription"),
            EXPECTED_LONG_DESCRIPTION,
        )
        check_exact(
            errors, "interface.developerName", interface.get("developerName"), EXPECTED_DEVELOPER_NAME
        )
        check_exact(errors, "interface.category", interface.get("category"), EXPECTED_CATEGORY)
        check_exact(
            errors, "interface.capabilities", interface.get("capabilities"), EXPECTED_CAPABILITIES
        )
        check_exact(errors, "interface.websiteURL", interface.get("websiteURL"), EXPECTED_WEBSITE_URL)
        check_exact(
            errors, "interface.defaultPrompt", interface.get("defaultPrompt"), EXPECTED_DEFAULT_PROMPT
        )

    forbidden = contains_forbidden_keys(manifest, FORBIDDEN_MANIFEST_KEYS, "")
    for finding in forbidden:
        errors.append(f"plugin.json must not contain forbidden key: {finding}")

    visual = contains_forbidden_keys(manifest, FORBIDDEN_VISUAL_KEYS, "")
    for finding in visual:
        errors.append(f"plugin.json must not contain a visual asset field: {finding}")


def validate_plugin_tree_contract(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    if not plugin_root.is_dir():
        errors.append(f"Plugin root is missing: {plugin_root}")
        return

    top_level = {entry.name for entry in plugin_root.iterdir()}
    if top_level != EXPECTED_PLUGIN_TOP_LEVEL:
        missing = sorted(EXPECTED_PLUGIN_TOP_LEVEL - top_level)
        extra = sorted(top_level - EXPECTED_PLUGIN_TOP_LEVEL)
        errors.append(
            f"Plugin root top-level entries mismatch; missing={missing}, extra={extra}"
        )

    codex_plugin_dir = plugin_root / ".codex-plugin"
    if codex_plugin_dir.is_dir():
        entries = sorted(entry.name for entry in codex_plugin_dir.iterdir())
        if entries != ["plugin.json"]:
            errors.append(f".codex-plugin must contain only plugin.json; found: {entries}")
    else:
        errors.append(f".codex-plugin directory is missing: {codex_plugin_dir}")

    skills_dir = plugin_root / "skills"
    if skills_dir.is_dir():
        entries = sorted(entry.name for entry in skills_dir.iterdir())
        if entries != ["agentic-change-audit"]:
            errors.append(
                "skills/ must contain exactly one directory, agentic-change-audit; "
                f"found: {entries}"
            )
    else:
        errors.append(f"skills directory is missing: {skills_dir}")


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
        errors.append(f"marketplace.json 'name' must be {EXPECTED_MARKETPLACE_NAME!r}.")

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
    """Recursively reject forbidden basenames anywhere under the Plugin root.

    Uses os.walk with followlinks=False so a symlinked directory is never
    descended into; that condition is separately rejected by
    validate_no_symlinks.
    """
    plugin_root = root / PLUGIN_RELATIVE
    if not plugin_root.is_dir():
        errors.append(f"Plugin root is missing: {plugin_root}")
        return

    for current_dir, dir_names, file_names in os.walk(plugin_root, followlinks=False):
        current = Path(current_dir)
        for name in dir_names:
            if name in FORBIDDEN_COMPONENT_BASENAMES:
                errors.append(f"Forbidden component present: {current / name}")
        for name in file_names:
            if name in FORBIDDEN_COMPONENT_BASENAMES:
                errors.append(f"Forbidden component present: {current / name}")


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
    validate_plugin_tree_contract(root, errors)
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
    print(f"- Plugin NOTICE: {root / PLUGIN_RELATIVE / 'NOTICE'}")
    print("- MCP servers: none (recursive scan)")
    print("- Apps/connectors: none (recursive scan)")
    print("- Hooks: none (recursive scan)")
    print("- capabilities: Read only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
