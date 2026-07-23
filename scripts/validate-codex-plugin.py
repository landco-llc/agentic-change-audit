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
EXPECTED_VERSION = "0.1.0-dev.3"
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

EXPECTED_MARKETPLACE_NAME = "agentic-change-audit"
EXPECTED_MARKETPLACE_DISPLAY_NAME = "Agentic Change Audit"
EXPECTED_MARKETPLACE_ENTRY_NAME = "agentic-change-audit"
EXPECTED_MARKETPLACE_SOURCE_TYPE = "local"
EXPECTED_MARKETPLACE_SOURCE_PATH = "./plugins/agentic-change-audit"
EXPECTED_MARKETPLACE_INSTALLATION_POLICY = "AVAILABLE"
EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY = "ON_INSTALL"
EXPECTED_MARKETPLACE_CATEGORY = "Productivity"
EXPECTED_MARKETPLACE_KEYS = {"name", "interface", "plugins"}
EXPECTED_MARKETPLACE_INTERFACE_KEYS = {"displayName"}
EXPECTED_MARKETPLACE_ENTRY_KEYS = {"name", "source", "policy", "category"}
EXPECTED_MARKETPLACE_SOURCE_KEYS = {"source", "path"}
EXPECTED_MARKETPLACE_POLICY_KEYS = {"installation", "authentication"}

