#!/usr/bin/env python3
"""Validate the Codex Plugin submission package without submitting anything.

The package is preparation material. This validator enforces that it stays
that way: exact listing contract, no overclaimed status, no leaked local
path, address, or secret, and an unchanged skills-only Plugin runtime.

This module itself uses the standard library only and makes no network
request. It does shell out to scripts/validate-codex-plugin.py, which needs
the repository's existing validation dependencies from
requirements-validation.txt.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SUPPORT_RELATIVE = "SUPPORT.md"
PRIVACY_RELATIVE = "PRIVACY.md"
SUBMISSION_RELATIVE = "submission/codex-plugin"
LISTING_RELATIVE = f"{SUBMISSION_RELATIVE}/listing.json"
STARTER_PROMPTS_RELATIVE = f"{SUBMISSION_RELATIVE}/starter-prompts.json"
TEST_CASES_RELATIVE = f"{SUBMISSION_RELATIVE}/test-cases.json"
AVAILABILITY_RELATIVE = f"{SUBMISSION_RELATIVE}/availability.json"
RELEASE_NOTES_RELATIVE = f"{SUBMISSION_RELATIVE}/release-notes.md"
HUMAN_PREREQUISITES_RELATIVE = f"{SUBMISSION_RELATIVE}/human-prerequisites.md"
VISUAL_ASSETS_RELATIVE = f"{SUBMISSION_RELATIVE}/visual-assets.md"
SUBMISSION_README_RELATIVE = f"{SUBMISSION_RELATIVE}/README.md"

PLUGIN_RELATIVE = "plugins/agentic-change-audit"
MANIFEST_RELATIVE = f"{PLUGIN_RELATIVE}/.codex-plugin/plugin.json"
PLUGIN_VALIDATOR_RELATIVE = "scripts/validate-codex-plugin.py"

PLUGIN_README_RELATIVE = f"{PLUGIN_RELATIVE}/README.md"
PLUGIN_README_JA_RELATIVE = f"{PLUGIN_RELATIVE}/README.ja.md"
PLUGIN_README_ZH_HANT_RELATIVE = f"{PLUGIN_RELATIVE}/README.zh-Hant.md"

# Files the submission package must provide.
REQUIRED_FILES = (
    SUPPORT_RELATIVE,
    PRIVACY_RELATIVE,
    SUBMISSION_README_RELATIVE,
    LISTING_RELATIVE,
    STARTER_PROMPTS_RELATIVE,
    TEST_CASES_RELATIVE,
    AVAILABILITY_RELATIVE,
    RELEASE_NOTES_RELATIVE,
    HUMAN_PREREQUISITES_RELATIVE,
    VISUAL_ASSETS_RELATIVE,
)

# Plugin-facing public content. These are not submission deliverables, but a
# reader reaches them from the listing, so they carry the same claim and
# leak boundaries and must exist.
PLUGIN_README_FILES = (
    PLUGIN_README_RELATIVE,
    PLUGIN_README_JA_RELATIVE,
    PLUGIN_README_ZH_HANT_RELATIVE,
)

# Files scanned for local paths, addresses, and secret-like values.
SCANNED_FILES = REQUIRED_FILES + PLUGIN_README_FILES

# Files scanned for product and submission status claims.
CLAIM_SCAN_FILES = (
    RELEASE_NOTES_RELATIVE,
    SUBMISSION_README_RELATIVE,
) + PLUGIN_README_FILES

EXPECTED_LISTING_KEYS = {
    "submissionType",
    "pluginName",
    "publisher",
    "shortDescription",
    "longDescription",
    "category",
    "websiteUrl",
    "supportUrl",
    "privacyUrl",
    "termsUrl",
    "developerIdentity",
    "logoStatus",
    "skills",
    "releaseStatus",
    "publicDirectoryStatus",
}
EXPECTED_DEVELOPER_IDENTITY_KEYS = {"type", "name", "verificationStatus"}
EXPECTED_SKILL_KEYS = {"name", "path"}

EXPECTED_SUBMISSION_TYPE = "skills-only"
EXPECTED_PLUGIN_NAME = "Agentic Change Audit"
EXPECTED_PUBLISHER = "L&Co.LLC"
EXPECTED_SHORT_DESCRIPTION = "Audit software changes with evidence before merge or release."
EXPECTED_LONG_DESCRIPTION = (
    "Agentic Change Audit reviews a fixed software change, records the checks "
    "and evidence actually available, identifies findings and required human "
    "checks, and returns one structured Verdict before merge, release, or "
    "deployment. It is evidence-first, agent-neutral, and read-only by default."
)
EXPECTED_CATEGORY = "Productivity"
EXPECTED_WEBSITE_URL = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_SUPPORT_URL = "https://github.com/landco-llc/agentic-change-audit/issues"
EXPECTED_PRIVACY_URL = (
    "https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md"
)
EXPECTED_TERMS_URL = "https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE"
EXPECTED_DEVELOPER_TYPE = "business"
EXPECTED_DEVELOPER_NAME = "L&Co.LLC"
EXPECTED_VERIFICATION_STATUS = "PENDING HUMAN CHECK"
EXPECTED_LOGO_STATUS = "PENDING APPROVED ASSET"
EXPECTED_SKILL_NAME = "agentic-change-audit"
EXPECTED_SKILL_PATH = "plugins/agentic-change-audit/skills/agentic-change-audit"
EXPECTED_RELEASE_STATUS = "draft-materials-only"
EXPECTED_PUBLIC_DIRECTORY_STATUS = "not-submitted"

URL_LISTING_KEYS = ("websiteUrl", "supportUrl", "privacyUrl", "termsUrl")

EXPECTED_AVAILABILITY_STATUS = "PENDING HUMAN DECISION"

STARTER_PROMPT_FIELDS = ("id", "title", "prompt", "expectedMode", "expectedBoundary")
TEST_CASE_FIELDS = (
    "id",
    "type",
    "title",
    "input",
    "preconditions",
    "expectedSelection",
    "expectedBehavior",
    "forbiddenBehavior",
    "acceptanceCriteria",
)
EXPECTED_STARTER_PROMPT_COUNT = 5
EXPECTED_TEST_CASE_COUNT = 8
EXPECTED_POSITIVE_COUNT = 5
EXPECTED_NEGATIVE_COUNT = 3
VALID_TEST_TYPES = ("positive", "negative")
VALID_MODES = ("FULL", "FOCUSED_REAUDIT", "RELEASE", "DOCS_ONLY")

EXPECTED_MANIFEST_VERSION = "0.1.0-dev.1"
EXPECTED_MANIFEST_CAPABILITIES = ["Read"]
FORBIDDEN_MANIFEST_KEYS = ("mcpServers", "apps", "hooks")

HUMAN_PREREQUISITE_ITEMS = (
    "OpenAI Platform organization selected",
    "Apps Management Write permission",
    "L&Co.LLC business identity verification",
    "Public website review",
    "Support URL review",
    "Privacy URL review",
    "Terms URL review",
    "Availability decision",
    "Logo approval",
    "Final Skill ZIP upload",
    "Submission portal draft creation",
    "Policy attestations",
    "Final submit decision",
)
PENDING_HUMAN_CHECK = "PENDING HUMAN CHECK"

# Each entry is one boundary: a label plus the accepted wordings. At least
# one wording must survive, so a single deletion cannot be masked by the
# other boundaries still being present.
PRIVACY_REQUIRED_BOUNDARIES = (
    ("skills-only Plugin", ("skills-only Plugin",)),
    ("no MCP server", ("no MCP server",)),
    ("no ChatGPT app", ("no ChatGPT app",)),
    ("no connector", ("no connector",)),
    ("no external service", ("no external service",)),
    ("no telemetry", ("no telemetry",)),
    ("no analytics", ("no analytics",)),
    ("no authentication flow", ("no authentication flow",)),
    ("no network client", ("no network client",)),
    (
        "the Plugin itself does not collect, transmit, sell, or share user data",
        ("does not collect, transmit, sell, or share user data",),
    ),
    (
        "L&Co.LLC does not receive task contents merely because the Plugin is installed",
        ("does not receive your task contents merely because the Plugin is installed",),
    ),
    (
        "the Plugin reads only data made available to the active task under the "
        "user's environment and permissions",
        ("reads only the data that is already made available to the active",),
    ),
    (
        "host-product and configured-tool data remains governed by those products "
        "and tools",
        ("remains governed by the host product and by the tools you have configured",),
    ),
    (
        "this policy does not change or override the host product's terms",
        ("does not change or override those terms",),
    ),
    (
        "users must not paste secrets unnecessarily",
        ("unnecessarily",),
    ),
    (
        "audit outputs may include paths, SHAs, branches, filenames, evidence, "
        "and findings",
        ("repository paths, commit SHAs, branch names, filenames",),
    ),
    (
        "users control where outputs are stored or shared",
        ("You control where those outputs are stored, pasted, or shared",),
    ),
    (
        "a future stateful or hosted component requires a new policy and review",
        ("requires a new privacy policy and a new review",),
    ),
)

SUPPORT_REQUIRED_BOUNDARIES = (
    ("the only support channel is GitHub Issues", ("only support channel", "GitHub Issues")),
    (
        "the public support URL",
        ("https://github.com/landco-llc/agentic-change-audit/issues",),
    ),
    (
        "secrets must not be published in a public report",
        ("Do not publish secrets, credentials, tokens",),
    ),
    ("support is best effort", ("best effort",)),
    ("no guaranteed response time", ("no guaranteed response time",)),
    ("no guarantee of a reply", ("no guarantee of a reply",)),
    (
        "no free implementation or integration work",
        ("free implementation work or integration work",),
    ),
    (
        "no audit, security certification, or compliance certification service",
        ("audit services, security certification, or compliance certification",),
    ),
    ("no legal advice", ("legal advice",)),
    (
        "no production support, incident response, or uptime commitment",
        ("production support, incident response, or uptime commitments",),
    ),
    (
        "no commercial or organization-specific support",
        ("commercial or organization-specific support",),
    ),
    (
        "paid professional services are separate from the open-source license",
        ("They are not part of this repository's license",),
    ),
)

SUPPORT_CHANNEL_HEADING = "## Support channel"
CANONICAL_SUPPORT_URL = "https://github.com/landco-llc/agentic-change-audit/issues"
SUPPORT_CHANNEL_DESCRIPTOR_PATTERN = re.compile(
    r"\b(?:official|support channel|portal|help ?desk|support contact|support)\b",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"'`]+")

# Material equivalents each Plugin README must still state. Presence alone is
# not sufficient: the claim scan runs over the same files, so an appended
# availability claim still fails even with every phrase below intact.
PLUGIN_README_REQUIRED_BOUNDARIES = {
    PLUGIN_README_RELATIVE: (
        ("development preview", ("development preview",)),
        (
            "not submitted to, listed in, or available from the public Plugins Directory",
            ("not submitted to, listed in, or available from",),
        ),
        (
            "official OpenAI submission is not complete",
            ("Official OpenAI submission is not complete",),
        ),
        (
            "no public Directory availability is claimed",
            ("No public Directory availability is claimed",),
        ),
        (
            "identity verification, logo approval, and submission remain pending",
            ("remain pending human decisions",),
        ),
    ),
    PLUGIN_README_JA_RELATIVE: (
        ("development preview", ("development preview",)),
        (
            "公開Plugins Directoryへ申請・登録・公開されていない",
            ("公開Plugins Directoryへ申請・登録・公開されていません",),
        ),
        ("正式申請は完了していない", ("正式申請は完了していません",)),
        ("公開Directoryでの提供を主張しない", ("公開Directoryでの提供は一切主張しません",)),
        (
            "identity verification、logo承認、申請が人間判断待ち",
            ("人間の判断待ちです",),
        ),
    ),
    PLUGIN_README_ZH_HANT_RELATIVE: (
        ("development preview", ("development preview",)),
        (
            "尚未提交、列入或公開於公開Plugins Directory",
            ("尚未提交、列入或公開於",),
        ),
        ("尚未完成正式申請", ("尚未完成向 OpenAI 的正式申請",)),
        ("不主張任何公開Directory上架", ("不主張任何公開 Directory 上架",)),
        (
            "identity verification、logo核准與申請仍待人工決定",
            ("均仍待人工決定",),
        ),
    ),
}

# A private local path leaking into a public submission artifact.
LOCAL_PATH_PATTERNS = (
    re.compile(r"(?<![\w./])/Users/[A-Za-z0-9._-]+"),
    re.compile(r"(?<![\w./])/home/[A-Za-z0-9._-]+"),
    re.compile(r"(?<![\w./])/private/(?:tmp|var)/"),
    re.compile(r"(?<![\w./])/var/folders/"),
    re.compile(r"\b[A-Za-z]:\\\\?(?:Users|Documents)\b"),
    re.compile(r"\bfile:///"),
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ALLOWED_EMAIL_DOMAIN = "example.invalid"

SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
)

# Product and submission status claims. These target the status of the
# Plugin itself, not benign wording such as "Public policy URLs are
# prepared." or "policies are published from this repository".
CLAIM_PATTERNS = (
    # English. Publishing a policy file from the repository is not a status
    # claim about the Plugin, so that wording is excluded deliberately.
    re.compile(
        r"\b(?:is|are|was|were)\s+(?:now\s+)?published\b(?!\s+from\s+this\s+repository)",
        re.IGNORECASE,
    ),
    re.compile(r"\bhas\s+been\s+(?:published|approved|submitted|released)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+(?:now\s+)?(?:approved|submitted)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+(?:now\s+)?stable\b", re.IGNORECASE),
    re.compile(r"\bstable\s+(?:release|version)\b", re.IGNORECASE),
    re.compile(r"\bpublicly\s+available\b", re.IGNORECASE),
    re.compile(r"\bgenerally\s+available\b", re.IGNORECASE),
    re.compile(r"\bpublic\s+release\b", re.IGNORECASE),
    re.compile(r"\blisted\s+in\b[^\n]{0,60}?\bDirectory\b", re.IGNORECASE),
    re.compile(r"\bavailable\s+(?:from|in)\b[^\n]{0,60}?\bDirectory\b", re.IGNORECASE),
    # Japanese.
    re.compile(r"公開\s*Plugins\s*Directory[^\n]{0,20}?(?:掲載|提供|公開|上架)されています"),
    re.compile(r"公開\s*Plugins\s*Directory[^\n]{0,20}?(?:から|で)[^\n]{0,10}?利用可能です"),
    re.compile(r"(?:正式)?申請(?:は|が)?完了しています"),
    re.compile(r"公開されています"),
    re.compile(r"承認されています"),
    # Traditional Chinese.
    re.compile(r"公開\s*Plugins\s*Directory[^\n]{0,15}?(?:上架|提供)"),
    re.compile(r"已(?:公開)?上架"),
    re.compile(r"已(?:獲|取得)核准"),
    re.compile(r"已(?:提交|送出)申請"),
)

# A claim is safe only when a negation applies inside its own clause.
NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|never|without|nothing|neither|nor|cannot|none)\b"
    r"|(?:ません|ない|ず|未|不|せん)"
    r"|(?:尚未|沒|非|無)",
    re.IGNORECASE,
)

# Sentence boundaries plus contrastive connectors. A negation before "but"
# does not license a claim after it, so each clause is inspected alone.
CLAUSE_SPLIT_PATTERN = re.compile(
    r"[.!?;:\n。！？；]"
    r"|(?<![A-Za-z])(?:but|however|yet|although|though|whereas)(?![A-Za-z])"
    r"|しかし|ただし|一方|とはいえ"
    r"|但是|但|然而|不過",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Codex Plugin submission package."
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


def check_exact(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label} must equal {expected!r}; found {actual!r}.")


def check_key_set(errors: list[str], label: str, actual: set[str], expected: set[str]) -> None:
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        errors.append(f"{label} keys mismatch; missing={missing}, extra={extra}")


def validate_required_files(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        candidate = root / relative
        if not candidate.is_file():
            errors.append(f"Required submission file is missing: {relative}")
        elif candidate.stat().st_size == 0:
            errors.append(f"Required submission file is empty: {relative}")


def find_empty_strings(value: Any, path: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        if not value.strip():
            found.append(path or "<root>")
    elif isinstance(value, dict):
        for key, sub_value in value.items():
            found.extend(find_empty_strings(sub_value, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_empty_strings(item, f"{path}[{index}]"))
    return found


def validate_listing(root: Path, errors: list[str]) -> None:
    try:
        listing = load_json(root / LISTING_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(listing, dict):
        errors.append("listing.json must be a JSON object.")
        return

    check_key_set(errors, "listing.json top-level", set(listing), EXPECTED_LISTING_KEYS)

    check_exact(
        errors, "listing.json submissionType", listing.get("submissionType"),
        EXPECTED_SUBMISSION_TYPE,
    )
    check_exact(errors, "listing.json pluginName", listing.get("pluginName"), EXPECTED_PLUGIN_NAME)
    check_exact(errors, "listing.json publisher", listing.get("publisher"), EXPECTED_PUBLISHER)
    check_exact(
        errors, "listing.json shortDescription", listing.get("shortDescription"),
        EXPECTED_SHORT_DESCRIPTION,
    )
    check_exact(
        errors, "listing.json longDescription", listing.get("longDescription"),
        EXPECTED_LONG_DESCRIPTION,
    )
    check_exact(errors, "listing.json category", listing.get("category"), EXPECTED_CATEGORY)
    check_exact(errors, "listing.json websiteUrl", listing.get("websiteUrl"), EXPECTED_WEBSITE_URL)
    check_exact(errors, "listing.json supportUrl", listing.get("supportUrl"), EXPECTED_SUPPORT_URL)
    check_exact(errors, "listing.json privacyUrl", listing.get("privacyUrl"), EXPECTED_PRIVACY_URL)
    check_exact(errors, "listing.json termsUrl", listing.get("termsUrl"), EXPECTED_TERMS_URL)
    check_exact(errors, "listing.json logoStatus", listing.get("logoStatus"), EXPECTED_LOGO_STATUS)
    check_exact(
        errors, "listing.json releaseStatus", listing.get("releaseStatus"),
        EXPECTED_RELEASE_STATUS,
    )
    check_exact(
        errors, "listing.json publicDirectoryStatus", listing.get("publicDirectoryStatus"),
        EXPECTED_PUBLIC_DIRECTORY_STATUS,
    )

    for key in URL_LISTING_KEYS:
        value = listing.get(key)
        if isinstance(value, str) and not value.startswith("https://"):
            errors.append(f"listing.json {key} must be an HTTPS URL; found {value!r}.")

    identity = listing.get("developerIdentity")
    if not isinstance(identity, dict):
        errors.append("listing.json 'developerIdentity' must be an object.")
    else:
        check_key_set(
            errors, "listing.json developerIdentity", set(identity),
            EXPECTED_DEVELOPER_IDENTITY_KEYS,
        )
        check_exact(
            errors, "listing.json developerIdentity.type", identity.get("type"),
            EXPECTED_DEVELOPER_TYPE,
        )
        check_exact(
            errors, "listing.json developerIdentity.name", identity.get("name"),
            EXPECTED_DEVELOPER_NAME,
        )
        # An agent must never assert that OpenAI has verified this business.
        check_exact(
            errors, "listing.json developerIdentity.verificationStatus",
            identity.get("verificationStatus"), EXPECTED_VERIFICATION_STATUS,
        )

    skills = listing.get("skills")
    if not isinstance(skills, list) or len(skills) != 1:
        errors.append("listing.json 'skills' must contain exactly one entry.")
    else:
        entry = skills[0]
        if not isinstance(entry, dict):
            errors.append("listing.json skills entry must be an object.")
        else:
            check_key_set(errors, "listing.json skills[0]", set(entry), EXPECTED_SKILL_KEYS)
            check_exact(
                errors, "listing.json skills[0].name", entry.get("name"), EXPECTED_SKILL_NAME
            )
            check_exact(
                errors, "listing.json skills[0].path", entry.get("path"), EXPECTED_SKILL_PATH
            )
            path_value = entry.get("path")
            if isinstance(path_value, str) and not (root / path_value).is_dir():
                errors.append(
                    f"listing.json skills[0].path does not exist in the repository: {path_value}"
                )

    for location in find_empty_strings(listing, ""):
        errors.append(f"listing.json contains an empty string at: {location}")


def validate_starter_prompts(root: Path, errors: list[str]) -> None:
    try:
        document = load_json(root / STARTER_PROMPTS_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(document, dict) or "starterPrompts" not in document:
        errors.append("starter-prompts.json must be an object with a 'starterPrompts' key.")
        return

    prompts = document["starterPrompts"]
    if not isinstance(prompts, list):
        errors.append("starter-prompts.json 'starterPrompts' must be a list.")
        return

    if len(prompts) != EXPECTED_STARTER_PROMPT_COUNT:
        errors.append(
            f"starter-prompts.json must contain exactly {EXPECTED_STARTER_PROMPT_COUNT} "
            f"prompts; found {len(prompts)}."
        )

    seen: set[str] = set()
    for index, prompt in enumerate(prompts):
        label = f"starter-prompts.json[{index}]"
        if not isinstance(prompt, dict):
            errors.append(f"{label} must be an object.")
            continue

        check_key_set(errors, label, set(prompt), set(STARTER_PROMPT_FIELDS))

        for field in STARTER_PROMPT_FIELDS:
            value = prompt.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} field {field!r} must be a non-empty string.")

        prompt_id = prompt.get("id")
        if isinstance(prompt_id, str):
            if prompt_id in seen:
                errors.append(f"starter-prompts.json has a duplicate id: {prompt_id}")
            seen.add(prompt_id)

        mode = prompt.get("expectedMode")
        if isinstance(mode, str) and mode not in VALID_MODES:
            errors.append(
                f"{label} expectedMode must be one of {list(VALID_MODES)}; found {mode!r}."
            )

    for location in find_empty_strings(document, ""):
        errors.append(f"starter-prompts.json contains an empty string at: {location}")


def validate_test_cases(root: Path, errors: list[str]) -> None:
    try:
        document = load_json(root / TEST_CASES_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(document, dict) or "testCases" not in document:
        errors.append("test-cases.json must be an object with a 'testCases' key.")
        return

    cases = document["testCases"]
    if not isinstance(cases, list):
        errors.append("test-cases.json 'testCases' must be a list.")
        return

    if len(cases) != EXPECTED_TEST_CASE_COUNT:
        errors.append(
            f"test-cases.json must contain exactly {EXPECTED_TEST_CASE_COUNT} test cases; "
            f"found {len(cases)}."
        )

    seen: set[str] = set()
    positive = 0
    negative = 0

    for index, case in enumerate(cases):
        label = f"test-cases.json[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object.")
            continue

        check_key_set(errors, label, set(case), set(TEST_CASE_FIELDS))

        for field in TEST_CASE_FIELDS:
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} field {field!r} must be a non-empty string.")

        case_id = case.get("id")
        if isinstance(case_id, str):
            if case_id in seen:
                errors.append(f"test-cases.json has a duplicate id: {case_id}")
            seen.add(case_id)

        case_type = case.get("type")
        if case_type == "positive":
            positive += 1
        elif case_type == "negative":
            negative += 1
        else:
            errors.append(
                f"{label} type must be one of {list(VALID_TEST_TYPES)}; found {case_type!r}."
            )

    if positive != EXPECTED_POSITIVE_COUNT:
        errors.append(
            f"test-cases.json must contain exactly {EXPECTED_POSITIVE_COUNT} positive test "
            f"cases; found {positive}."
        )
    if negative != EXPECTED_NEGATIVE_COUNT:
        errors.append(
            f"test-cases.json must contain exactly {EXPECTED_NEGATIVE_COUNT} negative test "
            f"cases; found {negative}."
        )

    for location in find_empty_strings(document, ""):
        errors.append(f"test-cases.json contains an empty string at: {location}")


def validate_availability(root: Path, errors: list[str]) -> None:
    try:
        availability = load_json(root / AVAILABILITY_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(availability, dict):
        errors.append("availability.json must be a JSON object.")
        return

    # Availability is a human decision; the file may only record a recommendation.
    check_exact(
        errors, "availability.json status", availability.get("status"),
        EXPECTED_AVAILABILITY_STATUS,
    )

    for key in ("recommendedInitialAvailability", "languageSupport", "excludedRegions"):
        if not isinstance(availability.get(key), list):
            errors.append(f"availability.json {key!r} must be a list.")

    notes = availability.get("decisionNotes")
    if not isinstance(notes, str) or not notes.strip():
        errors.append("availability.json 'decisionNotes' must be a non-empty string.")

    for location in find_empty_strings(availability, ""):
        errors.append(f"availability.json contains an empty string at: {location}")


def check_boundaries(
    errors: list[str],
    label: str,
    text: str,
    boundaries: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    lowered = text.lower()
    for name, wordings in boundaries:
        if not all(wording.lower() in lowered for wording in wordings):
            errors.append(f"{label} must state the boundary: {name}")


def validate_privacy(root: Path, errors: list[str]) -> None:
    path = root / PRIVACY_RELATIVE
    if not path.is_file():
        return
    check_boundaries(
        errors, "PRIVACY.md", path.read_text(encoding="utf-8"), PRIVACY_REQUIRED_BOUNDARIES
    )


def section_text(text: str, heading: str) -> str:
    """Return the body under an exact Markdown heading, up to the next
    heading of the same level."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    collected: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == heading:
            inside = True
            continue
        if inside:
            stripped = line.strip()
            if stripped.startswith("#"):
                current_level = len(stripped) - len(stripped.lstrip("#"))
                if current_level <= level:
                    break
            collected.append(line)
    return "\n".join(collected)


