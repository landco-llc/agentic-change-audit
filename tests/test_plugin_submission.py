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
    # dataclasses and other runtime type helpers resolve the defining module
    # through sys.modules, matching normal import machinery semantics.
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
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


class PortalStateWordingTests(RepoInvariantTestCase):
    """Portal-state regressions run only through the real validator process."""

    SAFE_BOUNDARIES = {
        submission_module.PLUGIN_README_RELATIVE: (
            "No portal action is performed or evidenced by this repository lane.",
            "Portal state remains a human verification gate.",
        ),
        submission_module.PLUGIN_README_JA_RELATIVE: (
            "このリポジトリ側の作業では申請ポータルを操作しておらず、その操作を示す証跡もありません。",
            "申請ポータルの状態は人間が確認する必要があります。",
        ),
        submission_module.PLUGIN_README_ZH_HANT_RELATIVE: (
            "本次儲存庫端作業未操作申請入口，也沒有相關操作證據。",
            "申請入口的實際狀態仍須由人工確認。",
        ),
    }

    def reject_portal_assertion(self, relative: str, text: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, relative, "\n" + text + "\n")

            result = run_validator(root)

            self.assert_rejected(result, "must not assert unverified external portal state")
            self.assertIn(relative, result.stderr)

    def assert_boundary_required(self, relative: str, boundary: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(root, relative, boundary)

            result = run_validator(root)

            self.assert_rejected(result, "must state the boundary")
            self.assertIn(relative, result.stderr)

    # --- Exact unsafe sentences being remediated ----------------------------

    def test_old_english_portal_sentence_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_RELATIVE,
            "No draft exists in the OpenAI submission portal, and nothing has been submitted.",
        )

    def test_old_japanese_portal_sentence_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "OpenAI submission portalにdraftは存在せず、何も提出していません。",
        )

    def test_old_traditional_chinese_portal_sentence_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "OpenAI submission portal 中沒有 draft，也未提交任何內容。",
        )

    # --- Materially equivalent portal-state claims -------------------------

    def test_english_portal_has_no_draft_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_RELATIVE, "The portal has no draft."
        )

    def test_english_portal_empty_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_RELATIVE,
            "The submission portal is empty.",
        )

    def test_english_portal_draft_exists_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_RELATIVE,
            "A draft exists in the OpenAI submission portal.",
        )

    def test_japanese_portal_has_no_draft_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "申請ポータルに下書きは存在しません。",
        )

    def test_japanese_nothing_submitted_through_portal_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "ポータルからは何も提出されていません。",
        )

    def test_japanese_portal_draft_exists_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "申請ポータルに下書きが存在します。",
        )

    def test_traditional_chinese_portal_has_no_draft_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "申請入口中沒有草稿。",
        )

    def test_traditional_chinese_portal_empty_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "申請入口是空的。",
        )

    def test_traditional_chinese_portal_draft_exists_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "申請入口中有草稿。",
        )

    # --- Every repository-lane boundary is independently required ----------

    def test_english_repository_lane_boundary_required(self):
        self.assert_boundary_required(
            submission_module.PLUGIN_README_RELATIVE,
            self.SAFE_BOUNDARIES[submission_module.PLUGIN_README_RELATIVE][0],
        )

    def test_english_human_gate_boundary_required(self):
        self.assert_boundary_required(
            submission_module.PLUGIN_README_RELATIVE,
            self.SAFE_BOUNDARIES[submission_module.PLUGIN_README_RELATIVE][1],
        )

    def test_japanese_repository_lane_boundary_required(self):
        self.assert_boundary_required(
            submission_module.PLUGIN_README_JA_RELATIVE,
            self.SAFE_BOUNDARIES[submission_module.PLUGIN_README_JA_RELATIVE][0],
        )

    def test_japanese_human_gate_boundary_required(self):
        self.assert_boundary_required(
            submission_module.PLUGIN_README_JA_RELATIVE,
            self.SAFE_BOUNDARIES[submission_module.PLUGIN_README_JA_RELATIVE][1],
        )

    def test_traditional_chinese_repository_lane_boundary_required(self):
        self.assert_boundary_required(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            self.SAFE_BOUNDARIES[submission_module.PLUGIN_README_ZH_HANT_RELATIVE][0],
        )

    def test_traditional_chinese_human_gate_boundary_required(self):
        self.assert_boundary_required(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            self.SAFE_BOUNDARIES[submission_module.PLUGIN_README_ZH_HANT_RELATIVE][1],
        )

    def test_safe_wording_passes_in_all_three_plugin_readmes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            self.assert_accepted(run_validator(root))

    def test_unsafe_english_assertion_after_safe_wording_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_RELATIVE, "There is no portal draft."
        )

    def test_unsafe_japanese_assertion_after_safe_wording_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "下書きは作成されていません。",
        )

    def test_unsafe_traditional_chinese_assertion_after_safe_wording_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "沒有建立任何申請草稿。",
        )

    def test_submission_readme_safe_portal_wording_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            text = (root / submission_module.SUBMISSION_README_RELATIVE).read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "No portal action is performed or evidenced by this repository lane.",
                text,
            )
            self.assertIn("Portal state remains a human verification gate.", text)
            self.assert_accepted(run_validator(root))