FORBIDDEN_HUMAN_IDENTITY_FRAGMENTS = ("landco-llc", "l&co")
STALE_README_MARKERS = (
    "landco-llc-open-source",
    "L&Co.LLC Open Source",
    "L&Co. Open Source",
    "0.1.0-dev.2",
)
REQUIRED_README_MARKERS = (
    "Agentic Change Audit marketplace",
    EXPECTED_VERSION,
)

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
PLUGIN_DEVELOPMENT_VERSION_PATTERN = re.compile(
    r"(?<![0-9A-Za-z])"
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"-dev\.(?:0|[1-9][0-9]*)(?:[.-][0-9A-Za-z-]+)*"
    r"(?![0-9A-Za-z-])",
    re.IGNORECASE,
)
README_CLAUSE_SPLIT_PATTERN = re.compile(
    r"(?:[!?。！？;；]+|\.(?=\s|$))",
    re.IGNORECASE,
)
README_MARKDOWN_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\([^\n)]*\)")
README_MARKDOWN_LINE_PREFIX_PATTERN = re.compile(
    r"(?m)^\s{0,3}(?:#{1,6}\s+|>\s?|[-+*]\s+|\d+[.)]\s+)"
)
README_MAX_CLAIM_WINDOW = 720
README_GATE_CONTEXT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])phase\s*c(?![A-Za-z0-9])|desktop\s+gate|"
    r"neutral[- ]marketplace identity|"
    r"neutral identity|中立(?:な)?\s*marketplace\s*identity|"
    r"中性\s*marketplace\s*identity|桌面\s*gate|"
    r"(?:renamed|current)\s+(?:agentic change audit\s+)?marketplace|"
    r"名称変更後の?\s*agentic change audit\s*marketplace|"
    r"(?:更名後|目前|現行|現在)\s*(?:的)?\s*marketplace",
    re.IGNORECASE,
)
README_VERIFIED_ACTION_PATTERN = re.compile(
    r"marketplace(?:\s+(?:registration|discovery|install(?:ation)?))?|"
    r"\b(?:desktop|registration|discovery|install(?:ation)?|invocation|"
    r"explicit invocation|working[- ]tree(?: non-mutation)?)\b|"
    r"marketplace登録|marketplaceの?登録|登録|発見|install|インストール|"
    r"明示呼び出し|明示的?呼び出し|working\s*tree[^。.!?\n]{0,24}非変更|"
    r"marketplace\s*註冊|探索|安裝|明確呼叫|明確叫用|"
    r"工作樹[^。.!?\n]{0,24}未變更",
    re.IGNORECASE,
)
README_CURRENT_IDENTITY_CUE_PATTERN = re.compile(
    rf"{re.escape(EXPECTED_VERSION)}|neutral[- ]marketplace identity|"
    r"neutral identity|renamed|current|now|agentic change audit marketplace|"
    r"現行|現在|名称変更後|中立|中性\s*marketplace\s*identity|"
    r"更名後|目前|現已",
    re.IGNORECASE,
)
README_POSITIVE_GATE_STATUS_PATTERN = re.compile(
    r"\b(?:pass(?:ed|es|ing)?|complet(?:e|ed)|verif(?:y|ies|ied|ication complete)|"
    r"validat(?:ed|ion complete)|approv(?:ed|al complete)|"
    r"success(?:ful|fully)?|succeed(?:ed|s|ing)?|ready)\b|"
    r"合格(?:済み)?|完了(?:済み|しました)?|検証済み|確認済み|"
    r"承認済み|承認されました|成功(?:しました)?|"
    r"(?:已|現已)?(?:通過|完成|驗證|驗證完成|驗證完畢|核准|批准|成功)|"
    r"已獲核准",
    re.IGNORECASE,
)
README_STATUS_NEGATION_BEFORE_PATTERN = re.compile(
    r"(?:\b(?:not|never|no)\s+(?:been\s+)?|"
    r"\b(?:has|have|had|is|are|was|were|does|do|did|must|should|may)\s+"
    r"not\s+(?:have\s+|been\s+|be\s+)?|"
    r"\b(?:cannot|can't)\s+(?:be\s+)?|"
    r"(?:未|まだ|尚未|並未|不得|不可|不曾|不能|不)\s*)$",
    re.IGNORECASE,
)
README_STATUS_PENDING_AFTER_PATTERN = re.compile(
    r"^\s*(?:not\b|ではありません|ではない|ではなく|"
    r"していません|していない|しておらず|とはいえない|"
    r"並非|不代表|不表示|不保證)",
    re.IGNORECASE,
)
README_STATUS_NON_CURRENT_BEFORE_PATTERN = re.compile(
    r"\b(?:will|would|shall|must|should|may)\s+(?:later\s+)?"
    r"(?:be\s+)?(?:re[- ]?)?$|"
    r"\b(?:when|if|once|after)\b[^.!?。！？;；]{0,96}$|"
    r"(?:将来|今後|予定|再(?:検証|確認|実施|試験)|待ち)[^。！？;；]{0,48}$|"
    r"(?:須於未來|未來|將|重新|仍待)[^。！？;；]{0,48}$",
    re.IGNORECASE,
)
README_STATUS_NON_CURRENT_AFTER_PATTERN = re.compile(
    r"^\s*(?:in the future\b|later\b|when\b|if\b|予定|待ち|"
    r"未來|之後|稍後|仍待)",
    re.IGNORECASE,
)
README_NON_ASSERTION_CUE_PATTERN = re.compile(
    r"\b(?:does not|doesn't|do not|don't|did not|never)\s+"
    r"(?:assert|claim|state|represent|mean)\b|"
    r"\b(?:must|should|is expected to|is intended to)\s+"
    r"(?:reject|forbid|prohibit)\b|"
    r"\b(?:rejects?|forbids?|prohibits?)\s+(?:the\s+)?claim\b|"
    r"\b(?:forbidden|prohibited|invalid)\s+(?:wording|claim|example)\b|"
    r"\bnot\s+(?:the\s+)?current\s+state\b|\bis not a claim\b|"
    r"主張し(?:ない|ません)|意味し(?:ない|ません)|認め(?:ない|ません)|"
    r"拒否(?:する|される)|禁止(?:する|される)?|"
    r"現在(?:の)?状態を示し(?:ない|ません)|"
    r"並未主張|不主張|不代表|不表示目前狀態|並非目前狀態|"
    r"拒絕|禁止|不得主張",
    re.IGNORECASE,
)
README_FIXTURE_REPORTING_PATTERN = re.compile(
    r"\b(?:fixture|example|test case)\b[^.!?。！？;；]{0,64}"
    r"\b(?:may say|quotes?|contains?|describes?)\b|"
    r"fixture[^。！？;；]{0,64}(?:例|説明|記載)|"
    r"fixture[^。！？;；]{0,64}(?:範例|說法|描述)",
    re.IGNORECASE,
)
README_NON_ASSERTION_AFTER_PATTERN = re.compile(
    r"^\s*(?:without\s+(?:asserting|claiming)|"
    r"is\s+(?:forbidden|prohibited|invalid)|must\s+be\s+rejected|"
    r"(?:という)?主張をし(?:ない|ません)|禁止(?:される)?|拒否(?:される)?|"
    r"現在(?:の)?状態を示し(?:ない|ません)|"
    r"並未主張|不主張|禁止|拒絕|不表示目前狀態|不代表)",
    re.IGNORECASE,
)
README_CONTRAST_PATTERN = re.compile(
    r"\b(?:but|however|rather|instead|yet)\b|"
    r"(?:が|しかし|ではなく|一方|而是|但是|但|卻)",
    re.IGNORECASE,
)
README_INDEPENDENT_CLAIM_BOUNDARY_PATTERN = re.compile(
    r"[,，、]\s*(?:and|then|also|the\s+current|currently|"
    r"現在|現行|目前|並且|而且)\b",
    re.IGNORECASE,
)
README_TRAILING_NON_ASSERTION_LINK_PATTERN = re.compile(
    r"^\s*(?:だと|とは|という(?:文言|主張)?(?:は)?|を|的說法)?"
    r"\s*[,、，:]?\s*$",
    re.IGNORECASE,
)
README_HISTORICAL_CUE_PATTERN = re.compile(
    r"\b(?:earlier|previous|prior|old|historical)\b|以前|過去|旧|先前|舊",
    re.IGNORECASE,
)
README_INVALIDATION_CUE_PATTERN = re.compile(
    r"\b(?:superseded|invalid|expired|no longer valid|does not verify)\b|"
    r"失効|無効|検証するものではありません|已失效|失效|不能驗證",
    re.IGNORECASE,
)


