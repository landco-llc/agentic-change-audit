#!/usr/bin/env python3
"""Validate Agentic Change Audit JSON results and selected semantics."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError
except ImportError as exc:  # pragma: no cover - exercised by user environments
    raise SystemExit(
        "jsonschema with format dependencies is required. Install validation "
        "dependencies with: python -m pip install -r requirements-validation.txt"
    ) from exc

PASSING_VERDICTS = {"PASS", "PASS WITH COMMENTS"}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def render(self) -> str:
        return f"{self.code} {self.path}: {self.message}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate audit-result JSON against the Draft 2020-12 Schema and "
            "selected canonical semantic guardrails. This does not replace "
            "full audit judgment against the canonical standards."
        )
    )
    parser.add_argument("documents", nargs="+", help="JSON result files to validate.")
    parser.add_argument(
        "--schema",
        default="standard/output-schema.json",
        help="Path to the audit-result JSON Schema.",
    )
    parser.add_argument(
        "--expect-invalid",
        action="store_true",
        help=(
            "Succeed only when every supplied document is invalid for the "
            "fixture-specific reasons declared by --expectations."
        ),
    )
    parser.add_argument(
        "--expectations",
        help=(
            "JSON manifest mapping invalid fixture basenames to expected "
            "validation issue code/path objects. Required with --expect-invalid."
        ),
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help=(
            "Run JSON Schema validation only. This is not complete audit-result "
            "validation."
        ),
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc


def format_path(parts: Iterable[Any]) -> str:
    rendered = "$"
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}"
    return rendered


def schema_issue_code(validator_name: str | None) -> str:
    if validator_name == "format":
        return "SCHEMA_FORMAT"
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", validator_name or "validation")
    return f"SCHEMA_{cleaned.upper().strip('_')}"


def semantic_issues(document: dict[str, Any]) -> list[ValidationIssue]:
    """Return selected semantic issues without redefining verdict decision order."""
    issues: list[ValidationIssue] = []
    verdict = document.get("verdict")
    passing = verdict in PASSING_VERDICTS

    schema_validation = document.get("schema_validation") or {}
    validity = document.get("audit_validity") or {}
    findings = document.get("findings") or []
    human = document.get("human_verification") or {}
    human_items = human.get("items") or []
    evidence = document.get("evidence") or {}
    checks = evidence.get("checks") or []
    checks_not_executed = evidence.get("checks_not_executed") or []

    if passing:
        if schema_validation.get("performed") is not True:
            issues.append(
                ValidationIssue(
                    "PASS_SCHEMA_VALIDATION_NOT_PERFORMED",
                    "$.schema_validation.performed",
                    "A passing verdict requires semantic validation to be recorded.",
                )
            )
        if validity.get("status") != "VALID":
            issues.append(
                ValidationIssue(
                    "PASS_AUDIT_VALIDITY_NOT_VALID",
                    "$.audit_validity.status",
                    "A passing verdict requires audit_validity.status=VALID.",
                )
            )
        if validity.get("target_unchanged_at_end") is not True:
            issues.append(
                ValidationIssue(
                    "PASS_TARGET_CHANGED",
                    "$.audit_validity.target_unchanged_at_end",
                    "A passing verdict requires the final target identity to be unchanged.",
                )
            )
        for index, finding in enumerate(findings):
            if finding.get("blocking") is True:
                issues.append(
                    ValidationIssue(
                        "PASS_BLOCKING_FINDING",
                        f"$.findings[{index}].blocking",
                        "A passing verdict cannot contain a blocking finding.",
                    )
                )
        for index, item in enumerate(human_items):
            if item.get("status") == "PENDING":
                issues.append(
                    ValidationIssue(
                        "PASS_PENDING_HUMAN_CHECK",
                        f"$.human_verification.items[{index}].status",
                        "A passing verdict cannot contain a PENDING human check.",
                    )
                )
        for index, item in enumerate(checks_not_executed):
            if item.get("required") is True:
                issues.append(
                    ValidationIssue(
                        "PASS_REQUIRED_CHECK_NOT_RUN",
                        f"$.evidence.checks_not_executed[{index}].required",
                        "A passing verdict cannot omit a required check.",
                    )
                )
        for index, item in enumerate(checks):
            if item.get("status") in {"FAILED", "BLOCKED"}:
                issues.append(
                    ValidationIssue(
                        "PASS_EXECUTED_CHECK_FAILED",
                        f"$.evidence.checks[{index}].status",
                        "A passing verdict cannot contain a FAILED or BLOCKED check.",
                    )
                )

    if verdict == "PASS":
        for index, item in enumerate(human_items):
            if item.get("status") == "DEFERRED TO APPROVED GATE":
                issues.append(
                    ValidationIssue(
                        "PASS_DEFERRED_HUMAN_CHECK",
                        f"$.human_verification.items[{index}].status",
                        "PASS cannot contain a human check deferred to a later gate.",
                    )
                )

    if document.get("audit_mode") == "FOCUSED_REAUDIT" and not isinstance(
        document.get("focused_reaudit"), dict
    ):
        issues.append(
            ValidationIssue(
                "FOCUSED_REAUDIT_MISSING_PAYLOAD",
                "$.focused_reaudit",
                "FOCUSED_REAUDIT requires a non-null focused_reaudit object.",
            )
        )

    if human.get("required") is True and not human_items:
        issues.append(
            ValidationIssue(
                "HUMAN_REQUIRED_EMPTY_ITEMS",
                "$.human_verification.items",
                "human_verification.required=true requires at least one item.",
            )
        )

    # Do not force all pending dependencies or required unexecuted checks to
    # BLOCKED here. The canonical decision order gives NOT AUDITABLE priority
    # when target identity or the audit contract is invalid, and
    # CHANGES REQUESTED can also take precedence when modification is required.
    return issues


def validate_document(
    document: Any,
    validator: Draft202012Validator,
    *,
    schema_only: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    schema_errors = sorted(
        validator.iter_errors(document),
        key=lambda item: (
            tuple(str(part) for part in item.path),
            str(item.validator),
            item.message,
        ),
    )
    for error in schema_errors:
        issues.append(
            ValidationIssue(
                schema_issue_code(error.validator),
                format_path(error.path),
                error.message,
            )
        )

    if not schema_only:
        if isinstance(document, dict):
            issues.extend(semantic_issues(document))
        elif not schema_errors:
            issues.append(
                ValidationIssue(
                    "SEMANTIC_OBJECT_REQUIRED",
                    "$",
                    "Semantic validation requires a JSON object.",
                )
            )

    # Remove exact duplicates while preserving deterministic order.
    return list(dict.fromkeys(issues))


def load_expectations(path: Path) -> dict[str, list[dict[str, str]]]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Expectation manifest must be a JSON object.")

    normalized: dict[str, list[dict[str, str]]] = {}
    for filename, expected_items in data.items():
        if not isinstance(filename, str) or not isinstance(expected_items, list):
            raise ValueError(
                "Expectation manifest values must be lists keyed by fixture basename."
            )
        normalized_items: list[dict[str, str]] = []
        for item in expected_items:
            if not isinstance(item, dict) or not isinstance(item.get("code"), str):
                raise ValueError(
                    f"Expectation for {filename} must include a string 'code'."
                )
            normalized_item = {"code": item["code"]}
            if "path" in item:
                if not isinstance(item["path"], str):
                    raise ValueError(
                        f"Expectation path for {filename} must be a string."
                    )
                normalized_item["path"] = item["path"]
            normalized_items.append(normalized_item)
        if not normalized_items:
            raise ValueError(f"Expectation list for {filename} must not be empty.")
        normalized[filename] = normalized_items
    return normalized


def expectations_satisfied(
    issues: list[ValidationIssue],
    expected: list[dict[str, str]],
) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for wanted in expected:
        matches = [
            issue
            for issue in issues
            if issue.code == wanted["code"]
            and ("path" not in wanted or issue.path == wanted["path"])
        ]
        if not matches:
            suffix = f" at {wanted['path']}" if "path" in wanted else ""
            missing.append(f"{wanted['code']}{suffix}")
    return not missing, missing


def build_validator(schema: Any) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()
    if "date-time" not in checker.checkers:
        raise RuntimeError(
            "The date-time format checker is unavailable. Install "
            "jsonschema[format-nongpl] from requirements-validation.txt."
        )
    return Draft202012Validator(schema, format_checker=checker)


def main() -> int:
    args = parse_args()
    schema_path = Path(args.schema)

    if args.expect_invalid and not args.expectations:
        print(
            "ERROR: --expect-invalid requires --expectations so each fixture "
            "is rejected for its intended reason.",
            file=sys.stderr,
        )
        return 2
    if args.expectations and not args.expect_invalid:
        print(
            "ERROR: --expectations is only valid with --expect-invalid.",
            file=sys.stderr,
        )
        return 2

    try:
        schema = load_json(schema_path)
        validator = build_validator(schema)
        expectations = (
            load_expectations(Path(args.expectations))
            if args.expectations
            else {}
        )
    except (ValueError, SchemaError, RuntimeError) as exc:
        print(f"ERROR: Unable to initialize validation: {exc}", file=sys.stderr)
        return 1

    overall_failure = False

    for document_name in args.documents:
        path = Path(document_name)
        try:
            document = load_json(path)
        except ValueError as exc:
            overall_failure = True
            print(
                f"Audit result validation: FAIL ({path}; unreadable JSON)",
                file=sys.stderr,
            )
            print(f"ERROR: {exc}", file=sys.stderr)
            continue

        issues = validate_document(document, validator, schema_only=args.schema_only)

        if args.expect_invalid:
            expected = expectations.get(path.name)
            if not expected:
                overall_failure = True
                print(
                    f"Audit result validation: FAIL ({path}; no expected "
                    "issue declaration)",
                    file=sys.stderr,
                )
                continue

            if not issues:
                overall_failure = True
                print(
                    f"Audit result validation: FAIL ({path}; expected invalid)",
                    file=sys.stderr,
                )
                print(
                    "ERROR: Document unexpectedly passed validation.",
                    file=sys.stderr,
                )
                continue

            matched, missing = expectations_satisfied(issues, expected)
            if not matched:
                overall_failure = True
                print(
                    f"Audit result validation: FAIL ({path}; wrong invalid reason)",
                    file=sys.stderr,
                )
                for item in missing:
                    print(f"ERROR: Missing expected issue: {item}", file=sys.stderr)
                for issue in issues:
                    print(f"OBSERVED: {issue.render()}", file=sys.stderr)
                continue

            print(
                f"Audit result validation: PASS ({path}; expected issues matched)"
            )
            for issue in issues:
                print(f"- {issue.render()}")
        else:
            if issues:
                overall_failure = True
                print(
                    f"Audit result validation: FAIL ({path}; expected valid)",
                    file=sys.stderr,
                )
                for issue in issues:
                    print(f"ERROR: {issue.render()}", file=sys.stderr)
            else:
                print(f"Audit result validation: PASS ({path}; expected valid)")

    return 1 if overall_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