def validate_support(root: Path, errors: list[str]) -> None:
    path = root / SUPPORT_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    check_boundaries(errors, "SUPPORT.md", text, SUPPORT_REQUIRED_BOUNDARIES)

    if not section_text(text, SUPPORT_CHANNEL_HEADING).strip():
        errors.append(f"SUPPORT.md must contain a {SUPPORT_CHANNEL_HEADING!r} section.")

    # GitHub Issues is the only support channel. A second URL presented as an
    # official channel contradicts that. The whole file is checked, not just
    # the Support channel section, because appending the same claim to the
    # Japanese or Traditional Chinese section contradicts it just as much.
    # Related-document links are relative and carry no URL, so they are unaffected.
    for line in text.splitlines():
        for match in URL_PATTERN.finditer(line):
            url = match.group(0).rstrip(".,;)")
            if url == CANONICAL_SUPPORT_URL:
                continue
            if SUPPORT_CHANNEL_DESCRIPTOR_PATTERN.search(line):
                errors.append(
                    "SUPPORT.md declares GitHub Issues as the only support channel, so "
                    f"it must not present another support channel: {line.strip()!r}"
                )


def validate_plugin_readmes(root: Path, errors: list[str]) -> None:
    for relative in PLUGIN_README_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"Required Plugin README is missing: {relative}")
            continue
        if path.stat().st_size == 0:
            errors.append(f"Required Plugin README is empty: {relative}")
            continue
        check_boundaries(
            errors,
            relative,
            path.read_text(encoding="utf-8"),
            PLUGIN_README_REQUIRED_BOUNDARIES[relative],
        )


