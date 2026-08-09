#!/usr/bin/env python3
"""Validate ACA orchestration work records and work results without network access."""

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
except ImportError as exc:  # pragma: no cover - depends on caller environment
    raise SystemExit(
        "jsonschema with format dependencies is required. Install validation "
        "dependencies with: python -m pip install -r requirements-validation.txt"
    ) from exc


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATION_ROOT = REPOSITORY_ROOT / "docs/ai-dev-ops/orchestration"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
TARGET_REQUIRED_STATES = frozenset(
    {
        "AUDITING",
        "REAUDITING",
        "PASS",
        "PASS_WITH_COMMENTS",
        "FAST_TRACK_ELIGIBLE",
        "READY",
        "MERGED",
        "POST_MERGE_SYNC",
    }
)
IMPLEMENTATION_FORBIDDEN = frozenset(
    {"AUDITING", "PASS", "PASS_WITH_COMMENTS", "READY", "MERGED", "COMPLETED"}
)
AUDIT_FORBIDDEN = frozenset({"IMPLEMENTING", "CORRECTING"})
CORRECTION_FORBIDDEN = frozenset(
    {"PASS", "PASS_WITH_COMMENTS", "READY", "MERGED", "COMPLETED"}
)
RESULT_STATES = {
    "IMPLEMENTATION": frozenset({"IMPLEMENTED_DRAFT_PR", "BLOCKED", "HARD_GATE"}),
    "INDEPENDENT_AUDIT": frozenset(
        {"PASS", "PASS_WITH_COMMENTS", "CHANGES_REQUESTED", "BLOCKED", "NOT_AUDITABLE"}
    ),
    "FRESH_REAUDIT": frozenset(
        {"PASS", "PASS_WITH_COMMENTS", "CHANGES_REQUESTED", "BLOCKED", "NOT_AUDITABLE"}
    ),
    "CORRECTION": frozenset({"REAUDITING", "BLOCKED", "HARD_GATE"}),
}
NON_BLOCKING_RESULT_STATES = frozenset(
    {"IMPLEMENTED_DRAFT_PR", "REAUDITING", "PASS", "PASS_WITH_COMMENTS"}
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def render(self) -> str:
        return f"{self.code} {self.path}: {self.message}"


class DuplicateKeyError(ValueError):
    """Raised when an input object repeats a JSON key."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate key {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    except FileNotFoundError as exc:
        raise ValueError(f"File not found: {path}") from exc
    except DuplicateKeyError as exc:
        raise ValueError(f"Duplicate JSON key in {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def format_path(parts: Iterable[Any]) -> str:
    rendered = "$"
    for part in parts:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered


def schema_issue_code(validator_name: str | None) -> str:
    if validator_name == "format":
        return "SCHEMA_FORMAT"
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", validator_name or "validation")
    return f"SCHEMA_{cleaned.upper().strip('_')}"


def build_validator(schema: Any) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    checker = FormatChecker()
    if "date-time" not in checker.checkers:
        raise RuntimeError(
            "The date-time format checker is unavailable. Install "
            "jsonschema[format-nongpl] from requirements-validation.txt."
        )
    return Draft202012Validator(schema, format_checker=checker)


def schema_issues(document: Any, validator: Draft202012Validator) -> list[ValidationIssue]:
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: (tuple(str(part) for part in item.path), str(item.validator), item.message),
    )
    return [
        ValidationIssue(schema_issue_code(error.validator), format_path(error.path), error.message)
        for error in errors
    ]


def allowed_transitions(schema: dict[str, Any]) -> dict[str, set[str]]:
    raw = schema.get("x-aca-allowed-transitions")
    if not isinstance(raw, dict):
        raise RuntimeError("Schema is missing x-aca-allowed-transitions.")
    normalized: dict[str, set[str]] = {}
    for from_state, to_states in raw.items():
        if not isinstance(from_state, str) or not isinstance(to_states, list):
            raise RuntimeError("Schema x-aca-allowed-transitions is invalid.")
        normalized[from_state] = {state for state in to_states if isinstance(state, str)}
    return normalized


def record_semantic_issues(document: dict[str, Any], transitions: dict[str, set[str]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    history = document.get("state_history")
    if not isinstance(history, list) or not history:
        return issues

    identity_fields = ("work_id", "repository", "branch", "base_sha", "target_applicable", "pr_applicable")
    for index, transition in enumerate(history):
        if not isinstance(transition, dict):
            continue
        prefix = f"$.state_history[{index}]"
        if index and isinstance(history[index - 1], dict):
            previous = history[index - 1]
            if transition.get("from_state") != previous.get("to_state"):
                issues.append(ValidationIssue("WR-01", f"{prefix}.from_state", "Adjacent transitions must be continuous."))
        for field in identity_fields:
            record_field = "id" if field == "work_id" else field
            if transition.get(field) != document.get(record_field):
                issues.append(ValidationIssue("WR-03", f"{prefix}.{field}", f"Transition {field} must match the work record."))
        if transition.get("target_applicable") is True and transition.get("target_sha") != document.get("target_sha"):
            issues.append(ValidationIssue("WR-03", f"{prefix}.target_sha", "Applicable transition target_sha must match the work record."))
        if transition.get("pr_applicable") is True and transition.get("pr_number") != document.get("pr_number"):
            issues.append(ValidationIssue("WR-03", f"{prefix}.pr_number", "Applicable transition pr_number must match the work record."))

        from_state, to_state = transition.get("from_state"), transition.get("to_state")
        if not isinstance(from_state, str) or to_state not in transitions.get(from_state, set()):
            issues.append(ValidationIssue("WR-04", f"{prefix}.to_state", "Transition is not allowed by the immutable schema vocabulary."))
        if to_state in TARGET_REQUIRED_STATES and (
            transition.get("target_applicable") is not True
            or not isinstance(transition.get("target_sha"), str)
            or not FULL_SHA.fullmatch(transition["target_sha"])
        ):
            issues.append(ValidationIssue("WR-05", f"{prefix}.target_sha", "This target state requires target_applicable=true and a full 40-character target SHA."))

        role = transition.get("actor_role")
        if (
            role == "IMPLEMENTATION" and to_state in IMPLEMENTATION_FORBIDDEN
        ) or (role in {"INDEPENDENT_AUDIT", "FRESH_REAUDIT"} and to_state in AUDIT_FORBIDDEN) or (
            role == "CORRECTION" and to_state in CORRECTION_FORBIDDEN
        ):
            issues.append(ValidationIssue("WR-07", f"{prefix}.actor_role", "Actor role is not permitted to record this target state."))

        cycle = transition.get("correction_cycle")
        if to_state != "CORRECTING" and cycle is not None:
            issues.append(ValidationIssue("WR-06", f"{prefix}.correction_cycle", "correction_cycle is only permitted for a CORRECTING transition."))

    correction_cycles = [
        (index, item.get("correction_cycle"))
        for index, item in enumerate(history)
        if isinstance(item, dict) and item.get("to_state") == "CORRECTING"
    ]
    expected_cycle = 1
    for index, cycle in correction_cycles:
        if cycle != expected_cycle or not isinstance(cycle, int) or cycle > 3:
            issues.append(ValidationIssue("WR-06", f"$.state_history[{index}].correction_cycle", "Correction cycles must be sequential positive integers from 1 through 3."))
        expected_cycle += 1

    if len(correction_cycles) > 3:
        issues.append(ValidationIssue("WR-06", "$.state_history", "At most three correction cycles are permitted."))
    final = history[-1]
    if isinstance(final, dict) and document.get("state") != final.get("to_state"):
        issues.append(ValidationIssue("WR-02", "$.state", "The record state must equal the final transition to_state."))
    return issues


def result_semantic_issues(document: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    transition = document.get("transition")
    if not isinstance(transition, dict):
        return issues

    for field in ("work_id", "repository", "branch", "base_sha"):
        if document.get(field) != transition.get(field):
            issues.append(ValidationIssue("RES-01", f"$.{field}", f"Result {field} must match its transition."))
    if document.get("result_state") != transition.get("to_state"):
        issues.append(ValidationIssue("RES-02", "$.result_state", "result_state must equal transition.to_state."))
    if transition.get("target_applicable") is True and document.get("target_sha") != transition.get("target_sha"):
        issues.append(ValidationIssue("RES-03", "$.target_sha", "Applicable result target_sha must match its transition."))
    if document.get("pr_applicable") != transition.get("pr_applicable"):
        issues.append(ValidationIssue("RES-03", "$.pr_applicable", "Result pr_applicable must match its transition."))
    if transition.get("pr_applicable") is True and document.get("pr_number") != transition.get("pr_number"):
        issues.append(ValidationIssue("RES-03", "$.pr_number", "Applicable result pr_number must match its transition."))

    role, result_state = document.get("role"), document.get("result_state")
    if role in RESULT_STATES and result_state not in RESULT_STATES[role]:
        issues.append(ValidationIssue("RES-04", "$.result_state", "This role cannot produce the declared result_state."))

    if transition.get("actor_role") != role:
        issues.append(ValidationIssue("RES-05", "$.transition.actor_role", "Transition actor_role must equal the result role."))
    scope = document.get("scope_observation")
    if isinstance(scope, dict) and scope.get("allowed_scope_only") is not True:
        issues.append(ValidationIssue("RES-05", "$.scope_observation.allowed_scope_only", "Result progression requires allowed_scope_only=true."))
    checks = document.get("checks")
    if result_state in NON_BLOCKING_RESULT_STATES and isinstance(checks, list):
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            if check.get("status") in {"FAILED", "NOT_RUN"}:
                issues.append(ValidationIssue("RES-05", f"$.checks[{index}].status", "A non-blocking progression cannot contain FAILED or NOT_RUN checks."))

    next_work = document.get("next_work")
    if isinstance(next_work, dict):
        action, proposed_id = next_work.get("action"), next_work.get("proposed_id")
        if action == "PROPOSE_ONE_NEW_WORK" and not isinstance(proposed_id, str):
            issues.append(ValidationIssue("RES-05", "$.next_work.proposed_id", "PROPOSE_ONE_NEW_WORK requires exactly one proposed_id."))
        elif action != "PROPOSE_ONE_NEW_WORK" and proposed_id is not None:
            issues.append(ValidationIssue("RES-05", "$.next_work.proposed_id", "Only PROPOSE_ONE_NEW_WORK may include proposed_id."))
    return issues


def validate_document(document: Any, validator: Draft202012Validator, *, kind: str, transitions: dict[str, set[str]]) -> list[ValidationIssue]:
    issues = schema_issues(document, validator)
    if isinstance(document, dict):
        if kind == "record":
            issues.extend(record_semantic_issues(document, transitions))
        else:
            issues.extend(result_semantic_issues(document))
    return list(dict.fromkeys(issues))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate ACA orchestration records and results offline.")
    parser.add_argument("documents", nargs="+", help="JSON record or result files to validate.")
    parser.add_argument("--kind", choices=("record", "result"), required=True, help="Document contract to apply.")
    parser.add_argument("--schema", help="Override the schema path for the selected --kind.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    default_schema = "work-record.schema.json" if args.kind == "record" else "work-result.schema.json"
    schema_path = Path(args.schema) if args.schema else ORCHESTRATION_ROOT / default_schema
    try:
        schema = load_json(schema_path)
        validator = build_validator(schema)
        transitions = allowed_transitions(schema)
    except (ValueError, SchemaError, RuntimeError) as exc:
        print(f"ERROR: Unable to initialize validation: {exc}", file=sys.stderr)
        return 2

    failed = False
    for name in args.documents:
        path = Path(name)
        try:
            document = load_json(path)
        except ValueError as exc:
            failed = True
            code = "JSON_DUPLICATE_KEY" if "Duplicate JSON key" in str(exc) else "JSON_PARSE"
            print(f"Orchestration validation: FAIL ({path})", file=sys.stderr)
            print(f"ERROR: {code} $: {exc}", file=sys.stderr)
            continue
        issues = validate_document(document, validator, kind=args.kind, transitions=transitions)
        if issues:
            failed = True
            print(f"Orchestration validation: FAIL ({path})", file=sys.stderr)
            for issue in issues:
                print(f"ERROR: {issue.render()}", file=sys.stderr)
        else:
            print(f"Orchestration validation: PASS ({path}; {args.kind})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
