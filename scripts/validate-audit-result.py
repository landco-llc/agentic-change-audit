#!/usr/bin/env python3
"""Validate Agentic Change Audit JSON results and selected semantics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from jsonschema.exceptions import SchemaError
except ImportError as exc:  # pragma: no cover - exercised by user environments
    raise SystemExit(
        "jsonschema is required. Install a compatible version with: "
        "python -m pip install 'jsonschema>=4.26,<5'"
    ) from exc

PASSING_VERDICTS = {"PASS", "PASS WITH COMMENTS"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate audit-result JSON against the Draft 2020-12 Schema and "
            "selected canonical semantic guardrails."
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
        help="Succeed only when every supplied document is invalid.",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Skip the additional semantic guardrails.",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def format_path(parts: Iterable[Any]) -> str:
    rendered = "$"
    for part in parts:
        if isinstance(part, int):
            rendered += f"[{part}]"
        else:
            rendered += f".{part}"
    return rendered


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
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
            errors.append("A passing verdict requires schema_validation.performed=true.")
        if validity.get("status") != "VALID":
            errors.append("A passing verdict requires audit_validity.status=VALID.")
        if validity.get("target_unchanged_at_end") is not True:
            errors.append(
                "A passing verdict requires audit_validity.target_unchanged_at_end=true."
            )
        if any(item.get("blocking") is True for item in findings):
            errors.append("A passing verdict cannot contain a blocking finding.")
        if any(item.get("status") == "PENDING" for item in human_items):
            errors.append("A passing verdict cannot contain a PENDING human check.")
        if any(item.get("required") is True for item in checks_not_executed):
            errors.append("A passing verdict cannot omit a required check.")
        if any(item.get("status") in {"FAILED", "BLOCKED"} for item in checks):
            errors.append("A passing verdict cannot contain a FAILED or BLOCKED check.")

    if verdict == "PASS" and any(
        item.get("status") == "DEFERRED TO APPROVED GATE" for item in human_items
    ):
        errors.append("PASS cannot contain a DEFERRED TO APPROVED GATE human check.")

    if document.get("audit_mode") == "FOCUSED_REAUDIT" and not isinstance(
        document.get("focused_reaudit"), dict
    ):
        errors.append("FOCUSED_REAUDIT requires a non-null focused_reaudit object.")

    if human.get("required") is True and not human_items:
        errors.append("human_verification.required=true requires at least one item.")

    if human.get("required") is True and any(
        item.get("status") == "PENDING" for item in human_items
    ) and verdict != "BLOCKED":
        errors.append("A required PENDING human check requires verdict BLOCKED.")

    if any(item.get("required") is True for item in checks_not_executed) and verdict != "BLOCKED":
        errors.append("An unexecuted required check requires verdict BLOCKED.")

    return errors


def validate_document(
    document: Any,
    validator: Draft202012Validator,
    *,
    schema_only: bool,
) -> list[str]:
    errors: list[str] = []

    schema_errors = sorted(
        validator.iter_errors(document),
        key=lambda item: tuple(str(part) for part in item.path),
    )
    for error in schema_errors:
        errors.append(f"Schema {format_path(error.path)}: {error.message}")

    if not schema_errors and not schema_only:
        if not isinstance(document, dict):
            errors.append("Semantic validation requires a JSON object.")
        else:
            errors.extend(f"Semantic: {message}" for message in semantic_errors(document))

    return errors


def main() -> int:
    args = parse_args()
    schema_path = Path(args.schema)

    try:
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
    except (ValueError, SchemaError) as exc:
        print(f"ERROR: Unable to load or validate Schema: {exc}", file=sys.stderr)
        return 1

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    overall_failure = False

    for document_name in args.documents:
        path = Path(document_name)
        try:
            document = load_json(path)
        except ValueError as exc:
            overall_failure = True
            print(f"Audit result validation: FAIL ({path}; unreadable JSON)", file=sys.stderr)
            print(f"ERROR: {exc}", file=sys.stderr)
            continue

        errors = validate_document(document, validator, schema_only=args.schema_only)
        is_invalid = bool(errors)
        expected_invalid = args.expect_invalid
        passed_expectation = is_invalid if expected_invalid else not is_invalid

        expectation = "invalid" if expected_invalid else "valid"
        if passed_expectation:
            print(f"Audit result validation: PASS ({path}; expected {expectation})")
            if errors:
                for error in errors:
                    print(f"- {error}")
        else:
            overall_failure = True
            print(
                f"Audit result validation: FAIL ({path}; expected {expectation})",
                file=sys.stderr,
            )
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
            else:
                print("ERROR: Document unexpectedly passed validation.", file=sys.stderr)

    return 1 if overall_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