def validate_human_prerequisites(root: Path, errors: list[str]) -> None:
    path = root / HUMAN_PREREQUISITES_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    # Parse the status table structurally. Substring presence is not enough:
    # "COMPLETE - previously PENDING HUMAN CHECK" contains the pending text
    # while asserting the opposite, so the status cell must equal it exactly.
    data_rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
            continue
        if cells == ["#", "Item", "Status"]:
            continue
        data_rows.append(cells)

    for row in data_rows:
        if len(row) != 3:
            errors.append(
                "human-prerequisites.md status row must have exactly three cells "
                f"(number, item, status); found {len(row)}: {row!r}"
            )

    seen: dict[str, int] = {}
    for row in data_rows:
        if len(row) != 3:
            continue
        item = row[1]
        seen[item] = seen.get(item, 0) + 1
        if item not in HUMAN_PREREQUISITE_ITEMS:
            errors.append(
                f"human-prerequisites.md status table has an unexpected item: {item!r}"
            )
            continue
        status = row[2]
        if status != PENDING_HUMAN_CHECK:
            errors.append(
                f"human-prerequisites.md status cell for {item!r} must equal "
                f"{PENDING_HUMAN_CHECK!r} exactly; found {status!r}."
            )

    for item in HUMAN_PREREQUISITE_ITEMS:
        count = seen.get(item, 0)
        if count == 0:
            errors.append(
                f"human-prerequisites.md status table is missing the required item: {item}"
            )
        elif count > 1:
            errors.append(
                f"human-prerequisites.md status table has {count} rows for {item!r}; "
                "exactly one is required."
            )


