from __future__ import annotations

import copy
import hashlib
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
    AUTHORITY_SOURCE_BYTES = b"Human standing delegation source for ACA-GOV-001.\n"
    AUTHORITY_EVALUATION_TIME = "2026-09-27T00:00:00Z"

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
        cls.campaign_record = validator_module.load_json(
            FIXTURES / "records/valid/campaign-active.json"
        )
        cls.campaign_record_bytes = (
            FIXTURES / "records/valid/campaign-active.json"
        ).read_bytes()
        cls.campaign_result = validator_module.load_json(
            FIXTURES / "results/valid/campaign-continuation.json"
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

    def authority_proof(self, work_id, target_sha, *, transitions=None, validity=None):
        return {
            "schema_id": "ACA_AUTHORITY_PROOF",
            "version": "1.0",
            "authority_kind": "HUMAN_STANDING_DELEGATION",
            "human_decision": "GRANT",
            "lifecycle_state": "ACCEPTED_CURRENT",
            "repository": "landco-llc/agentic-change-audit",
            "work_id": work_id,
            "target_sha": target_sha,
            "executor_role": "CONTROLLER",
            "covered_transitions": transitions
            or ["READY", "MERGED", "CONTINUE_CAMPAIGN"],
            "source": {
                "kind": "HUMAN_GITHUB_ISSUE_COMMENT",
                "immutable_id": "github:landco-llc/agentic-change-audit:issue:37:comment:5855064936",
                "sha256": hashlib.sha256(self.AUTHORITY_SOURCE_BYTES).hexdigest(),
            },
            "validity": validity
            or {"kind": "EXPIRES_AT", "expires_at": "2026-12-31T00:00:00Z"},
        }

    def authority_proof_bytes(self, proof=None):
        proof = proof or self.authority_proof("ACA-GOV-001", "b" * 40)
        return json.dumps(proof, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def authority_validation_kwargs(self, proof=None, source_bytes=None, evaluation_time=None):
        proof = proof or self.authority_proof("ACA-GOV-001", "b" * 40)
        proof_bytes = self.authority_proof_bytes(proof)
        source_bytes = source_bytes if source_bytes is not None else self.AUTHORITY_SOURCE_BYTES
        return {
            "authority_proof": proof,
            "authority_proof_sha256": hashlib.sha256(proof_bytes).hexdigest(),
            "authority_source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "authority_evaluation_time": evaluation_time or self.AUTHORITY_EVALUATION_TIME,
            "authority_proof_valid": True,
        }

    def run_authority_cli(
        self,
        directory_path,
        name,
        kind,
        document,
        *,
        proof_bytes=None,
        source_bytes=None,
        evaluation_time=AUTHORITY_EVALUATION_TIME,
        include_proof=True,
        include_source=True,
        campaign_record=None,
    ):
        document_path = directory_path / f"{name}-{kind}.json"
        document_path.write_text(json.dumps(document), encoding="utf-8")
        command = [sys.executable, str(SCRIPT), "--kind", kind]
        if include_proof:
            proof_path = directory_path / f"{name}-proof.json"
            proof_path.write_bytes(
                proof_bytes if proof_bytes is not None else self.authority_proof_bytes()
            )
            command.extend(["--authority-proof", str(proof_path)])
        if include_source:
            source_path = directory_path / f"{name}-source.txt"
            source_path.write_bytes(
                source_bytes if source_bytes is not None else self.AUTHORITY_SOURCE_BYTES
            )
            command.extend(["--authority-source", str(source_path)])
        if evaluation_time is not None:
            command.extend(["--evaluation-time", evaluation_time])
        if campaign_record is not None:
            record_path = directory_path / f"{name}-campaign-record.json"
            record_bytes = (json.dumps(campaign_record, indent=2) + "\n").encode("utf-8")
            record_path.write_bytes(record_bytes)
            document["next_work"]["campaign_record_sha256"] = hashlib.sha256(
                record_bytes
            ).hexdigest()
            document_path.write_text(json.dumps(document), encoding="utf-8")
            command.extend(["--campaign-record", str(record_path)])
        command.append(str(document_path))
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
        )

    def controller_lifecycle_record(self, to_state):
        from_state = "FAST_TRACK_ELIGIBLE" if to_state == "READY" else "READY"
        document = copy.deepcopy(self.auditing_record)
        document["state"] = to_state
        proof = self.authority_proof(document["id"], document["target_sha"])
        digest = hashlib.sha256(self.authority_proof_bytes(proof)).hexdigest()
        document["state_history"] = [
            {
                **document["state_history"][0],
                "actor_role": "CONTROLLER",
                "from_state": from_state,
                "to_state": to_state,
                "authority_proof_sha256": digest,
            }
        ]
        return document

    def controller_lifecycle_result(self, to_state):
        from_state = "FAST_TRACK_ELIGIBLE" if to_state == "READY" else "READY"
        document = self.controller_completed_result()
        document["result_state"] = to_state
        document["next_work"] = {"action": "NONE", "rule": "bounded lifecycle"}
        document["transition"].update(
            {
                "from_state": from_state,
                "to_state": to_state,
                "authority_proof_sha256": hashlib.sha256(
                    self.authority_proof_bytes(
                        self.authority_proof(document["work_id"], document["target_sha"])
                    )
                ).hexdigest(),
            }
        )
        return document

    def paired_result_issues(self, result, record=None, record_bytes=None):
        record = copy.deepcopy(record if record is not None else self.campaign_record)
        if record_bytes is None:
            if record == self.campaign_record:
                record_bytes = self.campaign_record_bytes
            else:
                record_bytes = (json.dumps(record, indent=2) + "\n").encode("utf-8")
        return validator_module.validate_document(
            result,
            self.result_validator,
            kind="result",
            transitions=self.transitions,
            campaign_record=record,
            campaign_record_sha256=hashlib.sha256(record_bytes).hexdigest(),
            campaign_record_validator=self.record_validator,
            **self.authority_validation_kwargs(),
        )

    def paired_campaign_documents(self, record=None):
        record = copy.deepcopy(record if record is not None else self.campaign_record)
        if record == self.campaign_record:
            record_bytes = self.campaign_record_bytes
        else:
            record_bytes = (json.dumps(record, indent=2) + "\n").encode("utf-8")
        result = copy.deepcopy(self.campaign_result)
        result["next_work"]["campaign_record_sha256"] = hashlib.sha256(
            record_bytes
        ).hexdigest()
        return record, result, record_bytes

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

    def test_controller_ready_and_merge_require_closed_typed_proof(self):
        for kind, factory, validator in (
            ("record", self.controller_lifecycle_record, self.record_validator),
            ("result", self.controller_lifecycle_result, self.result_validator),
        ):
            for to_state in ("READY", "MERGED"):
                with self.subTest(kind=kind, to_state=to_state):
                    document = factory(to_state)
                    proof = self.authority_proof(
                        document["id"] if kind == "record" else document["work_id"],
                        document["target_sha"],
                    )
                    self.assertEqual(
                        [],
                        validator_module.validate_document(
                            document,
                            validator,
                            kind=kind,
                            transitions=self.transitions,
                            **self.authority_validation_kwargs(proof),
                        ),
                    )

                    authority_location = (
                        document["state_history"][0]
                        if kind == "record"
                        else document["transition"]
                    )
                    authority_location.pop("authority_proof_sha256")
                    issues = validator_module.validate_document(
                        document,
                        validator,
                        kind=kind,
                        transitions=self.transitions,
                        **self.authority_validation_kwargs(proof),
                    )
                    self.assertTrue(issues)

    def test_legacy_self_asserted_authority_is_schema_rejected(self):
        for kind, factory, validator in (
            ("record", self.controller_lifecycle_record, self.record_validator),
            ("result", self.controller_lifecycle_result, self.result_validator),
        ):
            document = factory("READY")
            location = document if kind == "record" else document["transition"]
            location["authority_state"] = "ACCEPTED_CURRENT"
            location["delegation_binding"] = {
                "authority_state": "ACCEPTED_CURRENT"
            }
            issues = validator_module.validate_document(
                document,
                validator,
                kind=kind,
                transitions=self.transitions,
                **self.authority_validation_kwargs(),
            )
            with self.subTest(kind=kind):
                self.assertIn(
                    "SCHEMA_ADDITIONALPROPERTIES", {issue.code for issue in issues}
                )

    def test_valid_finite_campaign_record(self):
        self.assertEqual(
            [],
            validator_module.validate_document(
                self.campaign_record,
                self.record_validator,
                kind="record",
                transitions=self.transitions,
                **self.authority_validation_kwargs(),
            ),
        )

    def test_wr_08_campaign_binding_fails_closed(self):
        cases = {}

        missing_current = copy.deepcopy(self.campaign_record)
        missing_current["campaign"]["current_work_id"] = "ACA-GOV-099"
        cases["missing_current"] = missing_current

        wrong_position = copy.deepcopy(self.campaign_record)
        wrong_position["campaign"]["current_work_position"] = 3
        cases["wrong_position"] = wrong_position

        multiple_active = copy.deepcopy(self.campaign_record)
        multiple_active["campaign"]["active_work_ids"] = [
            "ACA-GOV-001",
            "ACA-GOV-002",
        ]
        cases["multiple_active"] = multiple_active

        active_identity_drift = copy.deepcopy(self.campaign_record)
        active_identity_drift["campaign"]["active_work_ids"] = ["ACA-GOV-002"]
        cases["active_identity_drift"] = active_identity_drift

        for name, document in cases.items():
            with self.subTest(name=name):
                self.assertIn("WR-08", self.record_codes(document))

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

    def test_valid_controller_campaign_continuation(self):
        record, result, record_bytes = self.paired_campaign_documents()
        self.assertEqual(
            [],
            self.paired_result_issues(result, record, record_bytes),
        )

    def test_campaign_continuation_rejects_result_created_order_and_history(self):
        record, unlisted, record_bytes = self.paired_campaign_documents()
        unlisted["next_work"]["proposed_id"] = "UNLISTED-WORK"
        self.assertIn(
            "RES-09",
            {issue.code for issue in self.paired_result_issues(unlisted, record, record_bytes)},
        )

        rollback = copy.deepcopy(unlisted)
        rollback["next_work"]["proposed_id"] = "ACA-GOV-002"
        rollback["next_work"]["correction_history"]["dispatches"] = 0
        self.assertIn(
            "RES-09",
            {issue.code for issue in self.paired_result_issues(rollback, record, record_bytes)},
        )

    def test_f02_continuation_requires_valid_exact_paired_record(self):
        record, result, record_bytes = self.paired_campaign_documents()

        absent = validator_module.validate_document(
            result,
            self.result_validator,
            kind="result",
            transitions=self.transitions,
        )
        self.assertIn("RES-09", {issue.code for issue in absent})

        digest_mismatch = copy.deepcopy(result)
        digest_mismatch["next_work"]["campaign_record_sha256"] = "0" * 64
        self.assertIn(
            "RES-09",
            {
                issue.code
                for issue in self.paired_result_issues(
                    digest_mismatch, record, record_bytes
                )
            },
        )

        for name, field, value in (
            ("repository", "repository", "other/repository"),
            ("target", "target_sha", "d" * 40),
        ):
            document = copy.deepcopy(result)
            document[field] = value
            document["transition"][field] = value
            with self.subTest(name=name):
                self.assertIn(
                    "RES-09",
                    {
                        issue.code
                        for issue in self.paired_result_issues(
                            document, record, record_bytes
                        )
                    },
                )

        invalid_record = copy.deepcopy(record)
        invalid_record.pop("objective")
        invalid_record, paired_result, invalid_bytes = self.paired_campaign_documents(
            invalid_record
        )
        self.assertIn(
            "RES-09",
            {
                issue.code
                for issue in self.paired_result_issues(
                    paired_result, invalid_record, invalid_bytes
                )
            },
        )

        current_mismatch = copy.deepcopy(record)
        current_mismatch["campaign"]["current_work_id"] = "ACA-GOV-002"
        current_mismatch, paired_result, mismatch_bytes = self.paired_campaign_documents(
            current_mismatch
        )
        self.assertIn(
            "RES-09",
            {
                issue.code
                for issue in self.paired_result_issues(
                    paired_result, current_mismatch, mismatch_bytes
                )
            },
        )

    def test_f02_continuation_derives_order_gate_and_history_from_record(self):
        record, result, record_bytes = self.paired_campaign_documents()
        cases = {}

        unlisted = copy.deepcopy(result)
        unlisted["next_work"]["proposed_id"] = "UNLISTED-WORK"
        cases["unlisted"] = unlisted

        wrong_position = copy.deepcopy(result)
        wrong_position["next_work"]["sequence_position"] = 3
        cases["wrong_position"] = wrong_position

        wrong_gate = copy.deepcopy(result)
        wrong_gate["next_work"]["terminal_human_gate"] = "HUMAN_GATE_OTHER"
        cases["wrong_gate"] = wrong_gate

        wrong_completed = copy.deepcopy(result)
        wrong_completed["next_work"]["completed_work_id"] = "ACA-GOV-002"
        cases["wrong_completed"] = wrong_completed

        rollback = copy.deepcopy(result)
        rollback["next_work"]["correction_history"]["dispatches"] = 0
        cases["dispatch_rollback"] = rollback

        for name, document in cases.items():
            with self.subTest(name=name):
                issues = self.paired_result_issues(document, record, record_bytes)
                self.assertIn("RES-09", {issue.code for issue in issues})

        result_created_order = copy.deepcopy(result)
        result_created_order["next_work"]["authorized_work_ids"] = [
            "ACA-GOV-001",
            "UNLISTED-WORK",
        ]
        result_created_order["next_work"]["finite_work_limit"] = 2
        schema_codes = {
            issue.code
            for issue in validator_module.schema_issues(
                result_created_order, self.result_validator
            )
        }
        self.assertIn("SCHEMA_ADDITIONALPROPERTIES", schema_codes)

    def test_f02_record_history_and_open_findings_fail_closed(self):
        mismatch = copy.deepcopy(self.campaign_record)
        mismatch["campaign"]["correction_history"]["dispatches"] = 0
        self.assertIn("WR-10", self.record_codes(mismatch))

        for flag in ("repeated_material_finding", "unresolved_findings"):
            record = copy.deepcopy(self.campaign_record)
            record["campaign"]["correction_history"][flag] = True
            record, result, record_bytes = self.paired_campaign_documents(record)
            result["next_work"]["correction_history"] = copy.deepcopy(
                record["campaign"]["correction_history"]
            )
            with self.subTest(flag=flag):
                self.assertIn(
                    "RES-09",
                    {
                        issue.code
                        for issue in self.paired_result_issues(
                            result, record, record_bytes
                        )
                    },
                )

    def test_f02_limit_campaign_requires_record_authorized_successor(self):
        limit_record = copy.deepcopy(self.campaign_record)
        limit_record["campaign"].pop("work_ids")
        limit_record["campaign"]["work_limit"] = 3
        limit_record["campaign"]["authorized_next_work_id"] = "ACA-GOV-002"
        limit_record, limit_result, limit_bytes = self.paired_campaign_documents(
            limit_record
        )
        self.assertEqual(
            [], self.paired_result_issues(limit_result, limit_record, limit_bytes)
        )

        no_successor = copy.deepcopy(limit_record)
        no_successor["campaign"].pop("authorized_next_work_id")
        no_successor, no_successor_result, no_successor_bytes = (
            self.paired_campaign_documents(no_successor)
        )
        self.assertIn(
            "RES-09",
            {
                issue.code
                for issue in self.paired_result_issues(
                    no_successor_result, no_successor, no_successor_bytes
                )
            },
        )

        exhausted = copy.deepcopy(limit_record)
        exhausted["campaign"]["current_work_position"] = 3
        exhausted, exhausted_result, exhausted_bytes = self.paired_campaign_documents(
            exhausted
        )
        exhausted_result["next_work"]["sequence_position"] = 4
        self.assertIn(
            "RES-09",
            {
                issue.code
                for issue in self.paired_result_issues(
                    exhausted_result, exhausted, exhausted_bytes
                )
            },
        )

        wrong_next = copy.deepcopy(limit_result)
        wrong_next["next_work"]["proposed_id"] = "ACA-W017"
        self.assertIn(
            "RES-09",
            {
                issue.code
                for issue in self.paired_result_issues(
                    wrong_next, limit_record, limit_bytes
                )
            },
        )

    def test_controller_merge_transition_requires_authority_proof(self):
        document = self.controller_completed_result()
        document["result_state"] = "MERGED"
        document["next_work"] = {"action": "NONE", "rule": "post-merge sync next"}
        proof = self.authority_proof(document["work_id"], document["target_sha"])
        document["transition"].update(
            {
                "from_state": "READY",
                "to_state": "MERGED",
                "authority_proof_sha256": hashlib.sha256(
                    self.authority_proof_bytes(proof)
                ).hexdigest(),
            }
        )
        self.assertEqual(
            [],
            validator_module.validate_document(
                document,
                self.result_validator,
                kind="result",
                transitions=self.transitions,
                **self.authority_validation_kwargs(proof),
            ),
        )

        document["transition"].pop("authority_proof_sha256")
        issues = validator_module.validate_document(
            document,
            self.result_validator,
            kind="result",
            transitions=self.transitions,
            **self.authority_validation_kwargs(proof),
        )
        self.assertTrue(issues)

    def test_res_07_campaign_continuation_fails_closed(self):
        cases = {}

        for role in (
            "INSTRUCTION_EVIDENCE_AUTHOR",
            "IMPLEMENTATION",
            "INDEPENDENT_AUDIT",
            "CORRECTION",
            "FRESH_REAUDIT",
        ):
            non_controller = copy.deepcopy(self.campaign_result)
            non_controller["role"] = role
            non_controller["transition"]["actor_role"] = role
            cases[f"non_controller_{role.lower()}"] = non_controller

        nonterminal = copy.deepcopy(self.campaign_result)
        nonterminal["result_state"] = "IMPLEMENTED_DRAFT_PR"
        nonterminal["transition"].update(
            {"from_state": "IMPLEMENTING", "to_state": "IMPLEMENTED_DRAFT_PR"}
        )
        cases["nonterminal"] = nonterminal

        self_referential = copy.deepcopy(self.campaign_result)
        self_referential["next_work"]["proposed_id"] = self_referential["work_id"]
        cases["self_referential"] = self_referential

        unordered = copy.deepcopy(self.campaign_result)
        unordered["next_work"]["sequence_position"] = 3
        cases["unordered"] = unordered

        exhausted = copy.deepcopy(self.campaign_result)
        exhausted["next_work"]["finite_work_limit"] = 1
        cases["exhausted"] = exhausted

        missing_gate = copy.deepcopy(self.campaign_result)
        missing_gate["next_work"]["terminal_human_gate"] = ""
        cases["missing_gate"] = missing_gate

        repeated_finding = copy.deepcopy(self.campaign_result)
        repeated_finding["next_work"]["correction_history"][
            "repeated_material_finding"
        ] = True
        cases["repeated_finding"] = repeated_finding

        unresolved_finding = copy.deepcopy(self.campaign_result)
        unresolved_finding["next_work"]["correction_history"][
            "unresolved_findings"
        ] = True
        cases["unresolved_finding"] = unresolved_finding

        for name, document in cases.items():
            with self.subTest(name=name):
                issues = self.paired_result_issues(document)
                self.assertTrue(
                    {"RES-07", "RES-09", "SCHEMA_ADDITIONALPROPERTIES"}
                    & {issue.code for issue in issues},
                    [issue.render() for issue in issues],
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

    def test_cli_ar01_accepts_exact_closed_proof_for_ready_merge_and_campaign(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            for kind, factory in (
                ("record", self.controller_lifecycle_record),
                ("result", self.controller_lifecycle_result),
            ):
                for to_state in ("READY", "MERGED"):
                    document = factory(to_state)
                    work_id = document["id"] if kind == "record" else document["work_id"]
                    proof = self.authority_proof(work_id, document["target_sha"])
                    process = self.run_authority_cli(
                        directory_path,
                        f"valid-{kind}-{to_state}",
                        kind,
                        document,
                        proof_bytes=self.authority_proof_bytes(proof),
                    )
                    with self.subTest(kind=kind, to_state=to_state):
                        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
                        self.assertIn("Orchestration validation: PASS", process.stdout)

            proof_bytes = self.authority_proof_bytes()
            proof_digest = hashlib.sha256(proof_bytes).hexdigest()
            record = copy.deepcopy(self.campaign_record)
            result = copy.deepcopy(self.campaign_result)
            record["campaign"]["authority_proof_sha256"] = proof_digest
            result["next_work"]["authority_proof_sha256"] = proof_digest
            process = self.run_authority_cli(
                directory_path,
                "valid-campaign",
                "result",
                result,
                proof_bytes=proof_bytes,
                campaign_record=record,
            )
            self.assertEqual(0, process.returncode, process.stdout + process.stderr)
            self.assertIn("Orchestration validation: PASS", process.stdout)

            document = self.controller_lifecycle_result("READY")
            non_expiring = self.authority_proof(
                document["work_id"],
                document["target_sha"],
                validity={"kind": "NON_EXPIRING"},
            )
            document["transition"]["authority_proof_sha256"] = hashlib.sha256(
                self.authority_proof_bytes(non_expiring)
            ).hexdigest()
            process = self.run_authority_cli(
                directory_path,
                "valid-non-expiring",
                "result",
                document,
                proof_bytes=self.authority_proof_bytes(non_expiring),
                evaluation_time=None,
            )
            self.assertEqual(0, process.returncode, process.stdout + process.stderr)

    def test_cli_ar01_rejects_missing_malformed_mismatched_or_expired_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            base = self.controller_lifecycle_result("READY")
            base_proof = self.authority_proof(base["work_id"], base["target_sha"])
            base_bytes = self.authority_proof_bytes(base_proof)

            missing = self.run_authority_cli(
                directory_path,
                "missing-proof",
                "result",
                copy.deepcopy(base),
                include_proof=False,
            )
            self.assertEqual(1, missing.returncode, missing.stdout + missing.stderr)

            missing_source = self.run_authority_cli(
                directory_path,
                "missing-source",
                "result",
                copy.deepcopy(base),
                proof_bytes=base_bytes,
                include_source=False,
            )
            self.assertEqual(
                1,
                missing_source.returncode,
                missing_source.stdout + missing_source.stderr,
            )

            unreadable_document = directory_path / "unreadable-result.json"
            unreadable_source = directory_path / "unreadable-source.txt"
            unreadable_document.write_text(json.dumps(base), encoding="utf-8")
            unreadable_source.write_bytes(self.AUTHORITY_SOURCE_BYTES)
            unreadable = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--kind",
                    "result",
                    "--authority-proof",
                    str(directory_path / "absent-proof.json"),
                    "--authority-source",
                    str(unreadable_source),
                    "--evaluation-time",
                    self.AUTHORITY_EVALUATION_TIME,
                    str(unreadable_document),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
            self.assertEqual(1, unreadable.returncode, unreadable.stdout + unreadable.stderr)

            raw_cases = {
                "malformed-json": b"{",
                "duplicate-key": b'{"schema_id":"ACA_AUTHORITY_PROOF","schema_id":"ACA_AUTHORITY_PROOF"}',
            }
            for name, proof_bytes in raw_cases.items():
                process = self.run_authority_cli(
                    directory_path,
                    name,
                    "result",
                    copy.deepcopy(base),
                    proof_bytes=proof_bytes,
                )
                with self.subTest(name=name):
                    self.assertEqual(1, process.returncode, process.stdout + process.stderr)

            proof_mutations = {
                "unknown-property": ("extra", True),
                "wrong-schema": ("schema_id", "OTHER"),
                "wrong-version": ("version", "2.0"),
                "wrong-kind": ("authority_kind", "SYSTEM_ASSERTION"),
                "non-grant": ("human_decision", "DENY"),
                "non-current": ("lifecycle_state", "CANDIDATE"),
                "wrong-repository": ("repository", "other/repository"),
                "wrong-work": ("work_id", "OTHER-WORK"),
                "wrong-head": ("target_sha", "d" * 40),
                "wrong-executor": ("executor_role", "EXTERNAL_SYSTEM"),
                "wrong-transition": ("covered_transitions", ["MERGED"]),
                "empty-coverage": ("covered_transitions", []),
                "duplicate-coverage": ("covered_transitions", ["READY", "READY"]),
                "unknown-coverage": ("covered_transitions", ["READY", "DEPLOY"]),
            }
            for name, (field, value) in proof_mutations.items():
                proof = copy.deepcopy(base_proof)
                proof[field] = value
                proof_bytes = self.authority_proof_bytes(proof)
                document = copy.deepcopy(base)
                document["transition"]["authority_proof_sha256"] = hashlib.sha256(
                    proof_bytes
                ).hexdigest()
                process = self.run_authority_cli(
                    directory_path,
                    name,
                    "result",
                    document,
                    proof_bytes=proof_bytes,
                )
                with self.subTest(name=name):
                    self.assertEqual(1, process.returncode, process.stdout + process.stderr)

            non_human_source = copy.deepcopy(base_proof)
            non_human_source["source"]["kind"] = "AUTOMATION_OUTPUT"
            malformed_source_digest = copy.deepcopy(base_proof)
            malformed_source_digest["source"]["sha256"] = "invalid"
            for name, proof in (
                ("non-human-source", non_human_source),
                ("malformed-source-digest", malformed_source_digest),
            ):
                proof_bytes = self.authority_proof_bytes(proof)
                document = copy.deepcopy(base)
                document["transition"]["authority_proof_sha256"] = hashlib.sha256(
                    proof_bytes
                ).hexdigest()
                process = self.run_authority_cli(
                    directory_path, name, "result", document, proof_bytes=proof_bytes
                )
                with self.subTest(name=name):
                    self.assertEqual(1, process.returncode, process.stdout + process.stderr)

            digest_mismatch = copy.deepcopy(base)
            digest_mismatch["transition"]["authority_proof_sha256"] = "0" * 64
            process = self.run_authority_cli(
                directory_path,
                "proof-digest-mismatch",
                "result",
                digest_mismatch,
                proof_bytes=base_bytes,
            )
            self.assertEqual(1, process.returncode, process.stdout + process.stderr)

            source_mismatch = self.run_authority_cli(
                directory_path,
                "source-digest-mismatch",
                "result",
                copy.deepcopy(base),
                proof_bytes=base_bytes,
                source_bytes=b"different source bytes\n",
            )
            self.assertEqual(1, source_mismatch.returncode, source_mismatch.stdout + source_mismatch.stderr)

            expired = self.run_authority_cli(
                directory_path,
                "expired",
                "result",
                copy.deepcopy(base),
                proof_bytes=base_bytes,
                evaluation_time="2026-12-31T00:00:00Z",
            )
            self.assertEqual(1, expired.returncode, expired.stdout + expired.stderr)

            missing_evaluation_time = self.run_authority_cli(
                directory_path,
                "missing-evaluation-time",
                "result",
                copy.deepcopy(base),
                proof_bytes=base_bytes,
                evaluation_time=None,
            )
            self.assertEqual(
                1,
                missing_evaluation_time.returncode,
                missing_evaluation_time.stdout + missing_evaluation_time.stderr,
            )

    def test_cli_ar01_generic_prose_neither_grants_nor_denies_authority(self):
        phrases = (
            "Approval is pending.",
            "Awaiting Human acceptance.",
            "Human acceptance has not yet been granted.",
            "This authority is not yet effective.",
            "Draft delegation.",
            "This authority is disabled.",
        )
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            for index, phrase in enumerate(phrases):
                document = self.controller_lifecycle_result("READY")
                document["evidence"][0]["proves"] = phrase
                proof = self.authority_proof(document["work_id"], document["target_sha"])
                proof_bytes = self.authority_proof_bytes(proof)

                without_proof = self.run_authority_cli(
                    directory_path,
                    f"phrase-{index}-absent",
                    "result",
                    copy.deepcopy(document),
                    include_proof=False,
                )
                with_proof = self.run_authority_cli(
                    directory_path,
                    f"phrase-{index}-present",
                    "result",
                    copy.deepcopy(document),
                    proof_bytes=proof_bytes,
                )
                with self.subTest(phrase=phrase):
                    self.assertEqual(1, without_proof.returncode, without_proof.stdout + without_proof.stderr)
                    self.assertEqual(0, with_proof.returncode, with_proof.stdout + with_proof.stderr)

        self.assertFalse(hasattr(validator_module, "NEGATIVE_AUTHORITY_WORDING"))
        predicate_code = validator_module.authority_proof_issues.__code__
        self.assertNotIn("re", predicate_code.co_names)
        self.assertNotIn("search", predicate_code.co_names)
        predicate_constants = {
            value for value in predicate_code.co_consts if isinstance(value, str)
        }
        self.assertTrue(
            {"reference", "proves", "description", "notes", "reason"}.isdisjoint(
                predicate_constants
            )
        )

    def test_cli_f02_enforces_paired_campaign_authority(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def serialized_pair(record, result):
            record_bytes = (json.dumps(record, indent=2) + "\n").encode("utf-8")
            result = copy.deepcopy(result)
            result["next_work"]["campaign_record_sha256"] = hashlib.sha256(
                record_bytes
            ).hexdigest()
            return record_bytes, result

        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            proof_path = directory_path / "campaign-proof.json"
            source_path = directory_path / "campaign-source.txt"
            proof_path.write_bytes(self.authority_proof_bytes())
            source_path.write_bytes(self.AUTHORITY_SOURCE_BYTES)

            def run_pair(name, record, result, expected_returncode=1):
                record_bytes, bound_result = serialized_pair(record, result)
                record_path = directory_path / f"{name}-record.json"
                result_path = directory_path / f"{name}-result.json"
                record_path.write_bytes(record_bytes)
                result_path.write_text(json.dumps(bound_result), encoding="utf-8")
                process = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPT),
                        "--kind",
                        "result",
                        "--campaign-record",
                        str(record_path),
                        "--authority-proof",
                        str(proof_path),
                        "--authority-source",
                        str(source_path),
                        "--evaluation-time",
                        self.AUTHORITY_EVALUATION_TIME,
                        str(result_path),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )
                observed = process.stdout + process.stderr
                self.assertEqual(expected_returncode, process.returncode, observed)
                if expected_returncode:
                    self.assertNotIn("Orchestration validation: PASS", observed)
                else:
                    self.assertIn("Orchestration validation: PASS", process.stdout)
                return observed

            record = copy.deepcopy(self.campaign_record)
            result = copy.deepcopy(self.campaign_result)
            self.assertIn("PASS", run_pair("valid", record, result, 0))

            result_path = directory_path / "missing-pair-result.json"
            result_path.write_text(json.dumps(result), encoding="utf-8")
            missing = subprocess.run(
                [sys.executable, str(SCRIPT), "--kind", "result", "--authority-proof", str(proof_path), "--authority-source", str(source_path), "--evaluation-time", self.AUTHORITY_EVALUATION_TIME, str(result_path)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(1, missing.returncode, missing.stdout + missing.stderr)
            self.assertIn("RES-09", missing.stderr)

            unreadable = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--kind",
                    "result",
                    "--campaign-record",
                    str(directory_path / "absent-record.json"),
                    "--authority-proof",
                    str(proof_path),
                    "--authority-source",
                    str(source_path),
                    "--evaluation-time",
                    self.AUTHORITY_EVALUATION_TIME,
                    str(result_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(1, unreadable.returncode, unreadable.stdout + unreadable.stderr)
            self.assertIn("RES-09", unreadable.stderr)

            digest_record_bytes, digest_result = serialized_pair(record, result)
            digest_result["next_work"]["campaign_record_sha256"] = "0" * 64
            digest_record_path = directory_path / "digest-record.json"
            digest_result_path = directory_path / "digest-result.json"
            digest_record_path.write_bytes(digest_record_bytes)
            digest_result_path.write_text(json.dumps(digest_result), encoding="utf-8")
            digest_process = subprocess.run(
                [sys.executable, str(SCRIPT), "--kind", "result", "--campaign-record", str(digest_record_path), "--authority-proof", str(proof_path), "--authority-source", str(source_path), "--evaluation-time", self.AUTHORITY_EVALUATION_TIME, str(digest_result_path)],
                capture_output=True, text=True, check=False, env=env,
            )
            self.assertEqual(1, digest_process.returncode, digest_process.stdout + digest_process.stderr)
            self.assertIn("RES-09", digest_process.stderr)

            adversarial_results = {}
            unlisted = copy.deepcopy(result)
            unlisted["next_work"]["proposed_id"] = "UNLISTED-WORK"
            adversarial_results["unlisted"] = (record, unlisted)
            replaced = copy.deepcopy(result)
            replaced["next_work"]["authorized_work_ids"] = ["ACA-GOV-001", "UNLISTED-WORK"]
            replaced["next_work"]["finite_work_limit"] = 2
            adversarial_results["result-order"] = (record, replaced)
            wrong_position = copy.deepcopy(result)
            wrong_position["next_work"]["sequence_position"] = 3
            adversarial_results["position"] = (record, wrong_position)
            wrong_gate = copy.deepcopy(result)
            wrong_gate["next_work"]["terminal_human_gate"] = "HUMAN_GATE_OTHER"
            adversarial_results["gate"] = (record, wrong_gate)
            wrong_completed = copy.deepcopy(result)
            wrong_completed["next_work"]["completed_work_id"] = "ACA-GOV-002"
            adversarial_results["completed"] = (record, wrong_completed)
            rollback = copy.deepcopy(result)
            rollback["next_work"]["correction_history"]["dispatches"] = 0
            adversarial_results["rollback"] = (record, rollback)
            repo_mismatch = copy.deepcopy(result)
            repo_mismatch["repository"] = "other/repository"
            repo_mismatch["transition"]["repository"] = "other/repository"
            adversarial_results["repository"] = (record, repo_mismatch)
            branch_mismatch = copy.deepcopy(result)
            branch_mismatch["branch"] = "other/branch"
            branch_mismatch["transition"]["branch"] = "other/branch"
            adversarial_results["branch"] = (record, branch_mismatch)
            target_mismatch = copy.deepcopy(result)
            target_mismatch["target_sha"] = "d" * 40
            target_mismatch["transition"]["target_sha"] = "d" * 40
            adversarial_results["target"] = (record, target_mismatch)

            invalid_record = copy.deepcopy(record)
            invalid_record.pop("objective")
            adversarial_results["record-schema"] = (invalid_record, result)
            current_mismatch = copy.deepcopy(record)
            current_mismatch["campaign"]["current_work_id"] = "ACA-GOV-002"
            adversarial_results["current-work"] = (current_mismatch, result)
            history_mismatch = copy.deepcopy(record)
            history_mismatch["campaign"]["correction_history"]["dispatches"] = 0
            adversarial_results["history"] = (history_mismatch, result)
            for flag in ("repeated_material_finding", "unresolved_findings"):
                flagged_record = copy.deepcopy(record)
                flagged_record["campaign"]["correction_history"][flag] = True
                flagged_result = copy.deepcopy(result)
                flagged_result["next_work"]["correction_history"] = copy.deepcopy(
                    flagged_record["campaign"]["correction_history"]
                )
                adversarial_results[flag] = (flagged_record, flagged_result)

            limit_record = copy.deepcopy(record)
            limit_record["campaign"].pop("work_ids")
            limit_record["campaign"]["work_limit"] = 3
            limit_record["campaign"]["authorized_next_work_id"] = "ACA-GOV-002"
            self.assertIn("PASS", run_pair("limit-valid", limit_record, result, 0))
            no_next = copy.deepcopy(limit_record)
            no_next["campaign"].pop("authorized_next_work_id")
            adversarial_results["limit-no-next"] = (no_next, result)
            exhausted = copy.deepcopy(limit_record)
            exhausted["campaign"]["current_work_position"] = 3
            exhausted_result = copy.deepcopy(result)
            exhausted_result["next_work"]["sequence_position"] = 4
            adversarial_results["limit-exhausted"] = (exhausted, exhausted_result)
            wrong_next = copy.deepcopy(result)
            wrong_next["next_work"]["proposed_id"] = "ACA-W017"
            adversarial_results["limit-wrong-next"] = (limit_record, wrong_next)

            for name, (case_record, case_result) in adversarial_results.items():
                with self.subTest(name=name):
                    observed = run_pair(name, case_record, case_result)
                    self.assertTrue(
                        "RES-09" in observed or "SCHEMA_ADDITIONALPROPERTIES" in observed,
                        observed,
                    )

    def test_core_cli_valid_campaign(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            proof_path = temporary_path / "authority-proof.json"
            source_path = temporary_path / "authority-source.txt"
            proof_path.write_bytes(self.authority_proof_bytes())
            source_path.write_bytes(self.AUTHORITY_SOURCE_BYTES)
            for kind, directory in (("record", "records/valid"), ("result", "results/valid")):
                with self.subTest(kind=kind):
                    command = [
                        sys.executable,
                        str(SCRIPT),
                        "--kind",
                        kind,
                        "--authority-proof",
                        str(proof_path),
                        "--authority-source",
                        str(source_path),
                        "--evaluation-time",
                        self.AUTHORITY_EVALUATION_TIME,
                    ]
                    if kind == "result":
                        command.extend(
                            [
                                "--campaign-record",
                                str(FIXTURES / "records/valid/campaign-active.json"),
                            ]
                        )
                    command.extend(map(str, sorted((FIXTURES / directory).glob("*.json"))))
                    result = subprocess.run(
                        command,
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