PORTAL_REQUIRED_INVALID_CASES = (
    ("required_en_no_draft_exists", submission_module.PLUGIN_README_RELATIVE, "No draft exists in the OpenAI submission portal."),
    ("required_en_portal_has_no_draft", submission_module.PLUGIN_README_RELATIVE, "The portal has no draft."),
    ("required_en_no_portal_draft", submission_module.PLUGIN_README_RELATIVE, "There is no portal draft."),
    ("required_en_portal_empty", submission_module.PLUGIN_README_RELATIVE, "The submission portal is empty."),
    ("required_en_nothing_submitted", submission_module.PLUGIN_README_RELATIVE, "Nothing has been submitted through the portal."),
    ("required_en_draft_exists", submission_module.PLUGIN_README_RELATIVE, "A draft exists in the submission portal."),
    ("required_en_content_submitted", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the portal."),
    ("required_ja_no_draft", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きは存在しません。"),
    ("required_ja_portal_empty", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルには何もありません。"),
    ("required_ja_draft_not_created", submission_module.PLUGIN_README_JA_RELATIVE, "下書きは作成されていません。"),
    ("required_ja_nothing_submitted", submission_module.PLUGIN_README_JA_RELATIVE, "ポータルからは何も提出されていません。"),
    ("required_ja_draft_exists", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きが存在します。"),
    ("required_ja_submitted_content", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルには提出済みの内容があります。"),
    ("required_zh_no_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中沒有草稿。"),
    ("required_zh_portal_empty", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口是空的。"),
    ("required_zh_draft_not_created", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "沒有建立任何申請草稿。"),
    ("required_zh_nothing_submitted", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "尚未透過申請入口提交任何內容。"),
    ("required_zh_draft_exists", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中已有草稿。"),
    ("required_zh_content_submitted", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "已透過申請入口提交內容。"),
)

# The 15 concrete false-PASS cases observed by the independent focused
# re-audit. Four deliberately overlap the canonical 19 so both evidence sets
# stay explicitly traceable in the test report.
PORTAL_OBSERVED_FALSE_PASS_CASES = (
    ("observed_en_content_submitted", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the portal."),
    ("observed_ja_submitted_content", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルには提出済みの内容があります。"),
    ("observed_zh_existing_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中已有草稿。"),
    ("observed_zh_content_submitted", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "已透過申請入口提交內容。"),
    ("observed_en_application_portal_saved_draft", submission_module.PLUGIN_README_RELATIVE, "The application portal contains a saved draft."),
    ("observed_en_pending_application_draft", submission_module.PLUGIN_README_RELATIVE, "A pending draft exists in the application portal."),
    ("observed_en_no_saved_application_draft", submission_module.PLUGIN_README_RELATIVE, "No saved draft exists in the application portal."),
    ("observed_en_submitted_soft_break", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the\nportal."),
    ("observed_ja_dorafuto", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルにドラフトが存在します。"),
    ("observed_ja_soukou", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに草稿が存在します。"),
    ("observed_ja_soushin", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルには送審済みの内容があります。"),
    ("observed_zh_pending_review_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中有待送審草稿。"),
    ("observed_zh_existing_pending_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中已有待處理草稿。"),
    ("observed_zh_not_reviewed", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "尚未透過申請入口送審任何內容。"),
    ("observed_zh_reviewed", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "已透過申請入口送審內容。"),
)

PORTAL_SEMANTIC_REQUIRED_CASES = (
    ("semantic_en_content_submitted", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the portal."),
    ("semantic_en_saved_draft", submission_module.PLUGIN_README_RELATIVE, "The application portal has a saved draft."),
    ("semantic_en_pending_draft_present", submission_module.PLUGIN_README_RELATIVE, "A pending draft is present in the submission portal."),
    ("semantic_en_no_saved_draft", submission_module.PLUGIN_README_RELATIVE, "There is no saved draft in the application portal."),
    ("semantic_en_awaiting_review", submission_module.PLUGIN_README_RELATIVE, "The portal contains an application awaiting review."),
    ("semantic_en_no_pending_application", submission_module.PLUGIN_README_RELATIVE, "The review portal has no pending application."),
    ("semantic_en_materials_uploaded", submission_module.PLUGIN_README_RELATIVE, "Materials were uploaded to the developer portal."),
    ("semantic_en_nothing_filed", submission_module.PLUGIN_README_RELATIVE, "Nothing was filed through the application system."),
    ("semantic_en_under_review", submission_module.PLUGIN_README_RELATIVE, "A submission is already under review in the portal."),
    ("semantic_en_does_not_contain", submission_module.PLUGIN_README_RELATIVE, "The portal does not contain a draft."),
    ("semantic_en_portal_not_empty", submission_module.PLUGIN_README_RELATIVE, "The developer portal is not empty."),
    ("semantic_en_portal_absent", submission_module.PLUGIN_README_RELATIVE, "The review portal is absent."),
    ("semantic_ja_submitted_content", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルには提出済みの内容があります。"),
    ("semantic_ja_draft_exists", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルにドラフトがあります。"),
    ("semantic_ja_draft_absent", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに草稿は存在しません。"),
    ("semantic_ja_saved_draft", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面には保存済みの下書きがあります。"),
    ("semantic_ja_nothing_submitted", submission_module.PLUGIN_README_JA_RELATIVE, "申請サイトからは何も提出されていません。"),
    ("semantic_ja_reviewed", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルで送審済みです。"),
    ("semantic_ja_awaiting_review", submission_module.PLUGIN_README_JA_RELATIVE, "申請入口には送審待ちの内容があります。"),
    ("semantic_ja_no_application_content", submission_module.PLUGIN_README_JA_RELATIVE, "審査ポータルには申請内容がありません。"),
    ("semantic_ja_submitted_materials_saved", submission_module.PLUGIN_README_JA_RELATIVE, "申請システムに提出済み資料が保存されています。"),
    ("semantic_ja_draft_not_created", submission_module.PLUGIN_README_JA_RELATIVE, "ポータルにはドラフトが作成されていません。"),
    ("semantic_ja_portal_not_empty", submission_module.PLUGIN_README_JA_RELATIVE, "ポータルは空ではありません。"),
    ("semantic_zh_existing_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中已有草稿。"),
    ("semantic_zh_submitted_content", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "已透過申請入口提交內容。"),
    ("semantic_zh_no_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請平台中沒有草稿。"),
    ("semantic_zh_pending_submission_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "提交入口已有待提交草稿。"),
    ("semantic_zh_pending_review_content", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "送審平台中已有待送審內容。"),
    ("semantic_zh_not_reviewed", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口尚未送審。"),
    ("semantic_zh_submitted_page_content", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請頁面已有提交內容。"),
    ("semantic_zh_no_pending_application", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核入口沒有待審核申請。"),
    ("semantic_zh_saved_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "平台中已儲存草稿。"),
    ("semantic_zh_no_draft_exists", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中不存在任何草稿。"),
    ("semantic_zh_platform_not_empty", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "平台不是空的。"),
)

PORTAL_FORMATTING_INVALID_CASES = (
    ("format_en_markdown_emphasis", submission_module.PLUGIN_README_RELATIVE, "The **application portal** has a **saved draft**."),
    ("format_en_html_emphasis", submission_module.PLUGIN_README_RELATIVE, "The <em>application portal</em> has a <strong>saved draft</strong>."),
    ("format_en_link", submission_module.PLUGIN_README_RELATIVE, "[A saved draft exists in the application portal](https://example.com)."),
    ("format_en_soft_break", submission_module.PLUGIN_README_RELATIVE, "A saved draft exists in the application\nportal."),
    ("format_en_case", submission_module.PLUGIN_README_RELATIVE, "THE APPLICATION PORTAL HAS A SAVED DRAFT."),
    ("format_en_whitespace", submission_module.PLUGIN_README_RELATIVE, "The application   portal has   a saved   draft."),
    ("format_ja_markdown_emphasis", submission_module.PLUGIN_README_JA_RELATIVE, "**申請ポータル**に**ドラフト**があります。"),
    ("format_ja_html_emphasis", submission_module.PLUGIN_README_JA_RELATIVE, "<em>申請ポータル</em>に<strong>草稿</strong>があります。"),
    ("format_ja_link", submission_module.PLUGIN_README_JA_RELATIVE, "[申請ポータルにドラフトがあります](https://example.com)。"),
    ("format_ja_soft_break", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに\nドラフトがあります。"),
    ("format_zh_markdown_emphasis", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "**申請入口**中**已有草稿**。"),
    ("format_zh_html_emphasis", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "<em>申請入口</em>中<strong>已有草稿</strong>。"),
    ("format_zh_link", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "[申請入口中已有草稿](https://example.com)。"),
    ("format_zh_soft_break", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中\n已有草稿。"),
    ("format_explanatory_then_current", submission_module.PLUGIN_README_RELATIVE, "The portal documentation defines a field named \"draft\". A saved draft exists in the portal."),
)

PORTAL_SAFE_CONTROL_CASES = (
    ("safe_en_repository_lane", submission_module.PLUGIN_README_RELATIVE, "No portal action is performed or evidenced by this repository lane."),
    ("safe_en_human_gate", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate."),
    ("safe_en_repository_material", submission_module.PLUGIN_README_RELATIVE, "The submission package contains repository-side preparation material."),
    ("safe_en_human_check", submission_module.PLUGIN_README_RELATIVE, "The final portal state must be checked by a human."),
    ("safe_en_no_api_client", submission_module.PLUGIN_README_RELATIVE, "The repository does not contain a portal API client."),
    ("safe_en_documentation_field", submission_module.PLUGIN_README_RELATIVE, "The portal documentation defines a field named \"draft\"."),
    ("safe_en_future_draft", submission_module.PLUGIN_README_RELATIVE, "A future portal draft may be created after human approval."),
    ("safe_en_fixture_example", submission_module.PLUGIN_README_RELATIVE, "The test fixture contains the phrase \"pending draft\" as an example."),
    ("safe_ja_repository_lane", submission_module.PLUGIN_README_JA_RELATIVE, "このリポジトリ側の作業では申請ポータルを操作していません。"),
    ("safe_ja_human_gate", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルの状態は人間が確認します。"),
    ("safe_ja_documentation_field", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルの「下書き」項目について説明します。"),
    ("safe_ja_future_draft", submission_module.PLUGIN_README_JA_RELATIVE, "人間の承認後に下書きを作成する可能性があります。"),
    ("safe_ja_term_explanation", submission_module.PLUGIN_README_JA_RELATIVE, "この文は「送審」という用語の説明です。"),
    ("safe_zh_repository_lane", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "本次儲存庫端作業未操作申請入口。"),
    ("safe_zh_human_gate", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口的實際狀態仍須由人工確認。"),
    ("safe_zh_documentation_field", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "文件說明申請入口的「草稿」欄位。"),
    ("safe_zh_future_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "人工核准後可能建立草稿。"),
    ("safe_zh_term_explanation", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "本段僅解釋「送審」這個詞彙。"),
)

# Seventh-remediation F-06A audit vocabulary. Each case is an independent
# real-validator subprocess test so a failure names the exact lexical family.
F06_AUDIT_LEXICAL_INVALID_CASES = (
    ("f06a_en_saved_application_remains", submission_module.PLUGIN_README_RELATIVE, "A saved application remains in the review portal."),
    ("f06a_en_review_system_holds_material", submission_module.PLUGIN_README_RELATIVE, "The review system currently holds submitted material."),
    ("f06a_en_no_application_on_file", submission_module.PLUGIN_README_RELATIVE, "No application is on file in the portal."),
    ("f06a_en_dashboard_pending_application", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard contains a pending application."),
    ("f06a_ja_draft_remains", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルにドラフトが残っています。"),
    ("f06a_ja_material_registered", submission_module.PLUGIN_README_JA_RELATIVE, "提出ポータルに提出物が登録されています。"),
    ("f06a_ja_sent_to_review", submission_module.PLUGIN_README_JA_RELATIVE, "審査ポータルで審査に回っています。"),
    ("f06a_ja_application_not_remaining", submission_module.PLUGIN_README_JA_RELATIVE, "申請システムには申請が残っていません。"),
    ("f06a_zh_draft_retained", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中仍保留草稿。"),
    ("f06a_zh_application_material_saved", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "提交平台中保存了申請資料。"),
    ("f06a_zh_delivery_completed", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "送審入口已完成送件。"),
    ("f06a_zh_application_under_review", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核平台正在審查申請。"),
    ("f06a_zh_material_uploaded", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請資料已上傳至平台。"),
    ("f06a_en_portal_shows_awaiting_draft", submission_module.PLUGIN_README_RELATIVE, "The portal shows a draft awaiting review."),
    ("f06a_ja_screen_saved_draft", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面に草稿が保存されています。"),
)

F06_MORPHOLOGY_INVALID_CASES = (
    # English surfaces, objects, tense, and aspect.
    ("morph_en_lodged", submission_module.PLUGIN_README_RELATIVE, "The application was lodged through the submission system."),
    ("morph_en_holds_submitted_material", submission_module.PLUGIN_README_RELATIVE, "The review system currently holds submitted material."),
    ("morph_en_still_on_file", submission_module.PLUGIN_README_RELATIVE, "A draft is still on file in the developer portal."),
    ("morph_en_no_application_on_file", submission_module.PLUGIN_README_RELATIVE, "No application is on file in the portal."),
    ("morph_en_dashboard_contains", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard contains a pending application."),
    ("morph_en_sent_for_review", submission_module.PLUGIN_README_RELATIVE, "The application has already been sent for review through the portal."),
    ("morph_en_records_no_materials", submission_module.PLUGIN_README_RELATIVE, "The portal records no submitted materials."),
    ("morph_en_content_present", submission_module.PLUGIN_README_RELATIVE, "Submitted content is present in the application system."),
    ("morph_en_review_queue_holds", submission_module.PLUGIN_README_RELATIVE, "The review queue holds an application."),
    ("morph_en_record_remains", submission_module.PLUGIN_README_RELATIVE, "A submission record remains in the developer console."),
    ("morph_en_dashboard_displayed", submission_module.PLUGIN_README_RELATIVE, "The application dashboard displayed a saved form."),
    ("morph_en_workspace_stored", submission_module.PLUGIN_README_RELATIVE, "The submission workspace stored an application packet."),
    # Japanese surfaces, objects, inflection, and auxiliary forms.
    ("morph_ja_saved", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面に草稿が保存されています。"),
    ("morph_ja_applied", submission_module.PLUGIN_README_JA_RELATIVE, "申請サイトで申請済みです。"),
    ("morph_ja_registered", submission_module.PLUGIN_README_JA_RELATIVE, "提出ポータルに提出物が登録されています。"),
    ("morph_ja_under_review", submission_module.PLUGIN_README_JA_RELATIVE, "審査ポータルで審査に回っています。"),
    ("morph_ja_not_remaining", submission_module.PLUGIN_README_JA_RELATIVE, "申請システムには申請が残っていません。"),
    ("morph_ja_sent_material", submission_module.PLUGIN_README_JA_RELATIVE, "ポータルに送付済みの資料があります。"),
    ("morph_ja_awaiting_case", submission_module.PLUGIN_README_JA_RELATIVE, "申請ページには審査待ちの案件があります。"),
    ("morph_ja_sent_from_entry", submission_module.PLUGIN_README_JA_RELATIVE, "申請入口から送信済みです。"),
    ("morph_ja_content_not_saved", submission_module.PLUGIN_README_JA_RELATIVE, "審査画面に申請内容が保存されていません。"),
    ("morph_ja_list_registered", submission_module.PLUGIN_README_JA_RELATIVE, "申請一覧に案件が登録されています。"),
    ("morph_ja_queue_remaining", submission_module.PLUGIN_README_JA_RELATIVE, "審査キューに提出物が残っています。"),
    ("morph_ja_file_accepted", submission_module.PLUGIN_README_JA_RELATIVE, "管理画面で申請書が受理されています。"),
    # Taiwan Traditional Chinese surfaces, objects, and aspect markers.
    ("morph_zh_delivery_record", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請平台已有送件紀錄。"),
    ("morph_zh_material_saved", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "提交平台中保存了申請資料。"),
    ("morph_zh_pending_case", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請頁面已有待審案件。"),
    ("morph_zh_delivery_completed", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "送審入口已完成送件。"),
    ("morph_zh_reviewing", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核平台正在審查申請。"),
    ("morph_zh_no_delivery_material", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "入口中沒有任何送件資料。"),
    ("morph_zh_uploaded", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請資料已上傳至平台。"),
    ("morph_zh_sent_through_entry", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請已透過入口送出。"),
    ("morph_zh_pending_draft", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "平台中仍有待處理的草稿。"),
    ("morph_zh_backend_retained", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請後台留存了提交紀錄。"),
    ("morph_zh_queue_pending", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核佇列中已有待審案件。"),
    ("morph_zh_form_registered", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請介面已登記表單。"),
    # Additional unseen inflections from the audited morphology families.
    ("inflect_en_held", submission_module.PLUGIN_README_RELATIVE, "The review portal held submitted material."),
    ("inflect_en_holding", submission_module.PLUGIN_README_RELATIVE, "The application console is holding a saved record."),
    ("inflect_en_remained", submission_module.PLUGIN_README_RELATIVE, "A saved application remained in the review portal."),
    ("inflect_en_registration_remains", submission_module.PLUGIN_README_RELATIVE, "An application registration record remains in the developer console."),
    ("inflect_en_registered", submission_module.PLUGIN_README_RELATIVE, "The application was registered in the submission system."),
    ("inflect_ja_plain_remains", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きが残る。"),
    ("inflect_ja_registered_progressive", submission_module.PLUGIN_README_JA_RELATIVE, "申請一覧に案件が登録されている。"),
    ("inflect_ja_registered_complete", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面の申請書は登録済みです。"),
    ("inflect_ja_unregistered", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面の申請書は未登録です。"),
    ("inflect_zh_not_retained", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口中未保留草稿。"),
    ("inflect_zh_saved", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請平台已保存申請資料。"),
    ("inflect_zh_not_saved", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請平台未保存申請資料。"),
    ("inflect_zh_delivered", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口已送件。"),
    ("inflect_zh_not_yet_delivered", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口尚未送件。"),
    ("inflect_zh_uploaded", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請資料已上傳至申請平台。"),
    ("inflect_zh_not_uploaded", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請資料未上傳至申請平台。"),
)

F06_STRUCTURE_INVALID_CASES = (
    ("structure_en_parentheses", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate (a saved draft exists in the application portal)."),
    ("structure_en_fullwidth_parentheses", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate （a saved draft exists in the application portal）."),
    ("structure_en_square_brackets", submission_module.PLUGIN_README_RELATIVE, "Human review is required [the submission dashboard contains a pending application]."),
    ("structure_en_curly_brackets", submission_module.PLUGIN_README_RELATIVE, "The repository cannot determine the portal state {submitted content is present in the application system}."),
    ("structure_ja_fullwidth_parentheses", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルの状態は人間が確認します（申請画面には保存済みの下書きがあります）。"),
    ("structure_ja_corner_brackets", submission_module.PLUGIN_README_JA_RELATIVE, "人間による確認が必要です【提出ポータルに提出物が登録されています】。"),
    ("structure_zh_fullwidth_parentheses", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口的實際狀態仍須由人工確認（申請入口中已有草稿）。"),
    ("structure_zh_corner_brackets", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "仍須人工確認【申請資料已上傳至平台】。"),
    ("structure_nested_parentheses", submission_module.PLUGIN_README_RELATIVE, "Human verification is required (the reviewer should check whether the portal contains a draft (a saved draft actually exists))."),
)

F06_SAFE_PLUS_UNSAFE_INVALID_CASES = (
    ("isolation_en_later_sentence", submission_module.PLUGIN_README_RELATIVE, "The reviewer must verify the portal. A saved draft exists there in the application portal."),
    ("isolation_en_contrast", submission_module.PLUGIN_README_RELATIVE, "Human verification is required, but the portal currently holds submitted material."),
    ("isolation_en_coordinated_clause", submission_module.PLUGIN_README_RELATIVE, "Human verification is required, and a saved draft exists in the portal."),
    ("isolation_ja_contrast", submission_module.PLUGIN_README_JA_RELATIVE, "人間が確認しますが、申請ポータルには下書きがあります。"),
    ("isolation_ja_later_sentence", submission_module.PLUGIN_README_JA_RELATIVE, "確認が必要です。提出物は申請画面に登録されています。"),
    ("isolation_zh_contrast", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "仍須人工確認，但申請入口中已有草稿。"),
    ("isolation_zh_later_sentence", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "需要查核。申請資料已上傳至平台。"),
    ("isolation_en_future_semicolon", submission_module.PLUGIN_README_RELATIVE, "A future draft may be created; a saved draft currently exists in the portal."),
    ("isolation_ja_future_contrast", submission_module.PLUGIN_README_JA_RELATIVE, "承認後に操作する予定ですが、現在は申請画面に下書きがあります。"),
    ("isolation_zh_future_contrast", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "人工核准後可能建立草稿，但申請入口中已有草稿。"),
    ("isolation_list_items", submission_module.PLUGIN_README_RELATIVE, "- Portal state remains a human verification gate.\n- A saved draft exists in the application portal."),
)

F06_DISCOURSE_SAFE_CASES = (
    # English questions and scoped verification.
    ("discourse_en_determine_whether", submission_module.PLUGIN_README_RELATIVE, "The reviewer must determine whether a draft exists in the portal."),
    ("discourse_en_direct_question", submission_module.PLUGIN_README_RELATIVE, "Does a saved draft exist in the application portal? Human verification is required."),
    ("discourse_en_whether_remains", submission_module.PLUGIN_README_RELATIVE, "Whether submitted material remains in the review portal must be checked by a human."),
    ("discourse_en_cannot_determine_if", submission_module.PLUGIN_README_RELATIVE, "The repository cannot determine if an application is on file in the portal."),
    # Japanese questions and scoped verification.
    ("discourse_ja_exists_question", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きがあるかは人間が確認します。"),
    ("discourse_ja_draft_confirmation", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルにドラフトが存在するか確認が必要です。"),
    ("discourse_ja_cannot_determine", submission_module.PLUGIN_README_JA_RELATIVE, "申請が残っているかどうかは、このリポジトリから判断できません。"),
    ("discourse_ja_presence_human_check", submission_module.PLUGIN_README_JA_RELATIVE, "提出物の有無は人間が確認します。"),
    # Taiwan Traditional Chinese questions and scoped verification.
    ("discourse_zh_draft_whether", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口是否已有草稿，仍須人工確認。"),
    ("discourse_zh_submission_whether", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "需要確認申請是否已送件。"),
    ("discourse_zh_cannot_determine", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "平台中有無待審案件，無法由本儲存庫判定。"),
    ("discourse_zh_content_verification", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "提交內容是否存在仍須查核。"),
    # Documentation, examples, and quoted terms.
    ("discourse_en_documentation", submission_module.PLUGIN_README_RELATIVE, "The portal documentation defines a field named \"draft\"."),
    ("discourse_en_fixture_example", submission_module.PLUGIN_README_RELATIVE, "The test fixture contains the phrase \"pending draft\" as an example."),
    ("discourse_en_term_example", submission_module.PLUGIN_README_RELATIVE, "This example explains the term \"submitted content\"."),
    ("discourse_ja_documentation", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルの「下書き」項目について説明します。"),
    ("discourse_ja_term", submission_module.PLUGIN_README_JA_RELATIVE, "この文書は「送審」という用語を説明しています。"),
    ("discourse_ja_test_example", submission_module.PLUGIN_README_JA_RELATIVE, "テスト例として「提出済み」という文字列を記載します。"),
    ("discourse_zh_documentation", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "文件說明申請入口的「草稿」欄位。"),
    ("discourse_zh_term", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "本段僅說明「送審」這個詞彙。"),
    ("discourse_zh_test_example", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "測試範例包含「已提交」字樣。"),
    # Future and hypothetical scopes.
    ("discourse_en_future", submission_module.PLUGIN_README_RELATIVE, "A future portal draft may be created after human approval."),
    ("discourse_en_hypothetical", submission_module.PLUGIN_README_RELATIVE, "If a draft is created in the portal, a human will review it."),
    ("discourse_en_future_will", submission_module.PLUGIN_README_RELATIVE, "A portal draft will be created after approval."),
    ("discourse_en_future_when", submission_module.PLUGIN_README_RELATIVE, "When a human later submits an application through the portal, it will be reviewed."),
    ("discourse_ja_future", submission_module.PLUGIN_README_JA_RELATIVE, "人間の承認後に下書きを作成する可能性があります。"),
    ("discourse_ja_hypothetical", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きが作成された場合は人間が確認します。"),
    ("discourse_ja_future_plan", submission_module.PLUGIN_README_JA_RELATIVE, "承認後に申請ポータルへ送信する予定です。"),
    ("discourse_ja_hypothetical_nara", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きがあるなら人間が確認します。"),
    ("discourse_zh_future", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "人工核准後可能建立草稿。"),
    ("discourse_zh_hypothetical", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "如果申請入口建立草稿，屆時由人工確認。"),
    ("discourse_zh_future_expected", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "預計人工核准後在申請入口建立草稿。"),
    ("discourse_zh_hypothetical_ruo", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "若申請入口建立草稿，屆時由人工確認。"),
    # Code content is removed before structural segmentation.
    ("discourse_inline_code", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate. `(a saved draft exists in the application portal)`"),
    ("discourse_fenced_code", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate.\n\n```text\n(a saved draft exists in the application portal)\n```"),
)

PRODUCT_STATUS_DISCOURSE_INVALID_CASES = (
    ("product_zh_example_then_actual", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "測試範例包含「已提交」字樣，但本 Plugin 已提交。"),
    ("product_zh_bare_quoted_claim", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "本 Plugin「已提交」。"),
)

# Eighth-remediation lexical closures. The six audited sentences and fresh
# inflections each execute the real validator against an isolated repository.
F06_PREDICATE_LEXICAL_INVALID_CASES = (
    ("predicate_lexical_en_shows_no_entry", submission_module.PLUGIN_README_RELATIVE, "The developer console shows no pending entry."),
    ("predicate_lexical_ja_sent_file", submission_module.PLUGIN_README_JA_RELATIVE, "提出一覧には送付済みファイルがあります。"),
    ("predicate_lexical_ja_returned_case", submission_module.PLUGIN_README_JA_RELATIVE, "審査画面で案件が差し戻されています。"),
    ("predicate_lexical_ja_accepted_form", submission_module.PLUGIN_README_JA_RELATIVE, "申請フォームはすでに受付済みです。"),
    ("predicate_lexical_zh_shows_returned", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核頁面顯示退回的申請。"),
    ("predicate_lexical_zh_was_rejected", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "提交內容已被駁回。"),
    ("predicate_inflect_en_showing_entry", submission_module.PLUGIN_README_RELATIVE, "The application dashboard is showing a pending entry."),
    ("predicate_inflect_en_showed_entries", submission_module.PLUGIN_README_RELATIVE, "The review console showed no pending entries."),
    ("predicate_inflect_ja_file_was_sent", submission_module.PLUGIN_README_JA_RELATIVE, "提出一覧に送付されたファイルがあります。"),
    ("predicate_inflect_ja_file_sent_complete", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面のファイルは送付済みです。"),
    ("predicate_inflect_ja_case_will_return", submission_module.PLUGIN_README_JA_RELATIVE, "審査画面で案件が差し戻される。"),
    ("predicate_inflect_ja_case_returned", submission_module.PLUGIN_README_JA_RELATIVE, "審査一覧の案件は差し戻されている。"),
    ("predicate_inflect_ja_form_accepted", submission_module.PLUGIN_README_JA_RELATIVE, "申請フォームは受け付けられている。"),
    ("predicate_inflect_ja_application_received", submission_module.PLUGIN_README_JA_RELATIVE, "申請フォームの申請は受付されています。"),
    ("predicate_inflect_zh_displayed_returned", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核頁面顯示已退回的申請。"),
    ("predicate_inflect_zh_list_returned", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "審核列表呈現退回的案件。"),
    ("predicate_inflect_zh_content_rejected", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "提交內容遭駁回。"),
    ("predicate_inflect_zh_material_returned", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請資料已被退回。"),
)

# Safe operators and independent current predicates deliberately share one
# structural segment. Each named case proves that only the governed predicate
# is exempt, including cross-language coordination.
F06_PREDICATE_SCOPE_INVALID_CASES = (
    ("predicate_question_en_while", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether a draft exists while the review portal currently contains submitted material."),
    ("predicate_question_ja_ga", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きがあるか確認しますが、申請画面には提出済み資料があります。"),
    ("predicate_question_zh_dan", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "需要確認申請入口是否有草稿，但申請資料已上傳至平台。"),
    ("predicate_example_en_while", submission_module.PLUGIN_README_RELATIVE, "This is an explanatory example, while the portal currently contains a saved application."),
    ("predicate_example_ja_comma", submission_module.PLUGIN_README_JA_RELATIVE, "これは説明例で、申請画面には提出済み資料があります。"),
    ("predicate_example_zh_dan", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "這只是說明範例，但申請入口中已有草稿。"),
    ("predicate_repository_en_while", submission_module.PLUGIN_README_RELATIVE, "No portal action is performed or evidenced by this repository lane while a saved draft exists in the portal."),
    ("predicate_human_ja_ga", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルの状態は人間が確認しますが、申請画面には下書きがあります。"),
    ("predicate_human_zh_dan", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口的狀態仍須人工確認，但申請資料已提交。"),
    ("predicate_future_en_while", submission_module.PLUGIN_README_RELATIVE, "A draft may be created later while the portal currently holds submitted material."),
    ("predicate_future_ja_ga", submission_module.PLUGIN_README_JA_RELATIVE, "将来下書きを作成する可能性がありますが、現在は申請画面に下書きがあります。"),
    ("predicate_future_zh_dan", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "未來可能建立草稿，但申請入口中已有草稿。"),
    ("predicate_cross_en_ja", submission_module.PLUGIN_README_JA_RELATIVE, "This is only a hypothetical example, 申請ポータルには提出済み資料があります。"),
    ("predicate_cross_ja_zh", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "これは用語の説明です，但申請入口中已有草稿。"),
    ("predicate_cross_zh_en", submission_module.PLUGIN_README_RELATIVE, "本段僅為範例, but a saved draft exists in the application portal."),
    ("predicate_coord_en_whereas", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether a draft exists whereas the portal currently stores submitted material."),
    ("predicate_coord_en_and", submission_module.PLUGIN_README_RELATIVE, "Human verification is required and a saved draft exists in the portal."),
    ("predicate_coord_en_comma", submission_module.PLUGIN_README_RELATIVE, "This is a documentation example, the application console currently holds a saved record."),
    ("predicate_coord_ja_simultaneous", submission_module.PLUGIN_README_JA_RELATIVE, "下書きがあるか確認すると同時に、申請画面には提出済み資料があります。"),
    ("predicate_coord_ja_one_side", submission_module.PLUGIN_README_JA_RELATIVE, "これは用語の説明である一方、申請一覧には案件が登録されています。"),
    ("predicate_coord_ja_nagara", submission_module.PLUGIN_README_JA_RELATIVE, "将来の操作を説明しながら、現在は申請画面に下書きがあります。"),
    ("predicate_coord_ja_plain_ga", submission_module.PLUGIN_README_JA_RELATIVE, "下書きの有無は人間が確認するが申請画面には提出物があります。"),
    ("predicate_coord_zh_simultaneous", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "需要確認是否有草稿，同時申請資料已上傳至平台。"),
    ("predicate_coord_zh_er", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "本段只是範例，而申請入口中已有草稿。"),
    ("predicate_coord_zh_and", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "仍須人工確認且提交內容已被駁回。"),
)

F06_PREDICATE_SAFE_CASES = (
    ("predicate_safe_en_question", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether a draft exists in the portal."),
    ("predicate_safe_en_human_question", submission_module.PLUGIN_README_RELATIVE, "Human verification is required to determine whether the portal contains submitted material."),
    ("predicate_safe_en_example", submission_module.PLUGIN_README_RELATIVE, "This example explains the phrase \"submitted material is present in the portal\"."),
    ("predicate_safe_en_hypothetical", submission_module.PLUGIN_README_RELATIVE, "If a draft is created later, a human must review it."),
    ("predicate_safe_ja_question", submission_module.PLUGIN_README_JA_RELATIVE, "申請ポータルに下書きがあるかを人間が確認します。"),
    ("predicate_safe_ja_verification", submission_module.PLUGIN_README_JA_RELATIVE, "申請画面に提出物があるかどうかは確認が必要です。"),
    ("predicate_safe_ja_example", submission_module.PLUGIN_README_JA_RELATIVE, "これは「申請画面に提出済み資料があります」という例文の説明です。"),
    ("predicate_safe_ja_future", submission_module.PLUGIN_README_JA_RELATIVE, "将来下書きを作成する場合は、人間が確認します。"),
    ("predicate_safe_zh_question", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "申請入口是否已有草稿，仍須人工確認。"),
    ("predicate_safe_zh_verification", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "需要確認平台中是否有待審案件。"),
    ("predicate_safe_zh_example", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "本段說明「申請資料已提交」這個範例句。"),
    ("predicate_safe_zh_future", submission_module.PLUGIN_README_ZH_HANT_RELATIVE, "若未來建立草稿，仍須人工審核。"),
)

F06_JA_AVAILABILITY_INVALID_CASES = (
    ("availability_ja_public_available", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは公開利用可能です。"),
    ("availability_ja_current_public_available", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは現在公開利用可能です。"),
    ("availability_ja_general_public", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは一般公開で利用できます。"),
    ("availability_ja_published_available", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは公開済みで利用可能です。"),
    ("availability_ja_anyone", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは誰でも利用可能です。"),
    ("availability_ja_public_progressive", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは公開利用可能になっています。"),
    ("availability_ja_general_possible", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは一般公開で利用可能です。"),
    ("availability_ja_anyone_became", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは誰でも利用可能になりました。"),
)

F06_JA_AVAILABILITY_SAFE_CASES = (
    ("availability_safe_ja_future", submission_module.PLUGIN_README_JA_RELATIVE, "将来公開できる可能性があります。"),
    ("availability_safe_ja_question", submission_module.PLUGIN_README_JA_RELATIVE, "公開できるかどうかは人間が判断します。"),
    ("availability_safe_ja_direct_question", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは公開利用可能ですか？"),
    ("availability_safe_ja_negated", submission_module.PLUGIN_README_JA_RELATIVE, "このPluginは公開利用可能ではありません。"),
    ("availability_safe_ja_explanation", submission_module.PLUGIN_README_JA_RELATIVE, "これは「公開利用可能」という表現の説明です。"),
)


def _make_portal_semantic_rejection_test(relative: str, text: str):
    def test(self):
        self.reject_portal_assertion(relative, text)

    return test


def _make_portal_semantic_safe_test(relative: str, text: str):
    def test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, relative, "\n" + text + "\n")
            self.assert_accepted(run_validator(root))

    return test


for _name, _relative, _text in (
    *PORTAL_REQUIRED_INVALID_CASES,
    *PORTAL_OBSERVED_FALSE_PASS_CASES,
    *PORTAL_SEMANTIC_REQUIRED_CASES,
    *PORTAL_FORMATTING_INVALID_CASES,
    *F06_AUDIT_LEXICAL_INVALID_CASES,
    *F06_MORPHOLOGY_INVALID_CASES,
    *F06_STRUCTURE_INVALID_CASES,
    *F06_SAFE_PLUS_UNSAFE_INVALID_CASES,
    *F06_PREDICATE_LEXICAL_INVALID_CASES,
    *F06_PREDICATE_SCOPE_INVALID_CASES,
):
    setattr(
        PortalStateWordingTests,
        f"test_portal_semantic_{_name}_fails",
        _make_portal_semantic_rejection_test(_relative, _text),
    )

for _name, _relative, _text in (
    *PORTAL_SAFE_CONTROL_CASES,
    *F06_DISCOURSE_SAFE_CASES,
    *F06_PREDICATE_SAFE_CASES,
    *F06_JA_AVAILABILITY_SAFE_CASES,
):
    setattr(
        PortalStateWordingTests,
        f"test_portal_semantic_{_name}_passes",
        _make_portal_semantic_safe_test(_relative, _text),
    )


def _make_product_status_discourse_rejection_test(relative: str, text: str):
    def test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, relative, "\n" + text + "\n")
            self.assert_rejected(run_validator(root), "must not claim")

    return test


for _name, _relative, _text in (
    *PRODUCT_STATUS_DISCOURSE_INVALID_CASES,
    *F06_JA_AVAILABILITY_INVALID_CASES,
):
    setattr(
        PortalStateWordingTests,
        f"test_portal_semantic_{_name}_fails",
        _make_product_status_discourse_rejection_test(_relative, _text),
    )


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

    # --- CommonMark edge cases: escapes, entities, comments -----------------

    def test_md_backslash_escaped_emphasis_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            r"This Plugin is \*\*published\*\*.",
        )

    def test_md_named_entity_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is &ast;&ast;published&ast;&ast;.",
        )

    def test_md_decimal_entity_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is &#42;&#42;published&#42;&#42;.",
        )

    def test_md_hex_entity_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is &#x2A;&#x2A;published&#x2A;&#x2A;.",
        )

    def test_md_named_entity_underscore_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is &lowbar;&lowbar;approved&lowbar;&lowbar;.",
        )

    def test_md_single_line_html_comment_split_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is <!-- status -->published.",
        )

    def test_md_html_comment_splitting_a_word_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is pub<!-- split -->lished.",
        )

    def test_md_multiline_html_comment_split_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is <!--\nhidden\n-->approved.",
        )

    def test_md_claim_wholly_inside_html_comment_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "<!-- This Plugin is published. -->",
        )

    # --- CommonMark edge cases: soft line breaks ----------------------------

    def test_md_soft_line_break_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is publicly\navailable.",
        )

    def test_md_emphasized_soft_line_break_claim_fails(self):
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is **publicly\navailable**.",
        )

    def test_md_soft_line_break_ja_claim_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_JA_RELATIVE,
            "このPluginは正式\n公開済みです。",
        )

    def test_md_soft_line_break_zh_claim_fails(self):
        self.reject_claim(
            submission_module.PLUGIN_README_ZH_HANT_RELATIVE,
            "本Plugin目前已正式\n發布。",
        )

    def test_md_paragraph_boundary_is_not_joined_passes(self):
        # Two paragraphs must never be fused into one synthetic claim.
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "This Plugin is not publicly\n\navailable from the Directory.",
        )

    # --- CommonMark edge cases: indented code -------------------------------

    def test_md_four_space_indented_code_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Closing prose paragraph.\n\n    This Plugin is published.",
        )

    def test_md_tab_indented_code_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Closing prose paragraph.\n\n\tThis Plugin is approved.",
        )

    def test_md_multiline_indented_code_passes(self):
        self.accept_statement(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Closing prose paragraph.\n\n    This Plugin is published.\n\n"
            "    This Plugin is approved.",
        )

    def test_md_list_continuation_prose_is_still_scanned_fails(self):
        # Indented text under a list item is item prose, not a code block, so
        # it renders to the reader and must still be scanned.
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "- Item one.\n\n    This Plugin is published.",
        )

    def test_md_indent_cannot_interrupt_paragraph_fails(self):
        # An indented code block cannot interrupt a paragraph, so this stays
        # visible prose.
        self.reject_claim(
            submission_module.RELEASE_NOTES_RELATIVE,
            "Closing prose paragraph.\n    This Plugin is published.",
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

    # --- Reference destination forms ----------------------------------------

    def test_support_angle_bracket_reference_destination_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nUse [official support][help].\n\n"
                "[help]: <https://example.com/help>\n",
            )
        )

    def test_support_angle_destination_with_title_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nUse [official support][help].\n\n"
                "[help]: <https://example.com/help> 'Help'\n",
            )
        )

    def test_support_bare_destination_with_title_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nUse [official support][help].\n\n"
                '[help]: https://example.com/help "Help"\n',
            )
        )

    def test_support_unused_angle_definition_passes(self):
        self.accept_support("[unused-help]: <https://example.com/help>")

    # --- First definition wins ----------------------------------------------

    def test_support_duplicate_definition_first_noncanonical_fails(self):
        # CommonMark resolves the first definition, so the canonical URL on
        # the second line does not rescue this.
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n[help]: https://example.com/help\n"
                f"[help]: {submission_module.CANONICAL_SUPPORT_URL}\n\n"
                "Use [official support][help].\n",
            )
        )

    def test_support_duplicate_definition_first_canonical_passes(self):
        self.accept_support(
            f"[help]: {submission_module.CANONICAL_SUPPORT_URL}\n"
            "[help]: https://example.com/help\n\n"
            "Use [official support][help]."
        )

    # --- Label normalization and escapes ------------------------------------

    def test_support_escaped_bracket_label_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n[help]: https://example.com/help\n\n"
                "Use [official \\[support\\]][help].\n",
            )
        )

    def test_support_case_and_whitespace_normalized_label_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n[help]: https://example.com/help\n\n"
                "Use [Official   Support][  HELP  ].\n",
            )
        )

    # --- Images -------------------------------------------------------------

    def test_support_image_alt_official_support_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n![official support](https://example.com/help)\n",
            )
        )

    def test_support_reference_image_alt_official_support_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n![公式サポート][help]\n\n[help]: https://example.com/help\n",
            )
        )

    def test_support_linked_image_official_support_fails(self):
        # The outer destination is the support destination.
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\n[![official support](https://example.com/logo.png)]"
                "(https://example.com/help)\n",
            )
        )

    def test_support_neutral_image_passes(self):
        self.accept_support(
            "![support terminology diagram](https://example.com/diagram.png)"
        )


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
