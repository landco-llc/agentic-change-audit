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
            issue.code for issue in validator_module.result_semantic_issues(document)
        }

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

    def test_wr_06_correction_cycles(self):
        document = copy.deepcopy(self.correction_record)
        document["state_history"][0]["correction_cycle"] = 0
        self.assertIn("WR-06", self.record_codes(document))

    def test_wr_07_separated_roles(self):
        document = copy.deepcopy(self.auditing_record)
        document["state_history"][0]["actor_role"] = "IMPLEMENTATION"
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

    def test_res_04_role_output(self):
        document = copy.deepcopy(self.result)
        document["role"] = "IMPLEMENTATION"
        document["transition"]["actor_role"] = "IMPLEMENTATION"
        self.assertIn("RES-04", self.result_codes(document))

    def test_res_05_progression_scope_checks_next_work_and_actor(self):
        document = copy.deepcopy(self.result)
        document["scope_observation"]["allowed_scope_only"] = False
        document["checks"][0]["status"] = "FAILED"
        document["next_work"] = {"action": "NONE", "rule": "none", "proposed_id": "ACA-NEXT"}
        document["transition"]["actor_role"] = "FRESH_REAUDIT"
        self.assertIn("RES-05", self.result_codes(document))

    def test_schema_format_family(self):
        document = copy.deepcopy(self.record)
        document["requirements_basis"]["observed_at"] = "not-a-date"
        self.assertIn("SCHEMA_FORMAT", {issue.code for issue in validator_module.schema_issues(document, self.record_validator)})

    def test_core_cli_valid_campaign(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--kind", "record", *map(str, sorted((FIXTURES / "records/valid").glob("*.json")))],
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


if __name__ == "__main__":
    unittest.main()