def validate_visual_assets(root: Path, errors: list[str]) -> None:
    path = root / VISUAL_ASSETS_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if EXPECTED_LOGO_STATUS not in text:
        errors.append(f"visual-assets.md must record the logo status {EXPECTED_LOGO_STATUS!r}.")


def validate_release_notes(root: Path, errors: list[str]) -> None:
    path = root / RELEASE_NOTES_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")

    if EXPECTED_MANIFEST_VERSION not in text:
        errors.append(
            f"release-notes.md must record the current Plugin version "
            f"{EXPECTED_MANIFEST_VERSION!r}."
        )


def validate_status_claims(root: Path, errors: list[str]) -> None:
    """Reject any product or submission status claim that is not negated
    within its own clause.

    A negation earlier in the sentence does not license a later claim:
    "No approval has occurred, but this Plugin is published." asserts
    publication. Splitting at contrastive connectors isolates each clause so
    the negation only covers what it actually negates.
    """
    for relative in CLAIM_SCAN_FILES:
        path = root / relative
        if not path.is_file():
            continue
        for clause in CLAUSE_SPLIT_PATTERN.split(path.read_text(encoding="utf-8")):
            stripped = clause.strip()
            if not stripped:
                continue
            for pattern in CLAIM_PATTERNS:
                match = pattern.search(stripped)
                if not match:
                    continue
                if NEGATION_PATTERN.search(stripped):
                    continue
                errors.append(
                    f"{relative} must not claim public Directory availability, or "
                    f"submitted, published, approved, or stable status: "
                    f"{stripped!r} asserts {match.group(0)!r}."
                )


