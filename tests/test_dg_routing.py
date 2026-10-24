"""Pinned deployment and route-floor regressions, independent of live network/App."""
import copy
import contextlib
import io
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


class DGProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / '.codex/dg-routing-source.json').read_text())
        self.pin = self.manifest['source_commit']
        self.trusted_commit = {'sha': self.pin, 'tree': {'sha': self.manifest['source_tree']}}
        self.trusted_tree = {
            'sha': self.manifest['source_tree'], 'truncated': False,
            'tree': [{'path': e['source_path'], 'sha': e['source_blob'],
                      'type': 'blob', 'mode': '100644'} for e in self.manifest['roles'].values()],
        }

    def trusted_fetch(self, endpoint):
        # Deterministic stand-in for independently retrieved trusted API metadata;
        # mutations to a test candidate never update these baseline responses.
        if '/commits/' in endpoint:
            return copy.deepcopy(self.trusted_commit)
        return copy.deepcopy(self.trusted_tree)

    def test_independent_commit_tree_membership_verifies_current_source(self):
        DG.verify_source(self.manifest, self.pin, self.trusted_fetch)

    def test_missing_or_malformed_identity_rejected_offline(self):
        for key in ('source_repository', 'source_commit', 'source_tree'):
            invalid = copy.deepcopy(self.manifest)
            invalid.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                DG.validate_identity(invalid)

    def test_forged_identity_rejected_against_external_authority_and_remote(self):
        for key, value in [('source_repository', 'attacker/forged'),
                           ('source_commit', '0' * 40), ('source_tree', '0' * 40)]:
            invalid = copy.deepcopy(self.manifest)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                DG.validate_identity(invalid)
                DG.verify_source(invalid, self.pin, self.trusted_fetch)

    def test_external_expected_commit_required(self):
        with self.assertRaisesRegex(ValueError, 'external accepted source commit'):
            DG.verify_source(self.manifest, None, self.trusted_fetch)

    def test_incomplete_or_forged_remote_tree_rejected(self):
        for field, value in [('truncated', True), ('sha', '0' * 40)]:
            self.trusted_tree[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                DG.verify_source(self.manifest, self.pin, self.trusted_fetch)
            self.setUp()

    def test_missing_role_membership_rejected(self):
        invalid = copy.deepcopy(self.manifest)
        invalid['roles'].pop('audit_critical')
        with self.assertRaisesRegex(ValueError, 'inventory differs'):
            DG.verify_source(invalid, self.pin, self.trusted_fetch)

    def test_coordinated_lower_route_blob_and_schema_cannot_verify_source(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            shutil.copytree(ROOT / '.codex', root / '.codex')
            target = root / '.codex/agents/audit_critical.toml'
            text = target.read_text().replace('gpt-6.1-sol', 'gpt-5.6-sol').replace('"xhigh"', '"high"')
            target.write_text(text)
            entry = self.manifest['roles']['audit_critical']
            overlay = (root / entry['local_instructions']).read_text()
            suffix = DG.MARKER + overlay + '"""\n'
            forged_source = (text[:-len(suffix)] + '"""\n').encode()
            forged_manifest = copy.deepcopy(self.manifest)
            forged_manifest['roles']['audit_critical']['source_blob'] = DG.git_blob(forged_source)
            (root / '.codex/dg-routing-source.json').write_text(json.dumps(forged_manifest))
            roles = {}
            for role_name, item in forged_manifest['roles'].items():
                import tomllib
                roles[role_name] = tomllib.loads((root / item['source_path']).read_text())
            for filename in DG.SCHEMAS:
                path = root / 'docs/ai-dev-ops/orchestration' / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                schema = json.loads((ROOT / 'docs/ai-dev-ops/orchestration' / filename).read_text())
                schema['$defs']['routing'] = DG.routing_schema(roles)
                path.write_text(json.dumps(schema))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                DG.run(root=root)
            self.assertIn('CONSISTENCY_ONLY', output.getvalue())
            self.assertNotIn('CANONICAL_SOURCE_VERIFIED', output.getvalue())
            self.assertNotIn('PASS', output.getvalue())
            with self.assertRaisesRegex(ValueError, 'trusted tree membership'):
                DG.run(root=root, accepted_source_commit=self.pin, fetch_json=self.trusted_fetch)

    def test_regeneration_without_trusted_provenance_rejected_before_writes(self):
        with self.assertRaisesRegex(ValueError, 'Regeneration requires trusted'):
            DG.run(source_dir=Path('unused'))


if __name__ == '__main__':
    unittest.main()