class DuplicateJSONKeyError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise DuplicateJSONKeyError(key)
        document[key] = value
    return document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the skills-only Codex Plugin foundation."
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"File does not exist: {path}") from exc
    except DuplicateJSONKeyError as exc:
        raise ValueError(f"Duplicate JSON key in {path}: {exc.key!r}.") from exc
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


def iter_string_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_string_values(item)


def validate_company_neutral_value(errors: list[str], label: str, value: Any) -> None:
    """Reject company identity only in structurally human-facing fields.

    Legal identity and technical GitHub URL fields are validated separately and
    intentionally never passed to this function.
    """
    for text in iter_string_values(value):
        normalized = text.casefold()
        for fragment in FORBIDDEN_HUMAN_IDENTITY_FRAGMENTS:
            if fragment in normalized:
                errors.append(
                    f"{label} must remain company-neutral; found {fragment!r}."
                )


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
    actual_version = manifest.get("version")
    check_exact(errors, "version", actual_version, EXPECTED_VERSION)
    try:
        validate_semver(actual_version)
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

        for label, value in (
            ("plugin.json name", manifest.get("name")),
            ("plugin.json description", manifest.get("description")),
            ("plugin.json keywords", manifest.get("keywords")),
            ("plugin.json interface.displayName", interface.get("displayName")),
            ("plugin.json interface.shortDescription", interface.get("shortDescription")),
            ("plugin.json interface.longDescription", interface.get("longDescription")),
            ("plugin.json interface.defaultPrompt", interface.get("defaultPrompt")),
        ):
            validate_company_neutral_value(errors, label, value)

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

    check_key_set(
        errors,
        "marketplace.json top-level",
        set(marketplace),
        EXPECTED_MARKETPLACE_KEYS,
    )

    if marketplace.get("name") != EXPECTED_MARKETPLACE_NAME:
        errors.append(f"marketplace.json 'name' must be {EXPECTED_MARKETPLACE_NAME!r}.")
    validate_company_neutral_value(
        errors, "marketplace.json name", marketplace.get("name")
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
    if isinstance(interface, dict):
        check_key_set(
            errors,
            "marketplace.json interface",
            set(interface),
            EXPECTED_MARKETPLACE_INTERFACE_KEYS,
        )
        validate_company_neutral_value(
            errors,
            "marketplace.json interface.displayName",
            interface.get("displayName"),
        )

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        errors.append("marketplace.json 'plugins' must contain exactly one entry.")
        return

    entry = plugins[0]
    if not isinstance(entry, dict):
        errors.append("marketplace.json plugin entry must be an object.")
        return

    check_key_set(
        errors,
        "marketplace.json plugin entry",
        set(entry),
        EXPECTED_MARKETPLACE_ENTRY_KEYS,
    )

    if entry.get("name") != EXPECTED_MARKETPLACE_ENTRY_NAME:
        errors.append(
            f"marketplace.json entry 'name' must be {EXPECTED_MARKETPLACE_ENTRY_NAME!r}."
        )
    validate_company_neutral_value(
        errors, "marketplace.json entry name", entry.get("name")
    )

    source = entry.get("source")
    if not isinstance(source, dict):
        errors.append("marketplace.json entry 'source' must be an object.")
    else:
        check_key_set(
            errors,
            "marketplace.json plugin entry source",
            set(source),
            EXPECTED_MARKETPLACE_SOURCE_KEYS,
        )
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
        check_key_set(
            errors,
            "marketplace.json plugin entry policy",
            set(policy),
            EXPECTED_MARKETPLACE_POLICY_KEYS,
        )
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


def readme_claim_clauses(text: str) -> list[str]:
    visible = README_MARKDOWN_LINK_PATTERN.sub(r"\1", text)
    visible = README_MARKDOWN_LINE_PREFIX_PATTERN.sub("", visible)
    visible = re.sub(r"</?[^>\n]+>", " ", visible)
    visible = re.sub(r"[`*_~]", "", visible)
    # A Markdown soft/hard line break changes presentation, not claim meaning.
    visible = re.sub(r"[ \t]*\r?\n[ \t]*", " ", visible)
    return [
        " ".join(clause.split())
        for clause in README_CLAUSE_SPLIT_PATTERN.split(visible)
        if clause.strip()
    ]


def status_match_is_negated(clause: str, match: re.Match[str]) -> bool:
    before = clause[max(0, match.start() - 128) : match.start()]
    after = clause[match.end() : match.end() + 128]
    return bool(
        README_STATUS_NEGATION_BEFORE_PATTERN.search(before)
        or README_STATUS_PENDING_AFTER_PATTERN.search(after)
    )


def status_match_is_non_current(clause: str, match: re.Match[str]) -> bool:
    before = clause[max(0, match.start() - 128) : match.start()]
    after = clause[match.end() : match.end() + 128]
    return bool(
        README_STATUS_NON_CURRENT_BEFORE_PATTERN.search(before)
        or README_STATUS_NON_CURRENT_AFTER_PATTERN.search(after)
    )


def status_match_is_quoted(clause: str, match: re.Match[str]) -> bool:
    for opening, closing in (("\"", "\""), ("'", "'"), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』")):
        cursor = 0
        while True:
            start = clause.find(opening, cursor)
            if start < 0:
                break
            end = clause.find(closing, start + len(opening))
            if end < 0:
                break
            if start < match.start() and match.end() <= end:
                return True
            cursor = end + len(closing)
    return False


def status_match_is_non_assertive(clause: str, match: re.Match[str]) -> bool:
    before = clause[: match.start()]
    after = clause[match.end() :]

    for cue in README_NON_ASSERTION_CUE_PATTERN.finditer(before):
        governed_text = before[cue.end() :]
        if len(governed_text) <= 128 and not README_CONTRAST_PATTERN.search(
            governed_text
        ) and not README_INDEPENDENT_CLAIM_BOUNDARY_PATTERN.search(governed_text):
            return True

    for cue in README_NON_ASSERTION_CUE_PATTERN.finditer(after):
        governed_text = after[: cue.start()]
        if README_TRAILING_NON_ASSERTION_LINK_PATTERN.fullmatch(governed_text):
            return True

    if status_match_is_quoted(clause, match) and README_NON_ASSERTION_CUE_PATTERN.search(
        clause
    ):
        return True

    return bool(
        README_FIXTURE_REPORTING_PATTERN.search(before[-128:])
        and README_NON_ASSERTION_AFTER_PATTERN.search(after[:128])
    )


def status_match_is_allowed_historical(
    clause: str,
    match: re.Match[str],
) -> bool:
    return bool(
        README_HISTORICAL_CUE_PATTERN.search(clause[: match.start()])
        and README_INVALIDATION_CUE_PATTERN.search(clause[match.end() :])
    )


def readme_claim_window(
    clauses: list[str],
    index: int,
    match: re.Match[str],
) -> str:
    preceding = clauses[index - 1][-240:] if index else ""
    current = clauses[index][max(0, match.start() - 240) : match.end() + 240]
    following = clauses[index + 1][:240] if index + 1 < len(clauses) else ""
    window = " ; ".join(part for part in (preceding, current, following) if part)
    if len(window) <= README_MAX_CLAIM_WINDOW:
        return window
    current_offset = len(preceding) + 3 if preceding else 0
    current_start = max(0, match.start() - 240)
    center = current_offset + match.start() - current_start
    start = max(0, center - README_MAX_CLAIM_WINDOW // 2)
    return window[start : start + README_MAX_CLAIM_WINDOW]


def validate_readmes(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    for name in README_NAMES:
        candidate = plugin_root / name
        if not candidate.is_file() or candidate.stat().st_size == 0:
            errors.append(f"Plugin README is missing or empty: {candidate}")
            continue
        text = candidate.read_text(encoding="utf-8")
        for marker in STALE_README_MARKERS:
            if marker in text:
                errors.append(
                    f"Plugin README contains stale marketplace/version identity: "
                    f"{name}: {marker!r}"
                )
        for marker in REQUIRED_README_MARKERS:
            if marker not in text:
                errors.append(
                    f"Plugin README must record the current marketplace/version "
                    f"identity: {name}: {marker!r}"
                )

        for match in PLUGIN_DEVELOPMENT_VERSION_PATTERN.finditer(text):
            if match.group(0) != EXPECTED_VERSION:
                errors.append(
                    "Plugin README development-version mismatch: "
                    f"{name}: found {match.group(0)!r}; expected only "
                    f"{EXPECTED_VERSION!r}."
                )

        clauses = readme_claim_clauses(text)
        for index, clause in enumerate(clauses):
            for match in README_POSITIVE_GATE_STATUS_PATTERN.finditer(clause):
                window = readme_claim_window(clauses, index, match)
                has_gate_context = bool(README_GATE_CONTEXT_PATTERN.search(window))
                has_current_action_context = bool(
                    README_VERIFIED_ACTION_PATTERN.search(window)
                    and README_CURRENT_IDENTITY_CUE_PATTERN.search(window)
                )
                if not (has_gate_context or has_current_action_context):
                    continue
                if status_match_is_negated(
                    clause, match
                ) or status_match_is_non_current(
                    clause, match
                ) or status_match_is_non_assertive(
                    clause, match
                ) or status_match_is_allowed_historical(clause, match):
                    continue
                errors.append(
                    "Plugin README Phase C identity contradiction: "
                    f"{name}: {window!r}."
                )
                break


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
