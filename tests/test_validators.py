from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


audit_validator = load_module(
    "validate_audit_result",
    ROOT / "scripts/validate-audit-result.py",
)
skill_validator = load_module(
    "validate_skill",
    ROOT / "scripts/validate-skill.py",
)


class AuditResultValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = audit_validator.load_json(ROOT / "standard/output-schema.json")
        cls.validator = audit_validator.build_validator(cls.schema)
        cls.base = audit_validator.load_json(
            ROOT / "tests/fixtures/valid-full.json"
        )

    def issues(self, document):
        return audit_validator.validate_document(
            document,
            self.validator,
            schema_only=False,
        )

    def codes(self, document):
        return {issue.code for issue in self.issues(document)}

    def test_invalid_datetime_is_rejected(self):
        document = copy.deepcopy(self.base)
        document["audited_at"] = "not-a-date"
        self.assertIn("SCHEMA_FORMAT", self.codes(document))

    def test_not_auditable_can_record_unexecuted_required_check(self):
        document = audit_validator.load_json(
            ROOT
            / "tests/fixtures/valid-not-auditable-required-check-not-run.json"
        )
        self.assertEqual([], self.issues(document))

    def test_blocked_can_record_unexecuted_required_check(self):
        document = audit_validator.load_json(
            ROOT / "tests/fixtures/valid-blocked-required-check-not-run.json"
        )
        self.assertEqual([], self.issues(document))

    def test_changes_requested_can_record_blocking_finding(self):
        document = audit_validator.load_json(
            ROOT / "tests/fixtures/valid-changes-requested-blocking.json"
        )
        self.assertEqual([], self.issues(document))

    def test_expected_issue_cannot_be_replaced_by_unrelated_schema_error(self):
        document = audit_validator.load_json(
            ROOT / "tests/fixtures/invalid-required-check-not-run.json"
        )
        document["evidence"]["checks_not_executed"][0]["required"] = False
        document["language"] = 7
        issues = self.issues(document)
        matched, missing = audit_validator.expectations_satisfied(
            issues,
            [
                {
                    "code": "PASS_REQUIRED_CHECK_NOT_RUN",
                    "path": "$.evidence.checks_not_executed[0].required",
                }
            ],
        )
        self.assertFalse(matched)
        self.assertTrue(missing)


class MarkdownReferenceTests(unittest.TestCase):
    def validate(self, root: Path, source: Path):
        return skill_validator.validate_markdown_references(
            root,
            source,
            source.read_text(encoding="utf-8"),
            {},
        )

    def test_commonmark_links_images_references_titles_and_fragments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "assets").mkdir()
            (root / "assets/image(test).png").write_bytes(b"png")
            (root / "target.md").write_text(
                "# Target Heading\n\n## Target Heading\n",
                encoding="utf-8",
            )
            source = root / "source.md"
            source.write_text(
                "\n".join(
                    [
                        "# Source Heading",
                        "",
                        '[Inline](target.md "Human-readable title")',
                        "![Image](<assets/image(test).png>)",
                        "[Reference][target-ref]",
                        "[Angle](<target.md>)",
                        "[Local fragment](#source-heading)",
                        "[First heading](target.md#target-heading)",
                        "[Duplicate heading](target.md#target-heading-1)",
                        "",
                        '[target-ref]: target.md#target-heading "Reference title"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual([], self.validate(root, source))

    def test_missing_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "![Missing](missing.png)\n",
                encoding="utf-8",
            )
            errors = self.validate(root, source)
            self.assertTrue(any("does not exist" in error for error in errors))

    def test_unresolved_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "[Missing][no-such-reference]\n",
                encoding="utf-8",
            )
            errors = self.validate(root, source)
            self.assertTrue(
                any("unresolved reference-style link" in error for error in errors)
            )

    def test_unresolved_reference_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "![Missing image][no-such-reference]\n",
                encoding="utf-8",
            )
            errors = self.validate(root, source)
            self.assertTrue(
                any("unresolved reference-style link" in error for error in errors)
            )

    def test_inline_code_reference_syntax_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "`[Inline example][missing-inline-definition]`\n",
                encoding="utf-8",
            )
            self.assertEqual([], self.validate(root, source))

    def test_fenced_code_reference_syntax_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "```md\n[Fenced example][missing-fenced-definition]\n```\n",
                encoding="utf-8",
            )
            self.assertEqual([], self.validate(root, source))

    def test_indented_code_reference_syntax_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "    [Indented example][missing-indented-definition]\n",
                encoding="utf-8",
            )
            self.assertEqual([], self.validate(root, source))

    def test_escaped_reference_syntax_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "\\[Escaped example][missing-escaped-definition]\n",
                encoding="utf-8",
            )
            self.assertEqual([], self.validate(root, source))

    def test_escaped_reference_image_syntax_is_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "\\![Escaped image][missing-image-definition]\n",
                encoding="utf-8",
            )
            self.assertEqual([], self.validate(root, source))

    def test_missing_fragment_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text(
                "# Present\n\n[Missing](#absent)\n",
                encoding="utf-8",
            )
            errors = self.validate(root, source)
            self.assertTrue(any("heading does not exist" in error for error in errors))

    def test_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            root.mkdir()
            outside = Path(temp) / "outside.md"
            outside.write_text("# Outside\n", encoding="utf-8")
            (root / "escape.md").symlink_to(outside)
            source = root / "source.md"
            source.write_text("[Escape](escape.md)\n", encoding="utf-8")
            errors = self.validate(root, source)
            self.assertTrue(any("escapes the skill root" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
