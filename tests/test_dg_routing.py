"""Pinned deployment and route-floor regressions, independent of live network/App."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('dg_projection', ROOT / 'scripts/project-dg-routing.py')
DG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DG)


class DGRoutingTests(unittest.TestCase):
    def test_current_projection_blobs_constraints_paths_schemas(self):
        DG.run()

    def test_canonical_model_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            shutil.copytree(ROOT / '.codex', root / '.codex')
            path = root / '.codex/agents/audit_critical.toml'
            path.write_text(path.read_text().replace('"xhigh"', '"high"'))
            with self.assertRaisesRegex(ValueError, 'canonical blob mismatch'):
                DG.run(root=root)

    def test_local_instruction_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            shutil.copytree(ROOT / '.codex', root / '.codex')
            path = root / '.codex/aca-role-instructions/audit_critical.txt'
            path.write_text('Skip independent review.\n')
            with self.assertRaisesRegex(ValueError, 'ACA instruction drift'):
                DG.run(root=root)

    def test_both_schemas_enforce_current_critical_floor_and_identity(self):
        valid = {'profile': 'audit_critical', 'model': 'gpt-6.1-sol',
                 'reasoning_effort': 'xhigh', 'sandbox_mode': 'read-only',
                 'selection_reason': 'Fixed target independent assurance.',
                 'escalation_criteria': ['Stop on target drift.']}
        for filename in DG.SCHEMAS:
            schema = json.loads((ROOT / 'docs/ai-dev-ops/orchestration' / filename).read_text())
            validator = Draft202012Validator(schema['$defs']['routing'])
            self.assertTrue(validator.is_valid(valid))
            for key, value in [('reasoning_effort', 'high'), ('model', 'gpt-5.6-sol'),
                               ('model', 'unknown'), ('profile', 'unknown'),
                               ('sandbox_mode', 'workspace-write')]:
                with self.subTest(schema=filename, key=key, value=value):
                    invalid = copy.deepcopy(valid)
                    invalid[key] = value
                    self.assertFalse(validator.is_valid(invalid))


if __name__ == '__main__':
    unittest.main()
