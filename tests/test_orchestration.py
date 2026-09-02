from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/orchestration"
SCRIPT = ROOT / "scripts/validate-orchestration.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator_module = load_module("validate_orchestration", SCRIPT)


class OrchestrationValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record_schema = validator_module.load_json(
            ROOT / "docs/ai-dev-ops/orchestration/work-record.schema.json"
        )
        cls.result_schema = validator_module.load_json(
            ROOT / "docs/ai-dev-ops/orchestration/work-result.schema.json"
        )
        cls.record_validator = validator_module.build_validator(cls.record_schema)
        cls.result_validator = validator_module.build_validator(cls.result_schema)
        cls.transitions = validator_module.allowed_transitions(cls.record_schema)
        cls.record = validator_module.load_json(
            FIXTURES / "records/valid/preflight.json"
        )
        cls.auditing_record = validator_module.load_json(
            FIXTURES / "records/valid/auditing.json"
        )
        cls.correction_record = validator_module.load_json(
            FIXTURES / "records/valid/correction-cycle.json"
        )
        cls.result = validator_module.load_json(
            FIXTURES / "results/valid/audit-pass.json"
        )

    def record_codes(self, document):
        return {
            issue.code
            for issue in validator_module.record_semantic_issues(document, self.transitions)
        }

    def result_codes(self, document):
        return {
            issue.code
            for issue in validator_module.result_semantic_issues(document, self.transitions)
        }

    def controller_completed_record(self):
        document = copy.deepcopy(self.auditing_record)
        document["state"] = "COMPLETED"
        document["state_history"] = [
            {
                **document["state_history"][0],
                "actor_role": "CONTROLLER",
                "from_state": "POST_MERGE_SYNC",
                "to_state": "COMPLETED",
                "reason": "Post-merge checks and durable history are complete.",
                "next_permitted_action": "propose one bounded successor",
            }
        ]
        return document

    def controller_completed_result(self):
        document = validator_module.load_json(
            FIXTURES / "results/valid/implementation.json"
        )
        document.update(
            {
                "role": "CONTROLLER",
                "result_state": "COMPLETED",
                "next_work": {
                    "action": "PROPOSE_ONE_NEW_WORK",
                    "rule": "Propose one bounded successor as PLANNED only.",
                    "proposed_id": "ACA-W005",
                },
            }
        )
        document["transition"].update(
            {
                "actor_role": "CONTROLLER",
                "target_applicable": True,
                "target_sha": document["target_sha"],
                "from_state": "POST_MERGE_SYNC",
                "to_state": "COMPLETED",
                "reason": "Post-merge checks and durable history are complete.",
                "next_permitted_action": "propose one bounded successor",
            }
        )
        return document

    def test_valid_fixtures_pass_their_immutable_schemas(self):
        for kind, schema_validator in (
            ("records", self.record_validator),
            ("results", self.result_validator),
        ):
            for path in sorted((FIXTURES / kind / "valid").glob("*.json")):
                with self.subTest(path=path):
                    document = validator_module.load_json(path)
                    self.assertEqual([], validator_module.schema_issues(document, schema_validator))

    def test_invalid_fixtures_are_rejected_or_unreadable(self):
        for kind, schema_validator in (
            ("records", self.record_validator),
            ("results", self.result_validator),
        ):
            for path in sorted((FIXTURES / kind / "invalid").glob("*.json")):
                with self.subTest(path=path):
                    try:
                        document = validator_module.load_json(path)
                    except ValueError:
                        continue
                    self.assertTrue(validator_module.schema_issues(document, schema_validator))

    def test_required_fixture_inventory_exists(self):
        self.assertGreaterEqual(len(list((FIXTURES / "records/valid").glob("*.json"))), 4)
        self.assertGreaterEqual(len(list((FIXTURES / "results/valid").glob("*.json"))), 4)
        self.assertGreaterEqual(len(list((FIXTURES / "records/invalid").glob("*.json"))), 12)
        self.assertGreaterEqual(len(list((FIXTURES / "results/invalid").glob("*.json"))), 12)

    def test_strict_duplicate_key_rejection(self):
        for path in (
            FIXTURES / "records/invalid/duplicate-key.json",
            FIXTURES / "results/invalid/duplicate-key.json",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
                    validator_module.load_json(path)

    def test_wr_01_adjacent_continuity(self):
        document = copy.deepcopy(self.record)
        document["state"] = "BLOCKED"
        document["state_history"].append(
            {**document["state_history"][0], "from_state": "IMPLEMENTING", "to_state": "BLOCKED"}
        )
        self.assertIn("WR-01", self.record_codes(document))

    def test_wr_02_final_state(self):
        document = copy.deepcopy(self.record)
        document["state"] = "IMPLEMENTING"
        self.assertIn("WR-02", self.record_codes(document))

    def test_wr_03_identity(self):
        document = copy.deepcopy(self.record)
        document["state_history"][0]["repository"] = "other/repository"
        self.assertIn("WR-03", self.record_codes(document))

    def test_wr_04_transition_vocabulary(self):
        document = copy.deepcopy(self.record)
        document["state_history"][0]["to_state"] = "IMPLEMENTED_DRAFT_PR"
        self.assertIn("WR-04", self.record_codes(document))

    def test_wr_05_required_full_target(self):
        document = copy.deepcopy(self.auditing_record)
        document["state_history"][0]["target_applicable"] = False
        document["state_history"][0].pop("target_sha")
        self.assertIn("WR-05", self.record_codes(document))

    def test_wr_05_completed_requires_target_binding(self):
        document = self.controller_completed_record()
        document["state_history"][0]["target_applicable"] = False
        document["state_history"][0].pop("target_sha")
        self.assertIn("WR-05", self.record_codes(document))

    def test_wr_06_correction_cycles(self):
        document = copy.deepcopy(self.correction_record)
        document["state_history"][0]["correction_cycle"] = 0
        self.assertIn("WR-06", self.record_codes(document))

    def test_wr_07_separated_roles(self):
        document = copy.deepcopy(self.auditing_record)
        document["state_history"][0]["actor_role"] = "IMPLEMENTATION"
        self.assertIn("WR-07", self.record_codes(document))

    def test_wr_07_non_string_actor_role_is_rejected_without_crashing(self):
        document = copy.deepcopy(self.auditing_record)
        document["state_history"][0]["actor_role"] = {"role": "CONTROLLER"}
        self.assertIn("WR-07", self.record_codes(document))

    def test_wr_07_controller_cannot_record_audit_pass(self):
        document = copy.deepcopy(self.auditing_record)
        document["state"] = "PASS"
        document["state_history"].append(
            {
                **document["state_history"][-1],
                "recorded_at": "2026-08-09T00:01:00Z",
                "actor_role": "CONTROLLER",
                "from_state": "AUDITING",
                "to_state": "PASS",
            }
        )
        self.assertIn("WR-07", self.record_codes(document))

    def test_wr_07_audit_agent_cannot_bypass_fast_track_or_ready(self):
        for final_state, history in (
            (
                "FAST_TRACK_ELIGIBLE",
                (("AUDITING", "PASS"), ("PASS", "FAST_TRACK_ELIGIBLE")),
            ),
            (
                "READY",
                (
                    ("AUDITING", "PASS"),
                    ("PASS", "FAST_TRACK_ELIGIBLE"),
                    ("FAST_TRACK_ELIGIBLE", "READY"),
                ),
            ),
        ):
            with self.subTest(final_state=final_state):
                document = copy.deepcopy(self.auditing_record)
                document["state"] = final_state
                for index, (from_state, to_state) in enumerate(history, start=1):
                    document["state_history"].append(
                        {
                            **document["state_history"][-1],
                            "recorded_at": f"2026-08-09T00:0{index}:00Z",
                            "actor_role": "INDEPENDENT_AUDIT",
                            "from_state": from_state,
                            "to_state": to_state,
                        }
                    )
                self.assertIn("WR-07", self.record_codes(document))

    def test_res_01_identity(self):
        document = copy.deepcopy(self.result)
        document["repository"] = "other/repository"
        self.assertIn("RES-01", self.result_codes(document))

    def test_res_02_state(self):
        document = copy.deepcopy(self.result)
        document["result_state"] = "PASS_WITH_COMMENTS"
        self.assertIn("RES-02", self.result_codes(document))

    def test_res_03_applicable_target_and_pr(self):
        document = copy.deepcopy(self.result)
        document["target_sha"] = "dddddddddddddddddddddddddddddddddddddddd"
        document["pr_number"] = 21
        self.assertIn("RES-03", self.result_codes(document))

    def test_res_03_completed_requires_exact_target_binding(self):
        cases = {}

        not_applicable = self.controller_completed_result()
        not_applicable["transition"]["target_applicable"] = False
        not_applicable["transition"].pop("target_sha")
        cases["not_applicable"] = not_applicable

        non_full_sha = self.controller_completed_result()
        non_full_sha["target_sha"] = "a" * 64
        non_full_sha["transition"]["target_sha"] = "a" * 64
        cases["non_full_sha"] = non_full_sha

        for name, document in cases.items():
            with self.subTest(name=name):
                self.assertIn("RES-03", self.result_codes(document))

    def test_res_04_role_output(self):
        document = copy.deepcopy(self.result)
        document["role"] = "IMPLEMENTATION"
        document["transition"]["actor_role"] = "IMPLEMENTATION"
        self.assertIn("RES-04", self.result_codes(document))

    def test_res_04_controller_cannot_report_audit_pass(self):
        document = copy.deepcopy(self.result)
        document["role"] = "CONTROLLER"
        document["transition"]["actor_role"] = "CONTROLLER"
        self.assertIn("RES-04", self.result_codes(document))

    def test_res_04_non_string_role_is_rejected_without_crashing(self):
        document = copy.deepcopy(self.result)
        document["role"] = {"role": "INDEPENDENT_AUDIT"}
        self.assertIn("RES-04", self.result_codes(document))

    def test_res_05_non_string_transition_actor_role_is_rejected_without_crashing(self):
        document = copy.deepcopy(self.result)
        document["transition"]["actor_role"] = {"role": "INDEPENDENT_AUDIT"}
        self.assertIn("RES-05", self.result_codes(document))

    def test_res_05_progression_scope_checks_next_work_and_actor(self):
        document = copy.deepcopy(self.result)
        document["scope_observation"]["allowed_scope_only"] = False
        document["checks"][0]["status"] = "FAILED"
        document["next_work"] = {"action": "NONE", "rule": "none", "proposed_id": "ACA-NEXT"}
        document["transition"]["actor_role"] = "FRESH_REAUDIT"
        self.assertIn("RES-05", self.result_codes(document))

    def test_res_05_next_work_must_not_reference_its_own_work_id(self):
        document = copy.deepcopy(self.result)
        document["next_work"] = {
            "action": "PROPOSE_ONE_NEW_WORK",
            "rule": "propose next work",
            "proposed_id": document["work_id"],
        }
        self.assertIn("RES-05", self.result_codes(document))

    def test_controller_may_complete_lifecycle_and_propose_one_successor(self):
        record = self.controller_completed_record()
        result = self.controller_completed_result()

        self.assertEqual(
            [],
            validator_module.validate_document(
                record,
                self.record_validator,
                kind="record",
                transitions=self.transitions,
            ),
        )
        self.assertEqual(
            [],
            validator_module.validate_document(
                result,
                self.result_validator,
                kind="result",
                transitions=self.transitions,
            ),
        )

    def test_res_05_successor_chaining_fails_closed(self):
        for role in (
            "IMPLEMENTATION",
            "INDEPENDENT_AUDIT",
            "CORRECTION",
            "FRESH_REAUDIT",
        ):
            with self.subTest(role=role):
                document = copy.deepcopy(self.result)
                document["role"] = role
                document["next_work"] = {
                    "action": "PROPOSE_ONE_NEW_WORK",
                    "rule": "propose next work",
                    "proposed_id": "ACA-W005",
                }
                issues = validator_module.result_semantic_issues(document, self.transitions)
                self.assertTrue(
                    any(
                        issue.path == "$.next_work.action"
                        and issue.message == "Only a CONTROLLER result may propose a new Work."
                        for issue in issues
                    )
                )

        completed = self.controller_completed_result()
        cases = {}

        pending_human = copy.deepcopy(completed)
        pending_human["next_work"] = {
            "action": "HUMAN_GATE",
            "rule": "A named Human decision remains pending.",
        }
        cases["pending_human"] = (pending_human, "$.next_work.action")

        pending_decision = copy.deepcopy(completed)
        pending_decision["limitations"] = ["A material decision remains pending."]
        cases["pending_decision"] = (pending_decision, "$.limitations")

        incomplete_obligation = copy.deepcopy(completed)
        incomplete_obligation["checks"][0]["status"] = "NOT_RUN"
        cases["incomplete_obligation"] = (
            incomplete_obligation,
            "$.checks[0].status",
        )

        identity_drift = copy.deepcopy(completed)
        identity_drift["transition"]["work_id"] = "ACA-W005"
        cases["identity_drift"] = (identity_drift, "$.work_id")

        unauthorized_origin = copy.deepcopy(completed)
        unauthorized_origin["transition"]["actor_role"] = "IMPLEMENTATION"
        cases["unauthorized_origin"] = (
            unauthorized_origin,
            "$.transition.actor_role",
        )

        for name, (document, expected_path) in cases.items():
            with self.subTest(name=name):
                issues = validator_module.result_semantic_issues(
                    document, self.transitions
                )
                self.assertTrue(
                    any(
                        issue.code in {"RES-01", "RES-05", "RES-06"}
                        and issue.path == expected_path
                        for issue in issues
                    ),
                    [issue.render() for issue in issues],
                )

    def test_schema_format_family(self):
        document = copy.deepcopy(self.record)
        document["requirements_basis"]["observed_at"] = "not-a-date"
        self.assertIn("SCHEMA_FORMAT", {issue.code for issue in validator_module.schema_issues(document, self.record_validator)})

    def test_core_cli_valid_campaign(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for kind, directory in (("record", "records/valid"), ("result", "results/valid")):
            with self.subTest(kind=kind):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--kind", kind, *map(str, sorted((FIXTURES / directory).glob("*.json")))],
                    capture_output=True, text=True, check=False, env=env,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("Orchestration validation: PASS", result.stdout)

    def test_core_cli_reports_input_and_stable_code(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--kind", "record", str(FIXTURES / "records/invalid/duplicate-key.json")],
            capture_output=True, text=True, check=False, env=env,
        )
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("duplicate-key.json", result.stderr)
        self.assertIn("JSON_DUPLICATE_KEY", result.stderr)

    def test_cli_rejects_role_and_next_work_bypasses(self):
        record_fast_track = copy.deepcopy(self.auditing_record)
        record_fast_track["state"] = "FAST_TRACK_ELIGIBLE"
        for from_state, to_state in (("AUDITING", "PASS"), ("PASS", "FAST_TRACK_ELIGIBLE")):
            record_fast_track["state_history"].append(
                {
                    **record_fast_track["state_history"][-1],
                    "recorded_at": "2026-08-09T00:01:00Z",
                    "actor_role": "INDEPENDENT_AUDIT",
                    "from_state": from_state,
                    "to_state": to_state,
                }
            )
        record_ready = copy.deepcopy(record_fast_track)
        record_ready["state"] = "READY"
        record_ready["state_history"].append(
            {
                **record_ready["state_history"][-1],
                "recorded_at": "2026-08-09T00:02:00Z",
                "actor_role": "INDEPENDENT_AUDIT",
                "from_state": "FAST_TRACK_ELIGIBLE",
                "to_state": "READY",
            }
        )
        controller_pass = copy.deepcopy(self.result)
        controller_pass["role"] = "CONTROLLER"
        controller_pass["transition"]["actor_role"] = "CONTROLLER"
        self_referential_next_work = copy.deepcopy(self.result)
        self_referential_next_work["next_work"] = {
            "action": "PROPOSE_ONE_NEW_WORK",
            "rule": "propose next work",
            "proposed_id": self_referential_next_work["work_id"],
        }

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            cases = (
                ("record", "audit-fast-track.json", record_fast_track),
                ("record", "audit-ready.json", record_ready),
                ("result", "controller-pass.json", controller_pass),
                ("result", "self-referential-next-work.json", self_referential_next_work),
            )
            for kind, name, document in cases:
                with self.subTest(name=name):
                    path = directory_path / name
                    path.write_text(json.dumps(document), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), "--kind", kind, str(path)],
                        capture_output=True, text=True, check=False, env=env,
                    )
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertIn(name, result.stderr)

    def test_cli_enforces_parent_only_terminal_next_work_chaining(self):
        implementation_proposal = validator_module.load_json(
            FIXTURES / "results/valid/implementation.json"
        )
        implementation_proposal["next_work"] = {
            "action": "PROPOSE_ONE_NEW_WORK",
            "rule": "propose one bounded successor",
            "proposed_id": "ACA-W005",
        }

        completed_record = self.controller_completed_record()
        completed_result = self.controller_completed_result()

        pending_human = copy.deepcopy(completed_result)
        pending_human["next_work"] = {
            "action": "HUMAN_GATE",
            "rule": "A named Human decision remains pending.",
        }

        pending_decision = copy.deepcopy(completed_result)
        pending_decision["limitations"] = ["A material decision remains pending."]

        incomplete_obligation = copy.deepcopy(completed_result)
        incomplete_obligation["checks"][0]["status"] = "NOT_RUN"

        identity_drift = copy.deepcopy(completed_result)
        identity_drift["transition"]["target_sha"] = "d" * 40

        unauthorized_origin = copy.deepcopy(completed_result)
        unauthorized_origin["transition"]["actor_role"] = "IMPLEMENTATION"

        controller_hard_gate = copy.deepcopy(completed_result)
        controller_hard_gate["result_state"] = "HARD_GATE"
        controller_hard_gate["transition"].update(
            {
                "from_state": "PREFLIGHT",
                "to_state": "HARD_GATE",
                "next_permitted_action": "await named human prerequisite",
            }
        )

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            cases = (
                ("record", "controller-completed-record.json", completed_record, 0),
                ("result", "controller-completed-result.json", completed_result, 0),
                ("result", "implementation-next-work.json", implementation_proposal, 1),
                ("result", "controller-hard-gate-next-work.json", controller_hard_gate, 1),
                ("result", "completed-pending-human.json", pending_human, 1),
                ("result", "completed-pending-decision.json", pending_decision, 1),
                ("result", "completed-incomplete-obligation.json", incomplete_obligation, 1),
                ("result", "completed-identity-drift.json", identity_drift, 1),
                ("result", "completed-unauthorized-origin.json", unauthorized_origin, 1),
            )
            for kind, name, document, expected_returncode in cases:
                with self.subTest(name=name):
                    path = directory_path / name
                    path.write_text(json.dumps(document), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), "--kind", kind, str(path)],
                        capture_output=True, text=True, check=False, env=env,
                    )
                    observed = result.stdout + result.stderr
                    self.assertEqual(expected_returncode, result.returncode, observed)
                    if expected_returncode:
                        self.assertNotIn("Orchestration validation: PASS", observed)
                    else:
                        self.assertIn("Orchestration validation: PASS", result.stdout)

    def test_cli_rejects_non_string_roles_without_traceback_or_local_paths(self):
        documents = []
        record_actor_role = copy.deepcopy(self.auditing_record)
        record_actor_role["state_history"][0]["actor_role"] = {"role": "CONTROLLER"}
        documents.append(("record", "object-actor-role.json", record_actor_role))

        result_role = copy.deepcopy(self.result)
        result_role["role"] = {"role": "INDEPENDENT_AUDIT"}
        documents.append(("result", "object-result-role.json", result_role))

        result_actor_role = copy.deepcopy(self.result)
        result_actor_role["transition"]["actor_role"] = {"role": "INDEPENDENT_AUDIT"}
        documents.append(("result", "object-transition-actor-role.json", result_actor_role))

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory(prefix="aca-orchestration-invalid-") as directory:
            directory_path = Path(directory)
            for kind, name, document in documents:
                with self.subTest(name=name):
                    path = directory_path / name
                    path.write_text(json.dumps(document), encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), "--kind", kind, str(path)],
                        capture_output=True, text=True, check=False, env=env,
                    )
                    observed = result.stdout + result.stderr
                    self.assertEqual(1, result.returncode, observed)
                    self.assertIn(name, observed)
                    self.assertNotIn("Traceback", observed)
                    self.assertNotIn(str(directory_path), observed)
                    self.assertNotIn(str(SCRIPT), observed)

    def test_cli_accepts_optional_routing_metadata(self):
        document = copy.deepcopy(self.record)
        document["policy_version"] = "aca-local-routing-2026-09"
        document["routing"] = {
            "profile": "implementation_standard",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "medium",
            "sandbox_mode": "workspace-write",
            "selection_reason": "Approved bounded standard implementation.",
            "escalation_criteria": ["Escalate material semantic ambiguity."],
        }
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "routed-record.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--kind", "record", str(path)],
                capture_output=True, text=True, check=False, env=env,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("routed-record.json", result.stdout)

    def test_cli_rejects_mismatched_routing_metadata(self):
        document = copy.deepcopy(self.result)
        document["policy_version"] = "aca-local-routing-2026-09"
        document["routing"] = {
            "profile": "audit_standard",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "medium",
            "sandbox_mode": "read-only",
            "selection_reason": "Invalid profile/model pairing.",
            "escalation_criteria": ["Escalate."],
        }
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mismatched-routing-result.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--kind", "result", str(path)],
                capture_output=True, text=True, check=False, env=env,
            )
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("mismatched-routing-result.json", result.stderr)
        self.assertIn("SCHEMA_ONEOF", result.stderr)


if __name__ == "__main__":
    unittest.main()
