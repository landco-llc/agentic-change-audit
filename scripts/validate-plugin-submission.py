#!/usr/bin/env python3
"""Validate the Codex Plugin submission package without submitting anything.

The package is preparation material. This validator enforces that it stays
that way: exact listing contract, no overclaimed status, no leaked local
path, address, or secret, and an unchanged skills-only Plugin runtime.

Standard library only. No network access.
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

MANIFEST_RELATIVE = "plugins/agentic-change-audit/.codex-plugin/plugin.json"
PLUGIN_VALIDATOR_RELATIVE = "scripts/validate-codex-plugin.py"

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

# Files scanned for local paths, addresses, and secret-like values.
SCANNED_FILES = REQUIRED_FILES

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

PRIVACY_REQUIRED_PHRASES = (
    "does not collect, transmit, sell, or share user data",
    "no telemetry",
    "no MCP server",
)
SUPPORT_REQUIRED_PHRASES = (
    "best effort",
    "no guaranteed response time",
)

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

# Words that only ever appear in release notes as a negated statement. A
# sentence asserting any of them without a negation is an overclaim.
RELEASE_CLAIM_PATTERNS = (
    re.compile(r"\bstable\b", re.IGNORECASE),
    re.compile(r"\bsubmitted\b", re.IGNORECASE),
    re.compile(r"\bapproved\b", re.IGNORECASE),
    re.compile(r"\bpublished\b", re.IGNORECASE),
    re.compile(r"\bgenerally available\b", re.IGNORECASE),
    re.compile(r"\bpublicly available\b", re.IGNORECASE),
    re.compile(r"\bpublic release\b", re.IGNORECASE),
)
NEGATION_PATTERN = re.compile(
    r"\b(?:not|no|never|without|nothing|neither|nor|pending|prohibited|unchanged)\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?\n]")


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


def validate_privacy(root: Path, errors: list[str]) -> None:
    path = root / PRIVACY_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for phrase in PRIVACY_REQUIRED_PHRASES:
        if phrase.lower() not in text.lower():
            errors.append(f"PRIVACY.md must state the boundary phrase: {phrase!r}")


def validate_support(root: Path, errors: list[str]) -> None:
    path = root / SUPPORT_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for phrase in SUPPORT_REQUIRED_PHRASES:
        if phrase.lower() not in text.lower():
            errors.append(f"SUPPORT.md must state the support boundary phrase: {phrase!r}")


def validate_human_prerequisites(root: Path, errors: list[str]) -> None:
    path = root / HUMAN_PREREQUISITES_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    # Only the status table is normative; the prose below it names the same
    # items without repeating their status.
    rows = [line for line in text.splitlines() if line.lstrip().startswith("|")]

    for item in HUMAN_PREREQUISITE_ITEMS:
        matching = [row for row in rows if item in row]
        if not matching:
            errors.append(
                f"human-prerequisites.md status table is missing the required item: {item}"
            )
            continue
        for row in matching:
            if PENDING_HUMAN_CHECK not in row:
                errors.append(
                    f"human-prerequisites.md item must remain {PENDING_HUMAN_CHECK!r}: {item}"
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

    for sentence in SENTENCE_SPLIT_PATTERN.split(text):
        stripped = sentence.strip()
        if not stripped or NEGATION_PATTERN.search(stripped):
            continue
        for pattern in RELEASE_CLAIM_PATTERNS:
            match = pattern.search(stripped)
            if match:
                errors.append(
                    "release-notes.md must not claim stable, submitted, approved, or "
                    f"published status: {stripped!r} asserts {match.group(0)!r}."
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
    validate_human_prerequisites(root, errors)
    validate_visual_assets(root, errors)
    validate_release_notes(root, errors)
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
    print(f"- availability: {EXPECTED_AVAILABILITY_STATUS}")
    print(f"- public directory status: {EXPECTED_PUBLIC_DIRECTORY_STATUS}")
    print(f"- Plugin version: {EXPECTED_MANIFEST_VERSION} (unchanged)")
    print("- capabilities: Read only")
    print("- submission to OpenAI: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
