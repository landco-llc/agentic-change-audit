from __future__ import annotations

import hashlib
import importlib.util
import json
import os
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
    shutil.copytree(
        ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__"), symlinks=True
    )
    return root


def run_validator(root: Path) -> subprocess.CompletedProcess:
    # PYTHONDONTWRITEBYTECODE keeps validator subprocesses from creating new
    # cache files anywhere, so repository-invariance checks stay exact.
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [PYTHON, str(root / "scripts/validate-plugin-submission.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def tracked_repo_state() -> tuple[dict[str, str], str]:
    """Hash every git-tracked file and capture the full git status, so a test
    can prove it mutated only its temporary copy — not the real repository.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    )
    hashes: dict[str, str] = {}
    for relative in listing.stdout.split("\0"):
        if relative:
            hashes[relative] = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return hashes, status.stdout


class RepoInvariantTestCase(unittest.TestCase):
    """Base class proving whole-repository invariance around every test.

    The checkout may legitimately hold pre-existing untracked entries (for
    example __pycache__), so the check is before-vs-after equality of every
    tracked file hash plus the complete status output, not tree cleanliness.
    """

    def setUp(self):
        super().setUp()
        self._repo_state_before = tracked_repo_state()

    def tearDown(self):
        self.assertEqual(
            self._repo_state_before,
            tracked_repo_state(),
            "a test modified the real repository instead of its temporary copy",
        )
        super().tearDown()

    def assert_rejected(self, result: subprocess.CompletedProcess, needle: str) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(needle, result.stderr)
        # A caller must never see a PASS line alongside a nonzero exit.
        self.assertNotIn("Plugin submission validation: PASS", result.stdout)
        self.assertNotIn("Plugin submission validation: PASS", result.stderr)

    def assert_accepted(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Plugin submission validation: PASS", result.stdout)


def mutate_listing(root: Path, key: str, value) -> None:
    path = root / submission_module.LISTING_RELATIVE
    listing = load_json(path)
    listing[key] = value
    path.write_text(json.dumps(listing, indent=2) + "\n", encoding="utf-8")


def append_text(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def remove_text(root: Path, relative: str, needle: str) -> None:
    path = root / relative
    original = path.read_text(encoding="utf-8")
    if needle not in original:
        raise AssertionError(f"{relative} does not contain the text to remove: {needle!r}")
    path.write_text(original.replace(needle, ""), encoding="utf-8")


class SubmissionPackageTests(RepoInvariantTestCase):
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


class HardenedValidationTests(RepoInvariantTestCase):
    """Regression tests for the five mutations the first independent audit
    found the validator false-PASSing.
    """

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

class StatusClaimSubprocessTests(RepoInvariantTestCase):
    """F-03 acceptance tests. Every case runs the real validator as a
    subprocess against a fresh temporary repository copy — no test re-derives
    the implementation's patterns.
    """

    def reject_claim(self, relative: str, text: str, needle: str = "must not claim"):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, relative, "\n" + text + "\n")

            result = run_validator(root)

            self.assert_rejected(result, needle)
            self.assertIn(relative, result.stderr)

    def accept_statement(self, relative: str, text: str):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, relative, "\n" + text + "\n")

            self.assert_accepted(run_validator(root))

    # --- English invalid variants -------------------------------------------

    def test_en_claim_after_em_dash_negation_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "No submission has occurred — this Plugin is published.",
        )

    def test_en_claim_after_en_dash_negation_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "No submission has occurred – this Plugin is published.",
        )

    def test_en_claim_after_although_subordinate_comma_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Although this Plugin is not submitted, it is publicly available.",
        )

    def test_en_claim_after_em_dash_approved_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "No approval has occurred — the Plugin is now approved.",
        )

    def test_en_claim_after_nevertheless_released_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "The Plugin is not stable, nevertheless it is officially released.",
        )

    # --- Japanese invalid variants ------------------------------------------

    def test_ja_claim_after_desuga_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "このPluginは未申請ですが、公開Directoryで利用可能です。",
        )

    def test_ja_claim_after_sarete_imasen_ga_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "このPluginは申請されていませんが、OpenAIの公開Plugins Directoryから利用できます。",
        )

    def test_ja_claim_after_monono_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "未承認ではあるものの、このPluginは公開Directoryで提供されています。",
        )

    def test_ja_claim_after_nimokakawarazu_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "申請されていないにもかかわらず、公開Directoryで利用可能です。",
        )

    # --- Traditional Chinese invalid variants -------------------------------

    def test_zh_claim_after_dan_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "本Plugin尚未提交，但目前可從OpenAI公開Plugins Directory使用。",
        )

    def test_zh_claim_after_buguo_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "本Plugin尚未送出申請，不過現在可在公開Directory取得。",
        )

    def test_zh_claim_after_suiran_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "雖然尚未核准，本Plugin目前已於公開Plugins Directory提供。",
        )

    # --- Valid controls: every allowed statement, through the validator -----

    def test_valid_no_submission_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE, "No submission has occurred."
        )

    def test_valid_not_published_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE, "This Plugin is not published."
        )

    def test_valid_has_not_been_submitted_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE, "This Plugin has not been submitted."
        )

    def test_valid_coordinated_negation_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is not listed in, available from, or approved for OpenAI's "
            "public Plugins Directory.",
        )

    def test_valid_status_not_claimed_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Stable, approved, and published status are not claimed.",
        )

    def test_valid_not_public_release_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE, "The Plugin is not a public release."
        )

    def test_valid_policy_urls_prepared_statement_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE, "Public policy URLs are prepared."
        )

    def test_valid_ja_policy_urls_prepared_statement_passes(self):
        self.accept_statement(
            submission_module.PLUGIN_README_JA_RELATIVE, "公開ポリシーURLは準備済みです。"
        )

    def test_valid_zh_policy_urls_prepared_statement_passes(self):
        self.accept_statement(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "公開政策 URL 已備妥。"
        )

    # --- F-03: Markdown formatting must not hide a status claim -------------

    def test_md_bold_published_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE, "This Plugin is **published**."
        )

    def test_md_dunder_approved_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE, "This Plugin is __approved__."
        )

    def test_md_italic_publicly_available_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE, "This Plugin is *publicly available*."
        )

    def test_md_strikethrough_negation_claim_fails(self):
        # Struck-through text reads as deleted, so "~~not~~ published"
        # asserts publication.
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE, "This Plugin is ~~not~~ published."
        )

    def test_md_html_strong_published_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is <strong>published</strong>.",
        )

    def test_md_inline_link_label_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is [published](https://example.com/status).",
        )

    def test_md_reference_link_label_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is [published][status].\n\n[status]: https://example.com/status",
        )

    def test_md_list_item_bold_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "- This Plugin is **generally available**.",
        )

    def test_md_heading_bold_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "## This Plugin is **officially released**",
        )

    def test_md_ja_bold_claim_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "このPluginは**正式公開済み**です。",
        )

    def test_md_zh_bold_claim_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "本Plugin目前已**正式發布**。",
        )

    def test_md_inline_code_example_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Example only: `This Plugin is published.`",
        )

    def test_md_fenced_code_example_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "```text\nThis Plugin is published.\n```",
        )

    def test_md_emphasized_canonical_negative_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE, "**This Plugin is not published.**"
        )

    def test_md_neutral_link_label_with_claimy_destination_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "See the [status overview](https://example.com/published-release-status).",
        )


class SupportChannelClassificationTests(RepoInvariantTestCase):
    """F-04 acceptance tests: a noncanonical URL fails only when asserted as
    a support/contact channel, in any of the three languages, at any
    placement in the file.
    """

    SUPPORT_ERROR = "must not present another support channel"

    def reject_support(self, mutate):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            mutate(root)

            self.assert_rejected(run_validator(root), self.SUPPORT_ERROR)

    def accept_support(self, text: str):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, submission_module.SUPPORT_RELATIVE, "\n" + text + "\n")

            self.assert_accepted(run_validator(root))

    def insert_before(self, root: Path, anchor: str, text: str):
        path = root / submission_module.SUPPORT_RELATIVE
        original = path.read_text(encoding="utf-8")
        if anchor not in original:
            raise AssertionError(f"SUPPORT.md does not contain the anchor: {anchor!r}")
        path.write_text(original.replace(anchor, text + anchor, 1), encoding="utf-8")

    # --- Invalid: channel assertions with a /help URL, all placements -------

    def test_support_mixed_language_help_desk_in_japanese_section_fails(self):
        self.reject_support(
            lambda root: self.insert_before(
                root,
                "### セキュリティに関わる報告",
                "公式help deskは https://example.com/help です。\n\n",
            )
        )

    def test_support_official_zh_channel_in_zh_section_fails(self):
        self.reject_support(
            lambda root: self.insert_before(
                root,
                "### 涉及安全性的回報",
                "官方支援可透過 https://example.com/help 取得。\n\n",
            )
        )

    def test_support_official_customer_support_at_eof_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nFor official customer support, use https://example.com/help.\n",
            )
        )

    def test_support_assertion_on_preceding_line_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n公式サポート窓口:\n\nhttps://example.com/help\n",
            )
        )

    # --- Valid: reference and documentation links must stay allowed ---------

    def test_support_glossary_reference_url_passes(self):
        self.accept_support(
            "For background on support terminology, see "
            "https://example.com/docs/support-glossary."
        )

    def test_support_hyphenated_vocabulary_reference_passes(self):
        self.accept_support(
            "The implementation notes discuss customer-support vocabulary: "
            "https://example.com/docs/glossary."
        )

    def test_support_ja_glossary_reference_passes(self):
        self.accept_support(
            "サポート用語の背景資料は https://example.com/docs/support-glossary "
            "を参照してください。"
        )

    def test_support_zh_glossary_reference_passes(self):
        self.accept_support(
            "支援術語的背景資料請參閱 https://example.com/docs/support-glossary。"
        )

    # --- F-04: reference-style links resolve to their destinations ----------

    def test_support_reference_link_official_support_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nUse [official support][alt-support].\n\n"
                "[alt-support]: https://example.com/help\n",
            )
        )

    def test_support_reference_link_separated_definition_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nUse [official support][alt-support].\n\n"
                "The project remains open source.\n\n"
                "[alt-support]: https://example.com/help\n",
            )
        )

    def test_support_reference_link_ja_official_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n[公式サポート][help]\n\n[help]: https://example.com/help\n",
            )
        )

    def test_support_reference_link_zh_official_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n[官方支援][help]\n\n[help]: https://example.com/help\n",
            )
        )

    def test_support_inline_link_official_support_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nUse [official support](https://example.com/help).\n",
            )
        )

    # --- F-04: previous-line carry, colon-introduced destinations -----------

    def test_support_colon_carry_english_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nOfficial support:\nhttps://example.com/help\n",
            )
        )

    def test_support_colon_carry_ja_toiawasesaki_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n問い合わせ先:\nhttps://example.com/help\n",
            )
        )

    def test_support_colon_carry_zh_fullwidth_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n官方支援：\nhttps://example.com/help\n",
            )
        )

    def test_support_multiple_links_canonical_does_not_hide_alternative_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nOfficial support: "
                "https://github.com/landco-llc/agentic-change-audit/issues "
                "or https://example.com/help\n",
            )
        )

    # --- F-04: context precision and link false-positive controls -----------

    def test_support_unused_reference_definition_passes(self):
        self.accept_support("[unused-help]: https://example.com/help")

    def test_support_reference_link_glossary_passes(self):
        self.accept_support(
            "Read the [support terminology glossary][glossary].\n\n"
            "[glossary]: https://example.com/docs/support-glossary"
        )

    def test_support_ja_inline_link_glossary_passes(self):
        self.accept_support("[ヘルプデスクという語の説明](https://example.com/docs/glossary)")

    def test_support_zh_inline_link_glossary_passes(self):
        self.accept_support("[支援術語的背景資料](https://example.com/docs/support-glossary)")

    def test_support_ja_doc_prose_same_line_passes(self):
        self.accept_support(
            "ヘルプデスクという語の説明は https://example.com/docs/glossary にあります。"
        )

    def test_support_two_line_documentation_reference_passes(self):
        self.accept_support(
            "Official support remains GitHub Issues.\n"
            "Documentation reference: https://example.com/help"
        )

    def test_support_zh_doc_prose_passes(self):
        self.accept_support("本文件說明客服用語：https://example.com/docs/glossary。")


# Canonical fragments quoted from the actual PRIVACY.md, one per boundary in
# the validator's normative list. Each is removed everywhere it appears in a
# temporary copy; the validator must then fail on exactly that boundary.
PRIVACY_REMOVAL_FIXTURES = {
    "skills_only": "skills-only Plugin",
    "no_mcp_server": "no MCP server",
    "no_chatgpt_app": "no ChatGPT app",
    "no_connector": "no connector",
    "no_external_service": "no external service",
    "no_telemetry": "no telemetry",
    "no_analytics": "no analytics",
    "no_authentication_flow": "no authentication flow",
    "no_network_client": "no network client",
    "no_collection": "does not collect, transmit, sell, or share user data",
    "l_and_co_receipt": (
        "L&Co.LLC does not receive your task contents merely because the Plugin "
        "is installed."
    ),
    "active_task_scope": (
        "The Plugin reads only the data that is already made available to the "
        "active ChatGPT or Codex task, under your own environment and your own "
        "permissions."
    ),
    "host_product_governance": (
        "remains governed by the host product and by the tools you have configured"
    ),
    "terms_not_overridden": "This policy does not change or override those terms.",
    "secret_input_warning": (
        "Do not paste secrets, credentials, tokens, or personal data unnecessarily "
        "into an audit task."
    ),
    "output_data_warning": "repository paths, commit SHAs, branch names, filenames",
    "user_storage_control": "You control where those outputs are stored, pasted, or shared.",
    "future_version_policy": "requires a new privacy policy and a new review",
}


class PrivacyBoundaryRemovalTests(RepoInvariantTestCase):
    """F-05: every canonical Privacy boundary, independently removed and
    verified through the full validator subprocess.
    """


def _make_privacy_removal_test(snippet: str):
    def test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(root, submission_module.PRIVACY_RELATIVE, snippet)

            self.assert_rejected(run_validator(root), "must state the boundary")

    return test


for _slug, _snippet in PRIVACY_REMOVAL_FIXTURES.items():
    setattr(
        PrivacyBoundaryRemovalTests,
        f"test_privacy_boundary_{_slug}_removed_fails",
        _make_privacy_removal_test(_snippet),
    )


if __name__ == "__main__":
    unittest.main()
