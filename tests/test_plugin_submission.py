from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

VALIDATE_SUBMISSION_SCRIPT = ROOT / "scripts/validate-plugin-submission.py"
MANIFEST_PATH = ROOT / "plugins/agentic-change-audit/.codex-plugin/plugin.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


submission_module = load_module("validate_plugin_submission", VALIDATE_SUBMISSION_SCRIPT)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_repo(temp: str) -> Path:
    """Copy the working repository so a mutation test can break one thing
    without touching the real tree. The submission validator shells out to
    validate-codex-plugin.py, which needs the whole Plugin tree present.
    """
    root = Path(temp) / "repo"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns(".git"), symlinks=True)
    return root


def run_validator(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, str(root / "scripts/validate-plugin-submission.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def mutate_listing(root: Path, key: str, value) -> None:
    path = root / submission_module.LISTING_RELATIVE
    listing = load_json(path)
    listing[key] = value
    path.write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")


def claim_flagged(text: str) -> bool:
    """Mirror the validator's clause-level claim rule for wording-level tests."""
    for clause in submission_module.CLAUSE_SPLIT_PATTERN.split(text):
        stripped = clause.strip()
        if not stripped:
            continue
        if submission_module.NEGATION_PATTERN.search(stripped):
            continue
        if any(pattern.search(stripped) for pattern in submission_module.CLAIM_PATTERNS):
            return True
    return False


def append_text(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def remove_text(root: Path, relative: str, needle: str) -> None:
    path = root / relative
    original = path.read_text(encoding="utf-8")
    if needle not in original:
        raise AssertionError(f"{relative} does not contain the text to remove: {needle!r}")
    path.write_text(original.replace(needle, ""), encoding="utf-8")


class SubmissionPackageTests(unittest.TestCase):
    def test_submission_package_passes(self):
        result = subprocess.run(
            [PYTHON, str(VALIDATE_SUBMISSION_SCRIPT), "--root", str(ROOT)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Plugin submission validation: PASS", result.stdout)

    def test_listing_contract(self):
        listing = load_json(ROOT / submission_module.LISTING_RELATIVE)

        self.assertEqual(set(listing), submission_module.EXPECTED_LISTING_KEYS)
        self.assertEqual(listing["submissionType"], "skills-only")
        self.assertEqual(listing["pluginName"], "Agentic Change Audit")
        self.assertEqual(listing["publisher"], "L&Co.LLC")
        self.assertEqual(listing["category"], "Productivity")
        self.assertEqual(listing["releaseStatus"], "draft-materials-only")
        self.assertEqual(listing["publicDirectoryStatus"], "not-submitted")
        self.assertEqual(listing["logoStatus"], "PENDING APPROVED ASSET")
        self.assertEqual(
            listing["developerIdentity"],
            {
                "type": "business",
                "name": "L&Co.LLC",
                "verificationStatus": "PENDING HUMAN CHECK",
            },
        )
        self.assertEqual(
            listing["skills"],
            [
                {
                    "name": "agentic-change-audit",
                    "path": "plugins/agentic-change-audit/skills/agentic-change-audit",
                }
            ],
        )

        for key in submission_module.URL_LISTING_KEYS:
            self.assertTrue(
                listing[key].startswith("https://"), f"{key} must be an HTTPS URL"
            )

    def test_exact_five_starter_prompts(self):
        document = load_json(ROOT / submission_module.STARTER_PROMPTS_RELATIVE)
        prompts = document["starterPrompts"]

        self.assertEqual(len(prompts), 5)
        self.assertEqual(len({prompt["id"] for prompt in prompts}), 5)

        for prompt in prompts:
            self.assertEqual(set(prompt), set(submission_module.STARTER_PROMPT_FIELDS))
            self.assertIn(prompt["expectedMode"], submission_module.VALID_MODES)
            for field in submission_module.STARTER_PROMPT_FIELDS:
                self.assertTrue(prompt[field].strip(), f"{prompt['id']}.{field} is empty")

    def test_exact_five_positive_three_negative(self):
        document = load_json(ROOT / submission_module.TEST_CASES_RELATIVE)
        cases = document["testCases"]

        self.assertEqual(len(cases), 8)
        self.assertEqual(sum(1 for case in cases if case["type"] == "positive"), 5)
        self.assertEqual(sum(1 for case in cases if case["type"] == "negative"), 3)

        for case in cases:
            self.assertEqual(set(case), set(submission_module.TEST_CASE_FIELDS))
            for field in submission_module.TEST_CASE_FIELDS:
                self.assertTrue(case[field].strip(), f"{case['id']}.{field} is empty")

    def test_unique_test_ids(self):
        cases = load_json(ROOT / submission_module.TEST_CASES_RELATIVE)["testCases"]
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)), f"duplicate test case id in {ids}")

    def test_missing_required_file_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            (root / submission_module.PRIVACY_RELATIVE).unlink()

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("Required submission file is missing", result.stderr)

    def test_wrong_publisher_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            mutate_listing(root, "publisher", "Someone Else")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("listing.json publisher", result.stderr)

    def test_submitted_status_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            mutate_listing(root, "publicDirectoryStatus", "submitted")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("listing.json publicDirectoryStatus", result.stderr)

    def test_verified_identity_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            mutate_listing(
                root,
                "developerIdentity",
                {"type": "business", "name": "L&Co.LLC", "verificationStatus": "VERIFIED"},
            )

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("developerIdentity.verificationStatus", result.stderr)

    def test_logo_ready_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            mutate_listing(root, "logoStatus", "APPROVED")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("listing.json logoStatus", result.stderr)

    def test_private_path_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.VISUAL_ASSETS_RELATIVE
            path.write_text(
                path.read_text(encoding="utf-8")
                + "\nDraft asset: /Users/example-person/Desktop/logo-draft.png\n",
                encoding="utf-8",
            )

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("contains a private local path", result.stderr)

    def test_email_address_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.SUPPORT_RELATIVE
            path.write_text(
                path.read_text(encoding="utf-8") + "\nContact: person@example.com\n",
                encoding="utf-8",
            )

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("contains an email address", result.stderr)

    def test_example_invalid_address_is_allowed(self):
        cases = load_json(ROOT / submission_module.TEST_CASES_RELATIVE)["testCases"]
        addresses = submission_module.EMAIL_PATTERN.findall(json.dumps(cases))

        for address in addresses:
            self.assertTrue(
                address.lower().endswith("@example.invalid"),
                f"test fixture address must use example.invalid: {address}",
            )

    def test_secret_like_value_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            fake_token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0"
            path = root / submission_module.RELEASE_NOTES_RELATIVE
            path.write_text(
                path.read_text(encoding="utf-8") + f"\nUpload token: {fake_token}\n",
                encoding="utf-8",
            )

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("contains a secret-like value", result.stderr)

    def test_invalid_test_count_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.TEST_CASES_RELATIVE
            document = load_json(path)
            document["testCases"] = document["testCases"][:-1]
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("must contain exactly 8 test cases", result.stderr)

    def test_duplicate_test_id_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.TEST_CASES_RELATIVE
            document = load_json(path)
            document["testCases"][1]["id"] = document["testCases"][0]["id"]
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("duplicate id", result.stderr)

    def test_release_notes_public_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.RELEASE_NOTES_RELATIVE
            path.write_text(
                path.read_text(encoding="utf-8")
                + "\nThis Plugin is now stable and publicly available in the "
                "OpenAI Plugins Directory.\n",
                encoding="utf-8",
            )

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("must not claim", result.stderr)
            self.assertIn("is now stable", result.stderr)

    def test_availability_decided_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.AVAILABILITY_RELATIVE
            availability = load_json(path)
            availability["status"] = "DECIDED"
            path.write_text(json.dumps(availability, indent=2) + "\n", encoding="utf-8")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("availability.json status", result.stderr)

    def test_human_prerequisite_completion_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.HUMAN_PREREQUISITES_RELATIVE
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "| 3 | L&Co.LLC business identity verification | PENDING HUMAN CHECK |",
                    "| 3 | L&Co.LLC business identity verification | COMPLETE |",
                ),
                encoding="utf-8",
            )

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("must equal 'PENDING HUMAN CHECK' exactly", result.stderr)

    def test_manifest_runtime_boundary_unchanged(self):
        manifest = load_json(MANIFEST_PATH)

        self.assertEqual(manifest["version"], "0.1.0-dev.1")
        self.assertEqual(manifest["interface"]["capabilities"], ["Read"])

        for key in submission_module.FORBIDDEN_MANIFEST_KEYS:
            self.assertNotIn(key, json.dumps(manifest))

        # The submission package must not silently relax the boundary either.
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.MANIFEST_RELATIVE
            mutated = load_json(path)
            mutated["interface"]["capabilities"] = ["Read", "Write"]
            path.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")

            result = run_validator(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("plugin.json interface.capabilities", result.stderr)


class HardenedValidationTests(unittest.TestCase):
    """Regression tests for the five mutations an independent audit found
    the first validator false-PASSing, plus the false-positive controls that
    keep the hardening honest.
    """

    def snapshot(self) -> dict[str, str]:
        digests = {}
        for relative in submission_module.SCANNED_FILES:
            path = ROOT / relative
            digests[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return digests

    def setUp(self):
        self.before = self.snapshot()

    def tearDown(self):
        self.assertEqual(
            self.before, self.snapshot(), "a mutation test modified the real repository"
        )

    def assert_rejected(self, result: subprocess.CompletedProcess, needle: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)
        # A caller must never see a PASS line alongside a nonzero exit.
        self.assertNotIn("Plugin submission validation: PASS", result.stdout)
        self.assertNotIn("Plugin submission validation: PASS", result.stderr)

    def test_release_claim_after_negation_connector_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.RELEASE_NOTES_RELATIVE,
                "\nNo approval has occurred, but this Plugin is published.\n",
            )

            self.assert_rejected(run_validator(root), "must not claim")

    def test_submission_readme_public_availability_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.SUBMISSION_README_RELATIVE,
                "\nThis Plugin is publicly available from OpenAI's public Plugins Directory.\n",
            )

            self.assert_rejected(run_validator(root), "must not claim")

    def test_plugin_readme_public_availability_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.PLUGIN_README_RELATIVE,
                "\nThis Plugin is publicly available from OpenAI's public Plugins Directory.\n",
            )

            result = run_validator(root)

            self.assert_rejected(result, "must not claim")
            self.assertIn(submission_module.PLUGIN_README_RELATIVE, result.stderr)

    def test_plugin_readme_ja_public_availability_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.PLUGIN_README_JA_RELATIVE,
                "\nこのPluginはOpenAIの公開Plugins Directoryから利用可能です。\n",
            )

            result = run_validator(root)

            self.assert_rejected(result, "must not claim")
            self.assertIn(submission_module.PLUGIN_README_JA_RELATIVE, result.stderr)

    def test_plugin_readme_zh_hant_public_availability_claim_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
                "\n本 Plugin 已在 OpenAI 的公開 Plugins Directory 上架。\n",
            )

            result = run_validator(root)

            self.assert_rejected(result, "must not claim")
            self.assertIn(submission_module.PLUGIN_README_ZH_HANT_RELATIVE, result.stderr)

    def test_plugin_readme_boundary_removal_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(
                root,
                submission_module.PLUGIN_README_RELATIVE,
                "No public Directory availability is claimed.",
            )

            self.assert_rejected(run_validator(root), "must state the boundary")

    def test_missing_plugin_readme_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            (root / submission_module.PLUGIN_README_ZH_HANT_RELATIVE).unlink()

            self.assert_rejected(run_validator(root), "Required Plugin README is missing")

    def test_support_additional_official_channel_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.SUPPORT_RELATIVE
            # Placed inside the English Support channel section, which is
            # where a second channel would most plausibly be added.
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "Please do not expect support through other channels.",
                    "Official support is also available at https://example.com/support.\n\n"
                    "Please do not expect support through other channels.",
                ),
                encoding="utf-8",
            )

            self.assert_rejected(run_validator(root), "must not present another support channel")

    def test_support_additional_official_channel_in_translated_section_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nOfficial support is also available at https://example.com/support.\n",
            )

            self.assert_rejected(run_validator(root), "must not present another support channel")

    def test_privacy_missing_host_product_boundary_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(
                root,
                submission_module.PRIVACY_RELATIVE,
                "Any repository, file, or tool data the host product accesses on your "
                "behalf remains governed by the host product and by the tools you have "
                "configured. This policy does not change or override those terms.",
            )

            self.assert_rejected(run_validator(root), "host-product")

    def test_privacy_missing_l_and_co_receipt_boundary_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(
                root,
                submission_module.PRIVACY_RELATIVE,
                "L&Co.LLC does not receive your task contents merely because the "
                "Plugin is installed.",
            )

            self.assert_rejected(run_validator(root), "L&Co.LLC does not receive task contents")

    def test_privacy_missing_future_version_boundary_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(
                root,
                submission_module.PRIVACY_RELATIVE,
                "If a future version adds an MCP server, an app, a connector, "
                "telemetry, analytics, an authentication flow, or any hosted service, "
                "that version requires a new privacy policy and a new review. It is "
                "not covered by this document.",
            )

            self.assert_rejected(run_validator(root), "new policy and review")

    def test_human_status_cell_with_complete_and_pending_text_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            path = root / submission_module.HUMAN_PREREQUISITES_RELATIVE
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "| 3 | L&Co.LLC business identity verification | PENDING HUMAN CHECK |",
                    "| 3 | L&Co.LLC business identity verification | "
                    "COMPLETE — previously PENDING HUMAN CHECK |",
                ),
                encoding="utf-8",
            )

            result = run_validator(root)

            self.assert_rejected(result, "must equal 'PENDING HUMAN CHECK' exactly")
            self.assertIn("COMPLETE", result.stderr)

    def test_human_duplicate_item_row_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.HUMAN_PREREQUISITES_RELATIVE,
                "\n| 14 | Logo approval | PENDING HUMAN CHECK |\n",
            )

            self.assert_rejected(run_validator(root), "exactly one is required")

    def test_submission_readme_documents_existing_validation_dependencies(self):
        text = (ROOT / submission_module.SUBMISSION_README_RELATIVE).read_text(
            encoding="utf-8"
        )

        self.assertIn("python -m pip install -r requirements-validation.txt", text)
        self.assertIn("requirements-validation.txt", text)
        self.assertIn("no new third-party dependency", text)
        # The old wording claimed end-to-end validation was standard library only.
        self.assertNotIn("runs offline, with the standard library only", text)

    def test_valid_package_survives_false_positive_controls(self):
        """Wording the instruction explicitly allows must not be rejected."""
        allowed = (
            "No submission has occurred.",
            "This Plugin is not submitted to, listed in, or available from OpenAI's "
            "public Plugins Directory.",
            "Public policy URLs are prepared.",
            "The Plugin is not a public release.",
            "PENDING HUMAN CHECK",
            "Support and Privacy are published from this repository.",
            "公開ポリシーURLは準備済みです。",
            "公開政策 URL 已備妥。",
        )

        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(
                    claim_flagged(text), f"benign wording must not be flagged: {text}"
                )

    def test_claims_are_detected_per_clause(self):
        """A negation only covers its own clause."""
        rejected = (
            "No approval has occurred, but this Plugin is published.",
            "This Plugin is not submitted; however, it is publicly available.",
            "The release is not stable yet, but it is approved.",
            "This Plugin is publicly available from OpenAI's public Plugins Directory.",
        )

        for text in rejected:
            with self.subTest(text=text):
                self.assertTrue(claim_flagged(text), f"claim must be flagged: {text}")


if __name__ == "__main__":
    unittest.main()
