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
        path = ROOT / relative
        if relative and path.is_file():
            hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
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

        self.assertEqual(manifest["version"], "0.1.0-dev.3")
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



    def test_plugin_readme_boundary_removal_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            remove_text(
                root,
                submission_module.PLUGIN_README_RELATIVE,
                "Phase C desktop evidence is pending.",
            )

            self.assert_rejected(run_validator(root), "must state the boundary")

    def test_missing_plugin_readme_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            (root / submission_module.PLUGIN_README_RELATIVE).unlink()

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

    def test_support_additional_official_channel_at_document_end_fails(self):
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
            "Phase C desktop evidence is pending.",
            "All human prerequisites remain pending.",
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





    def test_safe_wording_passes_in_canonical_plugin_readme(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            self.assert_accepted(run_validator(root))

    def test_unsafe_english_assertion_after_safe_wording_fails(self):
        self.reject_portal_assertion(
            submission_module.PLUGIN_README_RELATIVE, "There is no portal draft."
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

    # --- Eleventh-remediation exact audit regressions -----------------------



    def test_eleventh_audit_explicit_surface_anaphoric_one_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            relative = submission_module.PLUGIN_README_RELATIVE
            append_text(
                root,
                relative,
                '\nThe example says "no pending entry". Nevertheless, '
                "the developer console shows one.\n",
            )

            result = run_validator(root)

            self.assert_rejected(
                result, "must not assert unverified external portal state"
            )
            self.assertIn(relative, result.stderr)
            self.assertIn("developer console shows one", result.stderr)

    def test_eleventh_audit_unchecked_blank_line_control_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(
                root,
                submission_module.PLUGIN_README_RELATIVE,
                '\nThe submission dashboard remains unchecked.\n\n'
                'The next paragraph explains the word "nonetheless".\n',
            )

            self.assert_accepted(run_validator(root))


PORTAL_REQUIRED_INVALID_CASES = (
    ("required_en_no_draft_exists", submission_module.PLUGIN_README_RELATIVE, "No draft exists in the OpenAI submission portal."),
    ("required_en_portal_has_no_draft", submission_module.PLUGIN_README_RELATIVE, "The portal has no draft."),
    ("required_en_no_portal_draft", submission_module.PLUGIN_README_RELATIVE, "There is no portal draft."),
    ("required_en_portal_empty", submission_module.PLUGIN_README_RELATIVE, "The submission portal is empty."),
    ("required_en_nothing_submitted", submission_module.PLUGIN_README_RELATIVE, "Nothing has been submitted through the portal."),
    ("required_en_draft_exists", submission_module.PLUGIN_README_RELATIVE, "A draft exists in the submission portal."),
    ("required_en_content_submitted", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the portal."),
)

# The 15 concrete false-PASS cases observed by the independent focused
# re-audit. Four deliberately overlap the canonical 19 so both evidence sets
# stay explicitly traceable in the test report.
PORTAL_OBSERVED_FALSE_PASS_CASES = (
    ("observed_en_content_submitted", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the portal."),
    ("observed_en_application_portal_saved_draft", submission_module.PLUGIN_README_RELATIVE, "The application portal contains a saved draft."),
    ("observed_en_pending_application_draft", submission_module.PLUGIN_README_RELATIVE, "A pending draft exists in the application portal."),
    ("observed_en_no_saved_application_draft", submission_module.PLUGIN_README_RELATIVE, "No saved draft exists in the application portal."),
    ("observed_en_submitted_soft_break", submission_module.PLUGIN_README_RELATIVE, "Content has already been submitted through the\nportal."),
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
)

PORTAL_FORMATTING_INVALID_CASES = (
    ("format_en_markdown_emphasis", submission_module.PLUGIN_README_RELATIVE, "The **application portal** has a **saved draft**."),
    ("format_en_html_emphasis", submission_module.PLUGIN_README_RELATIVE, "The <em>application portal</em> has a <strong>saved draft</strong>."),
    ("format_en_link", submission_module.PLUGIN_README_RELATIVE, "[A saved draft exists in the application portal](https://example.com)."),
    ("format_en_soft_break", submission_module.PLUGIN_README_RELATIVE, "A saved draft exists in the application\nportal."),
    ("format_en_case", submission_module.PLUGIN_README_RELATIVE, "THE APPLICATION PORTAL HAS A SAVED DRAFT."),
    ("format_en_whitespace", submission_module.PLUGIN_README_RELATIVE, "The application   portal has   a saved   draft."),
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
)

# Seventh-remediation F-06A audit vocabulary. Each case is an independent
# real-validator subprocess test so a failure names the exact lexical family.
F06_AUDIT_LEXICAL_INVALID_CASES = (
    ("f06a_en_saved_application_remains", submission_module.PLUGIN_README_RELATIVE, "A saved application remains in the review portal."),
    ("f06a_en_review_system_holds_material", submission_module.PLUGIN_README_RELATIVE, "The review system currently holds submitted material."),
    ("f06a_en_no_application_on_file", submission_module.PLUGIN_README_RELATIVE, "No application is on file in the portal."),
    ("f06a_en_dashboard_pending_application", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard contains a pending application."),
    ("f06a_en_portal_shows_awaiting_draft", submission_module.PLUGIN_README_RELATIVE, "The portal shows a draft awaiting review."),
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
    # Additional unseen inflections from the audited morphology families.
    ("inflect_en_held", submission_module.PLUGIN_README_RELATIVE, "The review portal held submitted material."),
    ("inflect_en_holding", submission_module.PLUGIN_README_RELATIVE, "The application console is holding a saved record."),
    ("inflect_en_remained", submission_module.PLUGIN_README_RELATIVE, "A saved application remained in the review portal."),
    ("inflect_en_registration_remains", submission_module.PLUGIN_README_RELATIVE, "An application registration record remains in the developer console."),
    ("inflect_en_registered", submission_module.PLUGIN_README_RELATIVE, "The application was registered in the submission system."),
)

F06_STRUCTURE_INVALID_CASES = (
    ("structure_en_parentheses", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate (a saved draft exists in the application portal)."),
    ("structure_en_square_brackets", submission_module.PLUGIN_README_RELATIVE, "Human review is required [the submission dashboard contains a pending application]."),
    ("structure_en_curly_brackets", submission_module.PLUGIN_README_RELATIVE, "The repository cannot determine the portal state {submitted content is present in the application system}."),
    ("structure_nested_parentheses", submission_module.PLUGIN_README_RELATIVE, "Human verification is required (the reviewer should check whether the portal contains a draft (a saved draft actually exists))."),
)

F06_SAFE_PLUS_UNSAFE_INVALID_CASES = (
    ("isolation_en_later_sentence", submission_module.PLUGIN_README_RELATIVE, "The reviewer must verify the portal. A saved draft exists there in the application portal."),
    ("isolation_en_contrast", submission_module.PLUGIN_README_RELATIVE, "Human verification is required, but the portal currently holds submitted material."),
    ("isolation_en_coordinated_clause", submission_module.PLUGIN_README_RELATIVE, "Human verification is required, and a saved draft exists in the portal."),
    ("isolation_en_future_semicolon", submission_module.PLUGIN_README_RELATIVE, "A future draft may be created; a saved draft currently exists in the portal."),
    ("isolation_list_items", submission_module.PLUGIN_README_RELATIVE, "- Portal state remains a human verification gate.\n- A saved draft exists in the application portal."),
)

F06_DISCOURSE_SAFE_CASES = (
    # English questions and scoped verification.
    ("discourse_en_determine_whether", submission_module.PLUGIN_README_RELATIVE, "The reviewer must determine whether a draft exists in the portal."),
    ("discourse_en_direct_question", submission_module.PLUGIN_README_RELATIVE, "Does a saved draft exist in the application portal? Human verification is required."),
    ("discourse_en_whether_remains", submission_module.PLUGIN_README_RELATIVE, "Whether submitted material remains in the review portal must be checked by a human."),
    ("discourse_en_cannot_determine_if", submission_module.PLUGIN_README_RELATIVE, "The repository cannot determine if an application is on file in the portal."),
    # Documentation, examples, and quoted terms.
    ("discourse_en_documentation", submission_module.PLUGIN_README_RELATIVE, "The portal documentation defines a field named \"draft\"."),
    ("discourse_en_fixture_example", submission_module.PLUGIN_README_RELATIVE, "The test fixture contains the phrase \"pending draft\" as an example."),
    ("discourse_en_term_example", submission_module.PLUGIN_README_RELATIVE, "This example explains the term \"submitted content\"."),
    # Future and hypothetical scopes.
    ("discourse_en_future", submission_module.PLUGIN_README_RELATIVE, "A future portal draft may be created after human approval."),
    ("discourse_en_hypothetical", submission_module.PLUGIN_README_RELATIVE, "If a draft is created in the portal, a human will review it."),
    ("discourse_en_future_will", submission_module.PLUGIN_README_RELATIVE, "A portal draft will be created after approval."),
    ("discourse_en_future_when", submission_module.PLUGIN_README_RELATIVE, "When a human later submits an application through the portal, it will be reviewed."),
    # Code content is removed before structural segmentation.
    ("discourse_inline_code", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate. `(a saved draft exists in the application portal)`"),
    ("discourse_fenced_code", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate.\n\n```text\n(a saved draft exists in the application portal)\n```"),
)

PRODUCT_STATUS_DISCOURSE_INVALID_CASES = (
)

# Eighth-remediation lexical closures. The six audited sentences and fresh
# inflections each execute the real validator against an isolated repository.
F06_PREDICATE_LEXICAL_INVALID_CASES = (
    ("predicate_lexical_en_shows_no_entry", submission_module.PLUGIN_README_RELATIVE, "The developer console shows no pending entry."),
    ("predicate_inflect_en_showing_entry", submission_module.PLUGIN_README_RELATIVE, "The application dashboard is showing a pending entry."),
    ("predicate_inflect_en_showed_entries", submission_module.PLUGIN_README_RELATIVE, "The review console showed no pending entries."),
)

# Safe operators and independent current predicates deliberately share one
# structural segment. Each named case proves that only the governed predicate
# is exempt, including cross-language coordination.
F06_PREDICATE_SCOPE_INVALID_CASES = (
    ("predicate_question_en_while", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether a draft exists while the review portal currently contains submitted material."),
    ("predicate_example_en_while", submission_module.PLUGIN_README_RELATIVE, "This is an explanatory example, while the portal currently contains a saved application."),
    ("predicate_repository_en_while", submission_module.PLUGIN_README_RELATIVE, "No portal action is performed or evidenced by this repository lane while a saved draft exists in the portal."),
    ("predicate_future_en_while", submission_module.PLUGIN_README_RELATIVE, "A draft may be created later while the portal currently holds submitted material."),
    ("predicate_coord_en_whereas", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether a draft exists whereas the portal currently stores submitted material."),
    ("predicate_coord_en_and", submission_module.PLUGIN_README_RELATIVE, "Human verification is required and a saved draft exists in the portal."),
    ("predicate_coord_en_comma", submission_module.PLUGIN_README_RELATIVE, "This is a documentation example, the application console currently holds a saved record."),
)

F06_PREDICATE_SAFE_CASES = (
    ("predicate_safe_en_question", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether a draft exists in the portal."),
    ("predicate_safe_en_human_question", submission_module.PLUGIN_README_RELATIVE, "Human verification is required to determine whether the portal contains submitted material."),
    ("predicate_safe_en_example", submission_module.PLUGIN_README_RELATIVE, "This example explains the phrase \"submitted material is present in the portal\"."),
    ("predicate_safe_en_hypothetical", submission_module.PLUGIN_README_RELATIVE, "If a draft is created later, a human must review it."),
)

F06_JA_AVAILABILITY_INVALID_CASES = (
)

F06_JA_AVAILABILITY_SAFE_CASES = (
)

# Ninth-remediation fixed audit corpus. Every tuple becomes one independently
# named real-validator subprocess against a fresh temporary repository copy.
# The named audit groups preserve the exact ten false-PASS and six false-reject
# observations; the remaining groups exercise the architecture
# around them instead of teaching the validator only those observed strings.
F06_CONTEXT_AUDIT_FALSE_PASS_CASES = (
    ("ninth_audit_fp01_en_repository_even_though", submission_module.PLUGIN_README_RELATIVE, "The repository cannot determine the portal state, even though a lodged application remains on file."),
    ("ninth_audit_fp02_en_portal_and_contains", submission_module.PLUGIN_README_RELATIVE, "The application portal must be checked, and currently contains submitted material."),
    ("ninth_audit_fp03_en_console_but_entry", submission_module.PLUGIN_README_RELATIVE, "The developer console is under review but shows no pending entry."),
    ("ninth_audit_fp04_en_human_semicolon", submission_module.PLUGIN_README_RELATIVE, "Human verification is required; nevertheless, it already contains a saved draft."),
    ("ninth_audit_fp05_en_em_dash", submission_module.PLUGIN_README_RELATIVE, "The portal state is unknown — submitted content is already present."),
    ("ninth_audit_fp06_en_parenthetical", submission_module.PLUGIN_README_RELATIVE, "The portal must be reviewed (currently contains a saved application)."),
    ("ninth_audit_fp07_en_square_bracket", submission_module.PLUGIN_README_RELATIVE, "The portal state remains unverified [the review queue holds a pending form]."),
    ("ninth_audit_fp08_en_curly_bracket", submission_module.PLUGIN_README_RELATIVE, "Human review is required {it already stores submitted material}."),
)

F06_CONTEXT_REQUIRED_INVALID_CASES = (
)

F06_CONTEXT_AUDIT_FALSE_REJECT_CASES = (
    ("ninth_audit_fr04_en_quoted_separator", submission_module.PLUGIN_README_RELATIVE, "The example phrase is \"draft exists, but submission is pending\"."),
)

F06_BOUNDED_CONTEXT_INVALID_CASES = (
    ("ninth_near_en_semicolon_pronoun", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review; it already contains a draft."),
    ("ninth_near_en_colon_omitted_subject", submission_module.PLUGIN_README_RELATIVE, "The review portal remains unverified: submitted material is already present."),
)

F06_BOUNDED_CONTEXT_SAFE_CASES = (
    ("ninth_far_en_blank_line", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review.\n\nThe next section explains validator architecture."),
    ("ninth_far_en_heading_reset", submission_module.PLUGIN_README_RELATIVE, "## Portal review\nThe portal state requires human verification.\n\n## Test examples\nThe phrase \"submitted material\" is used as an example."),
    ("ninth_far_en_unrelated_database", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review.\n\nThe database contains submitted material used by a local fixture."),
    ("ninth_far_en_independent_sentence_reset", submission_module.PLUGIN_README_RELATIVE, "The portal requires review. The archive contains a saved record for a fixture."),
)

F06_PARENT_CHILD_INVALID_CASES = (
    ("ninth_parent_nested_en_square", submission_module.PLUGIN_README_RELATIVE, "The portal must be checked (status unknown [submitted content is already present])."),
    ("ninth_parent_nested_en_curly", submission_module.PLUGIN_README_RELATIVE, "Human verification is required [review pending {it already holds a saved draft}]."),
    ("ninth_parent_quote_then_real_assertion", submission_module.PLUGIN_README_RELATIVE, "The example phrase is \"draft exists, but submission is pending\"; the portal currently contains submitted material."),
)

F06_PARENT_CHILD_SAFE_CASES = (
    ("ninth_parent_safe_en_whether", submission_module.PLUGIN_README_RELATIVE, "The portal must be checked (whether it contains submitted material)."),
)

F06_MARKDOWN_CONTEXT_INVALID_CASES = (
    ("ninth_markdown_en_strong", submission_module.PLUGIN_README_RELATIVE, "The application portal must be checked, and **currently contains submitted material**."),
    ("ninth_markdown_en_html_emphasis", submission_module.PLUGIN_README_RELATIVE, "The developer console must be checked; <em>it already contains a saved draft</em>."),
    ("ninth_markdown_en_linked_antecedent", submission_module.PLUGIN_README_RELATIVE, "The [application portal](https://example.invalid) must be checked, and currently contains submitted material."),
    ("ninth_markdown_en_entity_dash", submission_module.PLUGIN_README_RELATIVE, "The portal state is unknown &mdash; submitted content is already present."),
    ("ninth_markdown_en_soft_break", submission_module.PLUGIN_README_RELATIVE, "The application portal must be checked,\nand currently contains submitted material."),
)

F06_MARKDOWN_CONTEXT_SAFE_CASES = (
    ("ninth_quote_single_en", submission_module.PLUGIN_README_RELATIVE, "The example phrase is 'draft exists, but submission is pending'."),
    ("ninth_quote_curly_en", submission_module.PLUGIN_README_RELATIVE, "The example phrase is “draft exists; submission is pending”."),
)


# Tenth-remediation continuation-context corpus. The first five cases are the
# independently observed false-PASSes: the structural separator was consumed,
# so the following span lost the portal/surface antecedent. The sixth case
# Every tuple still runs the real validator subprocess against
# its own fresh repository copy through the factories below.
F06_CONTINUATION_CONTEXT_FALSE_PASS_CASES = (
    ("tenth_audit_fp01_en_nevertheless", submission_module.PLUGIN_README_RELATIVE, "The application portal must be checked. Nevertheless, submitted material is already present."),
    ("tenth_audit_fp02_en_even_so", submission_module.PLUGIN_README_RELATIVE, "The developer dashboard remains unverified. Even so, it currently holds a pending application."),
)

F06_CONTINUATION_VARIANT_INVALID_CASES = (
)


def portal_context_distance_case(distance: int) -> str:
    """Put the state object exactly ``distance`` source characters after
    the end of its portal antecedent.
    """
    antecedent = "The application portal requires review"
    padding = "x" * (distance - 2) + " "
    return f"{antecedent};{padding}submitted material is already present."


F06_CONTEXT_SOURCE_DISTANCE_INVALID_CASES = (
    ("tenth_distance_before_bound", submission_module.PLUGIN_README_RELATIVE, portal_context_distance_case(submission_module.MAX_PORTAL_CONTEXT_SOURCE_DISTANCE - 1)),
    ("tenth_distance_at_bound", submission_module.PLUGIN_README_RELATIVE, portal_context_distance_case(submission_module.MAX_PORTAL_CONTEXT_SOURCE_DISTANCE)),
)

F06_CONTINUATION_CONTEXT_SAFE_CASES = (
    # The one observed long-distance false reject: the span begins nearby, but
    # its actual state object/predicate begins just beyond the source bound.
    ("tenth_audit_fr01_after_distance_bound", submission_module.PLUGIN_README_RELATIVE, portal_context_distance_case(submission_module.MAX_PORTAL_CONTEXT_SOURCE_DISTANCE + 1)),
    ("eleventh_after_distance_bound_plus_40", submission_module.PLUGIN_README_RELATIVE, portal_context_distance_case(submission_module.MAX_PORTAL_CONTEXT_SOURCE_DISTANCE + 40)),
    ("tenth_hard_reset_plain_sentence", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review. Submitted material is already present."),
    ("tenth_hard_reset_blank_line", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review.\n\nNevertheless, submitted material is already present."),
    # A continuation operator may use only its nearest structural antecedent;
    # it must not jump over unrelated prose to find an older portal mention.
    ("tenth_nearest_antecedent_only", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review. The local archive is described here. Nevertheless, submitted material is already present."),
)


# Eleventh-remediation variants exercise the semantic families around the four
# exact audit cases above. Each tuple is still a fresh-copy real-validator
# subprocess test generated by the same factories as all earlier F-06 cases.
F06_RESIDUAL_CONTINUATION_INVALID_CASES = (
)

F06_RESIDUAL_NECESSARY_INVALID_CASES = (
)

F06_RESIDUAL_ANAPHORIC_INVALID_CASES = (
    ("eleventh_anaphoric_dashboard_displays_one", submission_module.PLUGIN_README_RELATIVE, "The application dashboard must be checked. However, it displays one."),
    ("eleventh_anaphoric_console_another_one", submission_module.PLUGIN_README_RELATIVE, "The review console remains unverified, but contains another one."),
    ("eleventh_anaphoric_page_pending_item", submission_module.PLUGIN_README_RELATIVE, "The submission page is unchecked. Even so, it holds one pending item."),
    ("eleventh_anaphoric_portal_such_entry", submission_module.PLUGIN_README_RELATIVE, "The developer portal must be reviewed; it stores one such entry."),
    ("eleventh_anaphoric_near_unchecked", submission_module.PLUGIN_README_RELATIVE, "The review dashboard remains unchecked. Nonetheless, it displays one."),
    ("eleventh_anaphoric_near_example_reset", submission_module.PLUGIN_README_RELATIVE, 'The example defines "no draft". However, the application portal contains one.'),
    ("eleventh_anaphoric_markdown_comment", submission_module.PLUGIN_README_RELATIVE, 'The example says "no pending entry". Nevertheless, the developer console sh<!-- split -->ows one.'),
)

F06_RESIDUAL_VERIFICATION_COMBINED_INVALID_CASES = (
    ("eleventh_verification_unchecked_contains", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard remains unchecked, but contains a saved application."),
    ("eleventh_verification_unverified_shows", submission_module.PLUGIN_README_RELATIVE, "The developer console remains unverified and shows one pending entry."),
    ("eleventh_verification_not_checked_present", submission_module.PLUGIN_README_RELATIVE, "The application portal has not been checked; nevertheless, submitted material is present."),
    ("eleventh_verification_awaiting_stores", submission_module.PLUGIN_README_RELATIVE, "The review interface is awaiting human verification while it stores a draft."),
)

F06_RESIDUAL_SAFE_CASES = (
    ("eleventh_safe_anaphoric_question", submission_module.PLUGIN_README_RELATIVE, "Does the developer console show one pending entry?"),
    ("eleventh_safe_anaphoric_example", submission_module.PLUGIN_README_RELATIVE, 'The test example contains the word "one".'),
    ("eleventh_safe_anaphoric_future", submission_module.PLUGIN_README_RELATIVE, "One possible future entry may be displayed after submission."),
    ("eleventh_safe_anaphoric_number", submission_module.PLUGIN_README_RELATIVE, "The number one appears in this field description."),
    ("eleventh_safe_verification_unchecked", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard remains unchecked."),
    ("eleventh_safe_verification_unverified", submission_module.PLUGIN_README_RELATIVE, "The developer console remains unverified."),
    ("eleventh_safe_verification_not_checked", submission_module.PLUGIN_README_RELATIVE, "The application portal has not been checked."),
    ("eleventh_safe_verification_awaiting", submission_module.PLUGIN_README_RELATIVE, "The review interface is awaiting human verification."),
    ("eleventh_safe_verification_human_review", submission_module.PLUGIN_README_RELATIVE, "The submission page still requires human review."),
    ("eleventh_safe_near_review_unchecked", submission_module.PLUGIN_README_RELATIVE, "The review dashboard remains unchecked."),
    ("eleventh_safe_near_documentation_one", submission_module.PLUGIN_README_RELATIVE, 'The documentation explains the pronoun "one".'),
)


# Twelfth-remediation F-06R1-C corpus. The five audit identifiers preserve the
# exact independent failing strings; the nearby variants prove that generic
# UI nouns do not supply portal context, while list/present inflections remain
# material predicates on explicitly qualified or bounded portal surfaces.
F06_TWELFTH_GENERIC_SURFACE_SAFE_CASES = (
    ("twelfth_audit_ov02_performance_dashboard", submission_module.PLUGIN_README_RELATIVE, "The performance dashboard shows one active worker."),
    ("twelfth_audit_ov03_local_build_console", submission_module.PLUGIN_README_RELATIVE, "The local build console displays another one after the retry."),
    ("twelfth_audit_ov04_documentation_site", submission_module.PLUGIN_README_RELATIVE, "The documentation site contains one navigation example."),
    ("twelfth_generic_analytics_dashboard_list", submission_module.PLUGIN_README_RELATIVE, "The analytics dashboard lists another one in the chart."),
    ("twelfth_generic_monitoring_dashboard_present", submission_module.PLUGIN_README_RELATIVE, "The monitoring dashboard presents one pending alert."),
    ("twelfth_generic_runtime_console_listing", submission_module.PLUGIN_README_RELATIVE, "The local runtime console is listing one fixture."),
    ("twelfth_generic_test_console_presented", submission_module.PLUGIN_README_RELATIVE, "The test console presented one example."),
    ("twelfth_generic_documentation_page_shows", submission_module.PLUGIN_README_RELATIVE, "The documentation page shows another one below."),
    ("twelfth_generic_product_dashboard_contains", submission_module.PLUGIN_README_RELATIVE, "The product dashboard contains one active subscription."),
    ("twelfth_generic_support_site_lists", submission_module.PLUGIN_README_RELATIVE, "The support site lists another one in a sample table."),
)

F06_TWELFTH_MATERIAL_PREDICATE_INVALID_CASES = (
    ("twelfth_audit_ci03_lists", submission_module.PLUGIN_README_RELATIVE, "The developer console remains unverified. Even so, it lists another one."),
    ("twelfth_audit_ci04_presents", submission_module.PLUGIN_README_RELATIVE, "The review dashboard needs checking; it presents one pending item."),
    ("twelfth_list_base", submission_module.PLUGIN_README_RELATIVE, "The submission portal and review queue list another one."),
    ("twelfth_listed", submission_module.PLUGIN_README_RELATIVE, "The review portal listed one pending item."),
    ("twelfth_listing", submission_module.PLUGIN_README_RELATIVE, "The application console is listing one such entry."),
    ("twelfth_present_base", submission_module.PLUGIN_README_RELATIVE, "The review portal and submission queue present another one."),
    ("twelfth_presented", submission_module.PLUGIN_README_RELATIVE, "The application portal presented one pending item."),
    ("twelfth_presenting", submission_module.PLUGIN_README_RELATIVE, "The developer console is presenting one such entry."),
    ("twelfth_list_markdown", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard remains unchecked; it **lists another one**."),
    ("twelfth_present_inherited", submission_module.PLUGIN_README_RELATIVE, "The review workspace requires confirmation. Nevertheless, it presents one pending item."),
)

F06_TWELFTH_SAFE_SCOPE_CASES = (
    ("twelfth_safe_quote_lists", submission_module.PLUGIN_README_RELATIVE, "The guide quotes “the review portal lists another one” as a prohibited example."),
    ("twelfth_safe_quote_presents", submission_module.PLUGIN_README_RELATIVE, 'The example sentence is "the developer console presents one pending item".'),
    ("twelfth_safe_question_list", submission_module.PLUGIN_README_RELATIVE, "Does the review portal list another one?"),
    ("twelfth_safe_question_present", submission_module.PLUGIN_README_RELATIVE, "Could the application dashboard present one pending item?"),
    ("twelfth_safe_future_list", submission_module.PLUGIN_README_RELATIVE, "The developer console may list another one after a future submission."),
    ("twelfth_safe_future_present", submission_module.PLUGIN_README_RELATIVE, "The review portal will present one pending item later."),
    ("twelfth_safe_hypothetical_list", submission_module.PLUGIN_README_RELATIVE, "If the submission portal listed another one, the test would report it."),
    ("twelfth_safe_hypothetical_present", submission_module.PLUGIN_README_RELATIVE, "The application dashboard would present one pending item in that scenario."),
    ("twelfth_safe_presentation_example", submission_module.PLUGIN_README_RELATIVE, "The review dashboard presents one example below."),
    ("twelfth_safe_presentation_diagram", submission_module.PLUGIN_README_RELATIVE, "The developer console presents one diagram for the reviewer."),
    ("twelfth_safe_verify_list", submission_module.PLUGIN_README_RELATIVE, "The reviewer asks whether the developer console lists another one."),
    ("twelfth_safe_verify_present", submission_module.PLUGIN_README_RELATIVE, "Please verify whether the review dashboard presents one pending item."),
)


# Thirteenth-remediation semantic-classifier corpus. These are 125 new,
# individually named, fresh-copy real-validator subprocess cases: the exact 21
# independent failures plus the 104-case matrix required by the remediation
# contract. Surface, actuality, object, and predicate expectations are also
# asserted for representative cases without replacing the subprocess check.
F06_THIRTEENTH_EXACT_FALSE_PASS_CASES = (
    ("thirteenth_exact_pi_i_21", submission_module.PLUGIN_README_RELATIVE, "The review portal lists one returned item."),
    ("thirteenth_exact_pi_i_24", submission_module.PLUGIN_README_RELATIVE, "The developer portal presents one completed item."),
    ("thirteenth_exact_pi_i_25", submission_module.PLUGIN_README_RELATIVE, "The review dashboard presents one approved item."),
    ("thirteenth_exact_pi_i_26", submission_module.PLUGIN_README_RELATIVE, "The developer console lists one returned item."),
    ("thirteenth_exact_pi_i_27", submission_module.PLUGIN_README_RELATIVE, "The review portal lists one completed item."),
    ("thirteenth_exact_pi_i_28", submission_module.PLUGIN_README_RELATIVE, "The developer dashboard presents one rejected item."),
)

F06_THIRTEENTH_EXACT_GENERIC_FALSE_REJECT_CASES = (
    ("thirteenth_exact_gn_v_17", submission_module.PLUGIN_README_RELATIVE, "The performance dashboard shows one application latency metric."),
    ("thirteenth_exact_gn_v_18", submission_module.PLUGIN_README_RELATIVE, "The documentation site lists one application configuration sample."),
    ("thirteenth_exact_gn_v_22", submission_module.PLUGIN_README_RELATIVE, "The security console listed one application firewall rule."),
    ("thirteenth_exact_gn_v_23", submission_module.PLUGIN_README_RELATIVE, "The docs site presents one submission-format example."),
    ("thirteenth_exact_gn_v_25", submission_module.PLUGIN_README_RELATIVE, "The performance console presents one application health overview."),
    ("thirteenth_exact_gn_v_26", submission_module.PLUGIN_README_RELATIVE, "The documentation page lists one submission schema field."),
    ("thirteenth_exact_pr_v_09", submission_module.PLUGIN_README_RELATIVE, "The application dashboard presents one design example."),
    ("thirteenth_exact_pr_v_11", submission_module.PLUGIN_README_RELATIVE, "The submission site presents one documentation example."),
    ("thirteenth_exact_pr_v_13", submission_module.PLUGIN_README_RELATIVE, "The application console presents one operational runbook diagram."),
    ("thirteenth_exact_pr_v_14", submission_module.PLUGIN_README_RELATIVE, "The submission dashboard presents one schema documentation example."),
)

F06_THIRTEENTH_EXACT_HYPOTHETICAL_FALSE_REJECT_CASES = (
    ("thirteenth_exact_pr_v_07", submission_module.PLUGIN_README_RELATIVE, "The review portal would present one pending item in that hypothetical scenario."),
    ("thirteenth_exact_sc_v_05", submission_module.PLUGIN_README_RELATIVE, "The application dashboard might list one pending entry in a hypothetical demo."),
    ("thirteenth_exact_sc_v_14", submission_module.PLUGIN_README_RELATIVE, "The application portal might present one saved record in a hypothetical test."),
)

F06_THIRTEENTH_PORTAL_MATERIAL_STATE_INVALID_CASES = (
    ("thirteenth_material_review_returned_application", submission_module.PLUGIN_README_RELATIVE, "The review portal shows one returned application."),
    ("thirteenth_material_submission_approved_submission", submission_module.PLUGIN_README_RELATIVE, "The submission portal contains an approved submission."),
    ("thirteenth_material_application_completed_item", submission_module.PLUGIN_README_RELATIVE, "The application portal holds one completed review item."),
    ("thirteenth_material_developer_rejected_entry", submission_module.PLUGIN_README_RELATIVE, "The developer portal displays a rejected entry."),
    ("thirteenth_material_dashboard_returned_application", submission_module.PLUGIN_README_RELATIVE, "The review dashboard lists one returned application."),
    ("thirteenth_material_console_approved_item", submission_module.PLUGIN_README_RELATIVE, "The developer console presents an approved item."),
    ("thirteenth_material_submission_completed_item", submission_module.PLUGIN_README_RELATIVE, "The submission console shows a completed item."),
    ("thirteenth_material_application_rejected_item", submission_module.PLUGIN_README_RELATIVE, "The application dashboard contains a rejected item."),
    ("thirteenth_material_site_returned_record", submission_module.PLUGIN_README_RELATIVE, "The review site stores one returned record."),
    ("thirteenth_material_workspace_approved_application", submission_module.PLUGIN_README_RELATIVE, "The submission workspace displays an approved application."),
    ("thirteenth_material_interface_completed_submission", submission_module.PLUGIN_README_RELATIVE, "The application interface lists a completed submission."),
    ("thirteenth_material_screen_rejected_form", submission_module.PLUGIN_README_RELATIVE, "The developer screen presents a rejected form."),
    ("thirteenth_material_portal_has_returned_item", submission_module.PLUGIN_README_RELATIVE, "The portal has a returned item."),
    ("thirteenth_material_portal_has_approved_item", submission_module.PLUGIN_README_RELATIVE, "The portal has one approved item."),
    ("thirteenth_material_portal_holds_completed_item", submission_module.PLUGIN_README_RELATIVE, "The portal currently holds a completed item."),
    ("thirteenth_material_portal_contains_rejected_item", submission_module.PLUGIN_README_RELATIVE, "The portal contains another rejected item."),
    ("thirteenth_material_portal_records_returned_item", submission_module.PLUGIN_README_RELATIVE, "The review portal records a returned item."),
    ("thirteenth_material_portal_showing_approved_item", submission_module.PLUGIN_README_RELATIVE, "The developer portal is showing an approved item."),
    ("thirteenth_material_portal_displaying_completed_item", submission_module.PLUGIN_README_RELATIVE, "The submission portal is displaying a completed item."),
    ("thirteenth_material_portal_listing_rejected_item", submission_module.PLUGIN_README_RELATIVE, "The application portal is listing a rejected item."),
    ("thirteenth_material_returned_application_exists", submission_module.PLUGIN_README_RELATIVE, "A returned application exists in the review portal."),
    ("thirteenth_material_approved_submission_present", submission_module.PLUGIN_README_RELATIVE, "An approved submission is present in the developer portal."),
    ("thirteenth_material_completed_item_remains", submission_module.PLUGIN_README_RELATIVE, "A completed item remains in the submission portal."),
    ("thirteenth_material_rejected_item_on_file", submission_module.PLUGIN_README_RELATIVE, "A rejected item is currently on file in the application portal."),
)

F06_THIRTEENTH_GENERIC_PRESENTATION_SAFE_CASES = (
    ("thirteenth_generic_function_returned_value", submission_module.PLUGIN_README_RELATIVE, "The function returned one item from the local cache."),
    ("thirteenth_generic_code_review_approved", submission_module.PLUGIN_README_RELATIVE, "The code review approved one refactoring item."),
    ("thirteenth_generic_task_completed", submission_module.PLUGIN_README_RELATIVE, "The task console shows one completed maintenance task."),
    ("thirteenth_generic_hypothesis_rejected", submission_module.PLUGIN_README_RELATIVE, "The analysis dashboard lists one rejected hypothesis."),
    ("thirteenth_generic_returned_goods", submission_module.PLUGIN_README_RELATIVE, "The warehouse dashboard lists one returned item of stock."),
    ("thirteenth_generic_completed_presentation", submission_module.PLUGIN_README_RELATIVE, "The event site presents one completed presentation recording."),
    ("thirteenth_generic_approved_design", submission_module.PLUGIN_README_RELATIVE, "The design console presents one approved color option."),
    ("thirteenth_generic_rejected_build", submission_module.PLUGIN_README_RELATIVE, "The build dashboard shows one rejected artifact checksum."),
    ("thirteenth_generic_analytics_application_metric", submission_module.PLUGIN_README_RELATIVE, "The analytics dashboard displays an application throughput metric."),
    ("thirteenth_generic_docs_application_tutorial", submission_module.PLUGIN_README_RELATIVE, "The documentation site lists an application tutorial chapter."),
    ("thirteenth_generic_security_application_rule", submission_module.PLUGIN_README_RELATIVE, "The security console presents an application routing rule."),
    ("thirteenth_generic_report_submission_volume", submission_module.PLUGIN_README_RELATIVE, "The reporting site shows one submission-volume chart."),
    ("thirteenth_generic_schema_submission_field", submission_module.PLUGIN_README_RELATIVE, "The schema page lists a submission identifier field."),
    ("thirteenth_generic_runbook_review_diagram", submission_module.PLUGIN_README_RELATIVE, "The runbook site presents one review workflow diagram."),
    ("thirteenth_generic_slide_application_architecture", submission_module.PLUGIN_README_RELATIVE, "The slide console presents one application architecture illustration."),
    ("thirteenth_generic_demo_submission_format", submission_module.PLUGIN_README_RELATIVE, "The demo dashboard lists one submission-format sample."),
    ("thirteenth_generic_monitoring_review_latency", submission_module.PLUGIN_README_RELATIVE, "The monitoring dashboard contains one review latency series."),
    ("thirteenth_generic_local_application_fixture", submission_module.PLUGIN_README_RELATIVE, "The local console stores one application fixture record."),
    ("thirteenth_generic_docs_submission_example", submission_module.PLUGIN_README_RELATIVE, "The developer documentation site presents one submission example."),
    ("thirteenth_generic_presentation_lists_agenda", submission_module.PLUGIN_README_RELATIVE, "The presentation lists one review topic on its agenda."),
    ("thirteenth_generic_presenter_presents_slide", submission_module.PLUGIN_README_RELATIVE, "The presenter presents one application design slide."),
    ("thirteenth_generic_report_lists_item", submission_module.PLUGIN_README_RELATIVE, "The report lists one item from the inventory."),
    ("thirteenth_generic_visualization_presents_one", submission_module.PLUGIN_README_RELATIVE, "The visualization presents one rejected outlier for discussion."),
    ("thirteenth_generic_site_completed_demo", submission_module.PLUGIN_README_RELATIVE, "The training site contains one completed demo exercise."),
)

F06_THIRTEENTH_HYPOTHETICAL_SAFE_CASES = (
    ("thirteenth_hyp_if_approved_item", submission_module.PLUGIN_README_RELATIVE, "If the submission portal listed another approved item, we would investigate."),
    ("thirteenth_hyp_if_were_returned", submission_module.PLUGIN_README_RELATIVE, "If the review portal were to show a returned item, the mock would fail."),
    ("thirteenth_hyp_were_to_completed", submission_module.PLUGIN_README_RELATIVE, "Were the developer portal to present a completed item, the test would record it."),
    ("thirteenth_hyp_would_rejected", submission_module.PLUGIN_README_RELATIVE, "The application portal would list a rejected item in that scenario."),
    ("thirteenth_hyp_could_returned", submission_module.PLUGIN_README_RELATIVE, "The review dashboard could display one returned item in a simulation."),
    ("thirteenth_hyp_might_approved", submission_module.PLUGIN_README_RELATIVE, "The developer console might show an approved item during a mock run."),
    ("thirteenth_hyp_may_completed", submission_module.PLUGIN_README_RELATIVE, "The submission portal may contain a completed item after a future filing."),
    ("thirteenth_hyp_suppose_rejected", submission_module.PLUGIN_README_RELATIVE, "Suppose the review portal presented one rejected item."),
    ("thirteenth_hyp_assuming_returned", submission_module.PLUGIN_README_RELATIVE, "Assuming the application console lists a returned item, the fixture should fail."),
    ("thirteenth_hyp_scenario_approved", submission_module.PLUGIN_README_RELATIVE, "In a hypothetical scenario, the developer dashboard shows one approved item."),
    ("thirteenth_hyp_example_if_completed", submission_module.PLUGIN_README_RELATIVE, "For example, if the portal contained a completed item, the probe would reject it."),
    ("thirteenth_hyp_unless_rejected", submission_module.PLUGIN_README_RELATIVE, "Unless the submission portal lists a rejected item, the branch stays unchanged."),
    ("thirteenth_hyp_should_later_returned", submission_module.PLUGIN_README_RELATIVE, "Should the review portal later display a returned item, a human would inspect it."),
    ("thirteenth_hyp_conditional_approved", submission_module.PLUGIN_README_RELATIVE, "In a conditional walkthrough, the developer portal presents an approved item."),
    ("thirteenth_hyp_counterfactual_completed", submission_module.PLUGIN_README_RELATIVE, "In a counterfactual case, the application portal lists a completed item."),
    ("thirteenth_hyp_if_portal_had_rejected", submission_module.PLUGIN_README_RELATIVE, "If the review portal had a rejected item, the example would mention it."),
    ("thirteenth_hyp_assuming_dashboard_approved", submission_module.PLUGIN_README_RELATIVE, "Assuming the submission dashboard displayed an approved item, the demo would highlight it."),
    ("thirteenth_hyp_suppose_console_completed", submission_module.PLUGIN_README_RELATIVE, "Suppose the developer console lists one completed item for the exercise."),
    ("thirteenth_hyp_might_portal_return", submission_module.PLUGIN_README_RELATIVE, "A future application portal might return one item during the simulation."),
    ("thirteenth_hyp_would_portal_approve", submission_module.PLUGIN_README_RELATIVE, "A future review portal would approve one item in the hypothetical test."),
)

F06_THIRTEENTH_MIXED_SCOPE_INVALID_CASES = (
    ("thirteenth_scope_if_then_current_pronoun", submission_module.PLUGIN_README_RELATIVE, "If the portal changes later, we will investigate. It currently lists another approved item."),
    ("thirteenth_scope_hyp_then_current_portal", submission_module.PLUGIN_README_RELATIVE, "In a hypothetical scenario the portal lists a returned item; the portal currently shows an approved item."),
    ("thirteenth_scope_suppose_then_now", submission_module.PLUGIN_README_RELATIVE, "Suppose the review portal presented a rejected item; however, the review portal now contains a completed item."),
    ("thirteenth_scope_assuming_then_actual", submission_module.PLUGIN_README_RELATIVE, "Assuming the developer console lists a returned item, the test is useful, but the developer console actually shows an approved item."),
    ("thirteenth_scope_unless_then_current", submission_module.PLUGIN_README_RELATIVE, "Unless the application portal displays a completed item, the demo passes; the application portal currently holds a rejected item."),
    ("thirteenth_scope_counterfactual_then_now", submission_module.PLUGIN_README_RELATIVE, "In a counterfactual walkthrough the portal presents an approved item. The portal now lists a returned item."),
    ("thirteenth_scope_future_then_already", submission_module.PLUGIN_README_RELATIVE, "The submission portal might show a rejected item later, but it already contains a completed item."),
    ("thirteenth_scope_question_then_current", submission_module.PLUGIN_README_RELATIVE, "Could the review portal list a returned item? The review portal currently presents an approved item."),
    ("thirteenth_scope_quote_then_current", submission_module.PLUGIN_README_RELATIVE, "The guide quotes ‘the portal lists a completed item’; the portal currently shows a rejected item."),
    ("thirteenth_scope_example_then_current", submission_module.PLUGIN_README_RELATIVE, "For example, if the developer portal showed an approved item, we would inspect it; the developer portal now lists a returned item."),
    ("thirteenth_scope_should_then_actual", submission_module.PLUGIN_README_RELATIVE, "Should the application console later list a completed item, the mock will fail, whereas the application console actually contains a rejected item."),
    ("thirteenth_scope_may_then_current", submission_module.PLUGIN_README_RELATIVE, "The review dashboard may display a returned item in a future demo. It currently presents one approved item."),
)

F06_THIRTEENTH_SCOPE_CONTROL_SAFE_CASES = (
    ("thirteenth_control_quote_returned", submission_module.PLUGIN_README_RELATIVE, "The guide quotes ‘the review portal lists a returned item’ as prohibited wording."),
    ("thirteenth_control_quote_approved", submission_module.PLUGIN_README_RELATIVE, "The phrase \"the developer console shows an approved item\" is a test fixture."),
    ("thirteenth_control_question_completed", submission_module.PLUGIN_README_RELATIVE, "Does the submission portal contain a completed item?"),
    ("thirteenth_control_question_rejected", submission_module.PLUGIN_README_RELATIVE, "Could the application portal present a rejected item?"),
    ("thirteenth_control_verify_returned", submission_module.PLUGIN_README_RELATIVE, "Please verify whether the review dashboard lists a returned item."),
    ("thirteenth_control_verify_approved", submission_module.PLUGIN_README_RELATIVE, "A human must determine whether the developer portal shows an approved item."),
    ("thirteenth_control_future_completed", submission_module.PLUGIN_README_RELATIVE, "The submission console will list a completed item after human approval."),
    ("thirteenth_control_future_rejected", submission_module.PLUGIN_README_RELATIVE, "A future application portal may display a rejected item."),
    ("thirteenth_control_example_returned", submission_module.PLUGIN_README_RELATIVE, "This example explains how a review portal could show a returned item."),
    ("thirteenth_control_example_approved", submission_module.PLUGIN_README_RELATIVE, "The documentation presents ‘approved item’ as an example term."),
    ("thirteenth_control_repository_boundary", submission_module.PLUGIN_README_RELATIVE, "No portal action is performed or evidenced by this repository lane."),
    ("thirteenth_control_human_gate", submission_module.PLUGIN_README_RELATIVE, "Portal state remains a human verification gate."),
)

F06_THIRTEENTH_CONTEXT_INVALID_CASES = (
    ("thirteenth_context_continuation_returned", submission_module.PLUGIN_README_RELATIVE, "The review portal remains unchecked. Nevertheless, it lists a returned item."),
    ("thirteenth_context_semicolon_approved", submission_module.PLUGIN_README_RELATIVE, "The developer console needs verification; it presents an approved item."),
    ("thirteenth_context_parenthetical_completed", submission_module.PLUGIN_README_RELATIVE, "The submission portal requires review (it contains a completed item)."),
    ("thirteenth_context_bracket_rejected", submission_module.PLUGIN_README_RELATIVE, "The application dashboard is unverified [it shows a rejected item]."),
    ("thirteenth_context_pronoun_current_returned", submission_module.PLUGIN_README_RELATIVE, "The review portal may change later. It currently contains a returned item."),
    ("thirteenth_context_nearest_approved", submission_module.PLUGIN_README_RELATIVE, "The developer portal requires inspection. Even so, it presents an approved item."),
)

F06_THIRTEENTH_CONTEXT_SAFE_CASES = (
    ("thirteenth_reset_sentence_plain", submission_module.PLUGIN_README_RELATIVE, "The review portal requires inspection. Returned material is described in the local fixture."),
    ("thirteenth_reset_blank_paragraph", submission_module.PLUGIN_README_RELATIVE, "The developer portal needs verification.\n\nThe report lists a completed task."),
    ("thirteenth_reset_heading", submission_module.PLUGIN_README_RELATIVE, "The submission portal remains unchecked.\n\n## Training report\n\nThe dashboard presents an approved design sample."),
    ("thirteenth_reset_list", submission_module.PLUGIN_README_RELATIVE, "The application portal requires review.\n\n- The local console lists one returned stock item."),
    ("thirteenth_reset_nearest_surface", submission_module.PLUGIN_README_RELATIVE, "The review portal needs inspection. The analytics dashboard is documented. Nevertheless, it lists one completed exercise."),
    ("thirteenth_reset_source_distance", submission_module.PLUGIN_README_RELATIVE, "The developer portal requires confirmation;" + ("q" * 245) + " lists one returned warehouse item."),
)

F06_THIRTEENTH_ROLE_EXPECTATIONS = {
    "thirteenth_exact_pi_i_21": submission_module.PortalSemanticRoles(
        submission_module.SurfaceContext.GOVERNED_PORTAL,
        submission_module.Actuality.CURRENT_ASSERTION,
        submission_module.ObjectKind.STRONG_MATERIAL_OBJECT,
        submission_module.PredicateKind.MATERIAL_DISPLAY,
    ),
    "thirteenth_exact_gn_v_17": submission_module.PortalSemanticRoles(
        submission_module.SurfaceContext.GENERIC_UI,
        submission_module.Actuality.CURRENT_ASSERTION,
        submission_module.ObjectKind.NONE,
        submission_module.PredicateKind.MATERIAL_DISPLAY,
    ),
    "thirteenth_exact_pr_v_07": submission_module.PortalSemanticRoles(
        submission_module.SurfaceContext.GOVERNED_PORTAL,
        submission_module.Actuality.NON_CURRENT_OR_NON_ASSERTIVE,
        submission_module.ObjectKind.STRONG_MATERIAL_OBJECT,
        submission_module.PredicateKind.MATERIAL_DISPLAY,
    ),
    "thirteenth_material_returned_application_exists": submission_module.PortalSemanticRoles(
        submission_module.SurfaceContext.GOVERNED_PORTAL,
        submission_module.Actuality.CURRENT_ASSERTION,
        submission_module.ObjectKind.STRONG_MATERIAL_OBJECT,
        submission_module.PredicateKind.STATE,
    ),
}


def assert_portal_semantic_roles(test_case, text: str, expected) -> None:
    graph = submission_module.build_structured_span_graph(
        submission_module.markdown_visible_text(text)
    )
    spans = [
        assertion
        for structural_span in graph.spans
        for assertion in submission_module.extract_assertion_spans(
            structural_span, "portal-state"
        )
    ]
    observed = [submission_module.classify_portal_semantics(span) for span in spans]
    test_case.assertIn(expected, observed)


def _make_portal_semantic_rejection_test(
    relative: str, text: str, expected_roles=None
):
    def test(self):
        self.reject_portal_assertion(relative, text)
        if expected_roles is not None:
            assert_portal_semantic_roles(self, text, expected_roles)

    return test


def _make_portal_semantic_safe_test(relative: str, text: str, expected_roles=None):
    def test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            append_text(root, relative, "\n" + text + "\n")
            self.assert_accepted(run_validator(root))
        if expected_roles is not None:
            assert_portal_semantic_roles(self, text, expected_roles)

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
    *F06_CONTEXT_AUDIT_FALSE_PASS_CASES,
    *F06_CONTEXT_REQUIRED_INVALID_CASES,
    *F06_BOUNDED_CONTEXT_INVALID_CASES,
    *F06_PARENT_CHILD_INVALID_CASES,
    *F06_MARKDOWN_CONTEXT_INVALID_CASES,
    *F06_CONTINUATION_CONTEXT_FALSE_PASS_CASES,
    *F06_CONTINUATION_VARIANT_INVALID_CASES,
    *F06_CONTEXT_SOURCE_DISTANCE_INVALID_CASES,
    *F06_RESIDUAL_CONTINUATION_INVALID_CASES,
    *F06_RESIDUAL_NECESSARY_INVALID_CASES,
    *F06_RESIDUAL_ANAPHORIC_INVALID_CASES,
    *F06_RESIDUAL_VERIFICATION_COMBINED_INVALID_CASES,
    *F06_TWELFTH_MATERIAL_PREDICATE_INVALID_CASES,
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
    *F06_CONTEXT_AUDIT_FALSE_REJECT_CASES,
    *F06_BOUNDED_CONTEXT_SAFE_CASES,
    *F06_PARENT_CHILD_SAFE_CASES,
    *F06_MARKDOWN_CONTEXT_SAFE_CASES,
    *F06_CONTINUATION_CONTEXT_SAFE_CASES,
    *F06_RESIDUAL_SAFE_CASES,
    *F06_TWELFTH_GENERIC_SURFACE_SAFE_CASES,
    *F06_TWELFTH_SAFE_SCOPE_CASES,
):
    setattr(
        PortalStateWordingTests,
        f"test_portal_semantic_{_name}_passes",
        _make_portal_semantic_safe_test(_relative, _text),
    )


for _name, _relative, _text in (
    *F06_THIRTEENTH_EXACT_FALSE_PASS_CASES,
    *F06_THIRTEENTH_PORTAL_MATERIAL_STATE_INVALID_CASES,
    *F06_THIRTEENTH_MIXED_SCOPE_INVALID_CASES,
    *F06_THIRTEENTH_CONTEXT_INVALID_CASES,
):
    setattr(
        PortalStateWordingTests,
        f"test_portal_semantic_{_name}_fails",
        _make_portal_semantic_rejection_test(
            _relative, _text, F06_THIRTEENTH_ROLE_EXPECTATIONS.get(_name)
        ),
    )

for _name, _relative, _text in (
    *F06_THIRTEENTH_EXACT_GENERIC_FALSE_REJECT_CASES,
    *F06_THIRTEENTH_EXACT_HYPOTHETICAL_FALSE_REJECT_CASES,
    *F06_THIRTEENTH_GENERIC_PRESENTATION_SAFE_CASES,
    *F06_THIRTEENTH_HYPOTHETICAL_SAFE_CASES,
    *F06_THIRTEENTH_SCOPE_CONTROL_SAFE_CASES,
    *F06_THIRTEENTH_CONTEXT_SAFE_CASES,
):
    setattr(
        PortalStateWordingTests,
        f"test_portal_semantic_{_name}_passes",
        _make_portal_semantic_safe_test(
            _relative, _text, F06_THIRTEENTH_ROLE_EXPECTATIONS.get(_name)
        ),
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
    an English support/contact channel at any placement in the file.
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



    def test_support_official_customer_support_at_eof_fails(self):
        self.reject_support(
            lambda root: append_text(
                root,
                submission_module.SUPPORT_RELATIVE,
                "\nFor official customer support, use https://example.com/help.\n",
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




    def test_support_two_line_documentation_reference_passes(self):
        self.accept_support(
            "Official support remains GitHub Issues.\n"
            "Documentation reference: https://example.com/help"
        )


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


class CanonicalEnglishRuntimeRegressionTests(RepoInvariantTestCase):
    def test_validator_has_no_localized_machine_semantic_tables(self):
        source = VALIDATE_SUBMISSION_SCRIPT.read_text(encoding="utf-8")
        self.assertIsInstance(submission_module.PORTAL_CONTEXT_PATTERNS, tuple)
        self.assertIsInstance(submission_module.PORTAL_STATE_OBJECT_PATTERNS, tuple)
        self.assertIsInstance(submission_module.PORTAL_STATE_PREDICATE_PATTERNS, tuple)
        self.assertNotRegex(source, r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]")
        self.assertIn("not a general natural-language", source)

    def test_each_canonical_english_status_marker_is_required(self):
        for relative, markers in submission_module.CANONICAL_STATUS_MARKERS.items():
            for marker in markers:
                with self.subTest(relative=relative, marker=marker):
                    with tempfile.TemporaryDirectory() as temp:
                        root = build_repo(temp)
                        remove_text(root, relative, marker)
                        self.assert_rejected(
                            run_validator(root), "missing canonical English marker"
                        )

    def test_f05_unexpected_name_error_has_no_pass_or_runtime_details(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_repo(temp)
            script = root / "scripts/validate-plugin-submission.py"
            source = script.read_text(encoding="utf-8")
            self.assertIn("return main()", source)
            script.write_text(
                source.replace("return main()", "return missing_entrypoint()", 1),
                encoding="utf-8",
            )

            result = run_validator(root)
            combined = result.stdout + result.stderr
            self.assertEqual(1, result.returncode, combined)
            self.assertIn(
                "ERROR: Unexpected Plugin submission validator failure.",
                result.stderr,
            )
            self.assertNotIn("Plugin submission validation: PASS", combined)
            self.assertNotIn("NameError", combined)
            self.assertNotIn("Traceback", combined)


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