def validate_no_local_paths(root: Path, errors: list[str]) -> None:
    for relative in SCANNED_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in LOCAL_PATH_PATTERNS:
            for match in pattern.finditer(text):
                errors.append(
                    f"{relative} contains a private local path: {match.group(0)!r}"
                )


def validate_no_addresses(root: Path, errors: list[str]) -> None:
    for relative in SCANNED_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in EMAIL_PATTERN.finditer(text):
            address = match.group(0)
            if address.lower().endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
                continue
            errors.append(
                f"{relative} contains an email address; only {ALLOWED_EMAIL_DOMAIN} "
                f"placeholders are allowed: {address!r}"
            )


def validate_no_secrets(root: Path, errors: list[str]) -> None:
    for relative in SCANNED_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"{relative} contains a secret-like value matching {pattern.pattern!r}."
                )


def contains_key(value: Any, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if key in forbidden:
                found.append(key)
            found.extend(contains_key(sub_value, forbidden))
    elif isinstance(value, list):
        for item in value:
            found.extend(contains_key(item, forbidden))
    return found


def validate_manifest_boundary(root: Path, errors: list[str]) -> None:
    """The submission package must not move the Plugin runtime boundary."""
    try:
        manifest = load_json(root / MANIFEST_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(manifest, dict):
        errors.append("plugin.json must be a JSON object.")
        return

    check_exact(
        errors, "plugin.json version", manifest.get("version"), EXPECTED_MANIFEST_VERSION
    )

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json 'interface' must be an object.")
    else:
        check_exact(
            errors, "plugin.json interface.capabilities", interface.get("capabilities"),
            EXPECTED_MANIFEST_CAPABILITIES,
        )

    for key in contains_key(manifest, FORBIDDEN_MANIFEST_KEYS):
        errors.append(f"plugin.json must not contain a forbidden runtime key: {key}")


def run_plugin_validator(root: Path, errors: list[str]) -> None:
    validator = root / PLUGIN_VALIDATOR_RELATIVE
    if not validator.is_file():
        errors.append(f"Plugin validator script is missing: {PLUGIN_VALIDATOR_RELATIVE}")
        return

    result = subprocess.run(
        [sys.executable, str(validator), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("Existing Codex Plugin validator failed:")
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            errors.append(f"  {line}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    errors: list[str] = []

    validate_required_files(root, errors)
    validate_listing(root, errors)
    validate_starter_prompts(root, errors)
    validate_test_cases(root, errors)
    validate_availability(root, errors)
    validate_privacy(root, errors)
    validate_support(root, errors)
    validate_plugin_readmes(root, errors)
    validate_human_prerequisites(root, errors)
    validate_visual_assets(root, errors)
    validate_release_notes(root, errors)
    validate_status_claims(root, errors)
    validate_no_local_paths(root, errors)
    validate_no_addresses(root, errors)
    validate_no_secrets(root, errors)
    validate_manifest_boundary(root, errors)
    run_plugin_validator(root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            f"Plugin submission validation: FAIL ({len(errors)} issue(s))", file=sys.stderr
        )
        return 1

    print("Plugin submission validation: PASS")
    print(f"- listing: {root / LISTING_RELATIVE}")
    print(f"- starter prompts: {EXPECTED_STARTER_PROMPT_COUNT}")
    print(
        f"- test cases: {EXPECTED_TEST_CASE_COUNT} "
        f"({EXPECTED_POSITIVE_COUNT} positive, {EXPECTED_NEGATIVE_COUNT} negative)"
    )
    print(f"- developer identity: {EXPECTED_VERIFICATION_STATUS}")
    print(f"- logo: {EXPECTED_LOGO_STATUS}")
    print(f"- public content scanned: {len(SCANNED_FILES)} files")
    print(f"- status claims: none unnegated in {len(CLAIM_SCAN_FILES)} files")
    print(f"- human gates: {len(HUMAN_PREREQUISITE_ITEMS)} × {PENDING_HUMAN_CHECK}")
    print(f"- availability: {EXPECTED_AVAILABILITY_STATUS}")
    print(f"- public directory status: {EXPECTED_PUBLIC_DIRECTORY_STATUS}")
    print(f"- Plugin version: {EXPECTED_MANIFEST_VERSION} (unchanged)")
    print("- capabilities: Read only")
    print("- submission to OpenAI: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
