from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
PLUGIN_VALIDATOR = "scripts/validate-codex-plugin.py"
SUBMISSION_VALIDATOR = "scripts/validate-plugin-submission.py"
SKILL_VALIDATOR = "scripts/validate-skill.py"
MANIFEST = "plugins/agentic-change-audit/.codex-plugin/plugin.json"
MARKETPLACE = ".agents/plugins/marketplace.json"
PLUGIN_READMES = (
    "plugins/agentic-change-audit/README.md",
)
PASS_MARKERS = {
    "plugin": "Codex Plugin validation: PASS",
    "submission": "Plugin submission validation: PASS",
    "skill": "Skill validation: PASS",
}
DELETE = object()

Mutation = Callable[[Path], None]
Assertion = Callable[[Path], None]


def subprocess_env() -> dict[str, str]:
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def fresh_repo(temp: str) -> Path:
    destination = Path(temp) / "repo"
    shutil.copytree(
        ROOT,
        destination,
        ignore=shutil.ignore_patterns(".git", "__pycache__"),
        symlinks=True,
    )
    return destination


def run_validator(root: Path, validator: str) -> subprocess.CompletedProcess[str]:
    if validator == "skill":
        command = [
            PYTHON,
            str(root / SKILL_VALIDATOR),
            str(root),
            "--expected-name",
            "agentic-change-audit",
        ]
    else:
        script = PLUGIN_VALIDATOR if validator == "plugin" else SUBMISSION_VALIDATOR
        command = [PYTHON, str(root / script), "--root", str(root)]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


def json_mutation(relative: str, path: tuple[str | int, ...], value) -> Mutation:
    def mutate(root: Path) -> None:
        target = root / relative
        document = json.loads(target.read_text(encoding="utf-8"))
        cursor = document
        for part in path[:-1]:
            cursor = cursor[part]
        final = path[-1]
        if value is DELETE:
            del cursor[final]
        else:
            cursor[final] = value
        target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    return mutate


def append_text(relative: str, text: str) -> Mutation:
    def mutate(root: Path) -> None:
        target = root / relative
        target.write_text(
            target.read_text(encoding="utf-8") + f"\n{text}\n",
            encoding="utf-8",
        )

    return mutate


def append_exact_text(relative: str, text: str) -> Mutation:
    def mutate(root: Path) -> None:
        target = root / relative
        target.write_text(
            target.read_text(encoding="utf-8") + text,
            encoding="utf-8",
        )

    return mutate


def replace_text(relative: str, text: str) -> Mutation:
    """Replace a Markdown document with an isolated canonical fixture."""

    def mutate(root: Path) -> None:
        body = text.rstrip("\n")
        fixture = (
            "Agentic Change Audit marketplace\n\n"
            "0.1.0-dev.3\n\n"
            "Development preview\n\n"
            "Phase C desktop verification is complete and accepted. Earlier desktop evidence is "
            "historical, superseded, and non-transferable.\n\n"
            "English is the sole canonical language for machine semantics and exact tokens.\n\n"
            f"{body}\n"
        )
        (root / relative).write_text(fixture, encoding="utf-8")

    return mutate


def replace_bytes(relative: str, before: bytes, after: bytes) -> Mutation:
    def mutate(root: Path) -> None:
        target = root / relative
        data = target.read_bytes()
        if before not in data:
            raise AssertionError(f"{relative} does not contain {before!r}")
        target.write_bytes(data.replace(before, after, 1))

    return mutate


def append_bytes(relative: str, data: bytes) -> Mutation:
    def mutate(root: Path) -> None:
        target = root / relative
        target.write_bytes(target.read_bytes() + data)

    return mutate


def json_assertion(relative: str, path: tuple[str | int, ...], expected) -> Assertion:
    def assert_value(root: Path) -> None:
        value = json.loads((root / relative).read_text(encoding="utf-8"))
        for part in path:
            value = value[part]
        if value != expected:
            raise AssertionError(f"{relative}:{path!r} = {value!r}, expected {expected!r}")

    return assert_value


class IdentityPolicyTestCase(unittest.TestCase):
    def assert_rejected(self, validator: str, mutation: Mutation) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = fresh_repo(temp)
            mutation(root)
            result = run_validator(root, validator)
            combined = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode, combined)
            self.assertNotIn(PASS_MARKERS[validator], combined)

    def assert_accepted(self, validator: str, assertion: Assertion) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = fresh_repo(temp)
            assertion(root)
            result = run_validator(root, validator)
            combined = result.stdout + result.stderr
            self.assertEqual(0, result.returncode, combined)
            self.assertIn(PASS_MARKERS[validator], result.stdout)
            self.assertNotIn("Plugin README Phase C identity contradiction", combined)

    def assert_rejected_with_family(
        self,
        validator: str,
        mutation: Mutation,
        failure_family: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = fresh_repo(temp)
            mutation(root)
            result = run_validator(root, validator)
            combined = result.stdout + result.stderr
            self.assertNotEqual(0, result.returncode, combined)
            self.assertIn(failure_family, combined)
            self.assertNotIn(PASS_MARKERS[validator], combined)


@dataclass(frozen=True)
class InvalidRegressionCase:
    case_id: str
    description: str
    expected: str
    validator: str
    mutation: Mutation
    failure_family: str


def install_negative_cases(
    case_class: type[IdentityPolicyTestCase],
    cases: tuple[tuple[str, str, Mutation], ...],
) -> None:
    for name, validator, mutation in cases:
        def test(self, validator=validator, mutation=mutation):
            self.assert_rejected(validator, mutation)

        setattr(case_class, f"test_{name}", test)


def install_positive_cases(
    case_class: type[IdentityPolicyTestCase],
    cases: tuple[tuple[str, str, Assertion], ...],
) -> None:
    for name, validator, assertion in cases:
        def test(self, validator=validator, assertion=assertion):
            self.assert_accepted(validator, assertion)

        setattr(case_class, f"test_{name}", test)


def install_invalid_regression_cases(
    case_class: type[IdentityPolicyTestCase],
    cases: tuple[InvalidRegressionCase, ...],
) -> None:
    for case in cases:
        def test(self, case=case):
            self.assertEqual("invalid", case.expected)
            self.assert_rejected_with_family(
                case.validator,
                case.mutation,
                case.failure_family,
            )

        test.__doc__ = case.description
        setattr(case_class, f"test_{case.case_id.lower()}", test)


class MarketplaceExactIdentityTests(IdentityPolicyTestCase):
    def test_marketplace_01_exact_neutral_identity_is_accepted(self):
        self.assert_accepted(
            "plugin",
            json_assertion(
                MARKETPLACE,
                ("interface", "displayName"),
                "Agentic Change Audit",
            ),
        )


install_negative_cases(
    MarketplaceExactIdentityTests,
    (
        (
            "marketplace_02_old_internal_name_is_rejected",
            "plugin",
            json_mutation(MARKETPLACE, ("name",), "landco-llc-open-source"),
        ),
        (
            "marketplace_03_company_slug_name_is_rejected",
            "plugin",
            json_mutation(MARKETPLACE, ("name",), "landco-llc"),
        ),
        (
            "marketplace_04_noncanonical_neutral_name_is_rejected",
            "plugin",
            json_mutation(MARKETPLACE, ("name",), "agentic-change-audit-marketplace"),
        ),
        (
            "marketplace_05_old_display_name_is_rejected",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("interface", "displayName"),
                "L&Co.LLC Open Source",
            ),
        ),
        (
            "marketplace_06_short_company_display_name_is_rejected",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("interface", "displayName"),
                "L&Co. Open Source",
            ),
        ),
        (
            "marketplace_07_company_prefixed_product_is_rejected",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("interface", "displayName"),
                "L&Co.LLC Agentic Change Audit",
            ),
        ),
        (
            "marketplace_08_missing_name_is_rejected",
            "plugin",
            json_mutation(MARKETPLACE, ("name",), DELETE),
        ),
        (
            "marketplace_09_missing_interface_is_rejected",
            "plugin",
            json_mutation(MARKETPLACE, ("interface",), DELETE),
        ),
        (
            "marketplace_10_company_prefixed_entry_name_is_rejected",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "name"),
                "landco-llc-agentic-change-audit",
            ),
        ),
    ),
)


class ManifestProductLegalSeparationTests(IdentityPolicyTestCase):
    def test_manifest_01_exact_product_legal_separation_is_accepted(self):
        self.assert_accepted(
            "plugin",
            json_assertion(MANIFEST, ("author", "name"), "L&Co.LLC"),
        )


install_negative_cases(
    ManifestProductLegalSeparationTests,
    (
        (
            "manifest_02_stale_dev2_version_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("version",), "0.1.0-dev.2"),
        ),
        (
            "manifest_03_arbitrary_future_version_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("version",), "0.1.0-dev.4"),
        ),
        (
            "manifest_04_malformed_version_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("version",), "not-semver"),
        ),
        (
            "manifest_05_company_prefixed_name_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("name",), "landco-llc-agentic-change-audit"),
        ),
        (
            "manifest_06_company_prefixed_display_name_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "displayName"),
                "L&Co.LLC Agentic Change Audit",
            ),
        ),
        (
            "manifest_07_github_slug_author_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("author", "name"), "landco-llc"),
        ),
        (
            "manifest_08_github_slug_developer_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("interface", "developerName"), "landco-llc"),
        ),
        (
            "manifest_09_branded_author_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("author", "name"), "L&Co.LLC Open Source"),
        ),
        (
            "manifest_10_branded_developer_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "developerName"),
                "L&Co.LLC Open Source",
            ),
        ),
    ),
)


class ForbiddenHumanFacingIdentityTests(IdentityPolicyTestCase):
    pass


install_negative_cases(
    ForbiddenHumanFacingIdentityTests,
    (
        (
            "human_01_legal_name_in_description_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("description",), "L&Co.LLC audits software changes."),
        ),
        (
            "human_02_slug_in_description_is_rejected",
            "plugin",
            json_mutation(MANIFEST, ("description",), "landco-llc audits software changes."),
        ),
        (
            "human_03_short_company_name_in_short_description_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "shortDescription"),
                "L&Co. audits software changes.",
            ),
        ),
        (
            "human_04_old_marketplace_in_short_description_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "shortDescription"),
                "Use L&Co.LLC Open Source to audit changes.",
            ),
        ),
        (
            "human_05_company_name_in_long_description_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "longDescription"),
                "L&Co.LLC Open Source reviews fixed software changes.",
            ),
        ),
        (
            "human_06_company_name_in_default_prompt_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "defaultPrompt", 0),
                "Use L&Co. Open Source to audit this change.",
            ),
        ),
        (
            "human_07_slug_in_default_prompt_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "defaultPrompt", 1),
                "Ask landco-llc to audit this release candidate.",
            ),
        ),
        (
            "human_08_technical_url_in_default_prompt_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("interface", "defaultPrompt", 2),
                "Use https://github.com/landco-llc/agentic-change-audit as the product name.",
            ),
        ),
        (
            "human_09_slug_in_discovery_keyword_is_rejected",
            "plugin",
            json_mutation(
                MANIFEST,
                ("keywords",),
                ["software-audit", "landco-llc"],
            ),
        ),
        (
            "human_10_short_company_marketplace_display_is_rejected",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("interface", "displayName"),
                "L&Co. Agentic Change Audit",
            ),
        ),
    ),
)


def notice_legal_assertion(root: Path) -> None:
    notice = (root / "NOTICE").read_text(encoding="utf-8")
    legal = (root / "docs/legal-attribution.md").read_text(encoding="utf-8")
    if "L&Co.LLC" not in notice or "https://github.com/landco-llc/" not in notice:
        raise AssertionError("NOTICE must retain legal identity and technical source URL")
    if "L&Co.LLC" not in legal or "`landco-llc`" not in legal:
        raise AssertionError("legal attribution must retain legal and technical identities")


def mirror_assertion(root: Path) -> None:
    canonical = (root / "SKILL.md").read_bytes()
    mirrored = (
        root / "plugins/agentic-change-audit/skills/agentic-change-audit/SKILL.md"
    ).read_bytes()
    if canonical != mirrored:
        raise AssertionError("canonical and bundled Skill must be byte-identical")


class AllowedLegalAndTechnicalIdentityTests(IdentityPolicyTestCase):
    pass


install_positive_cases(
    AllowedLegalAndTechnicalIdentityTests,
    (
        (
            "allowed_01_exact_legal_author_is_accepted",
            "plugin",
            json_assertion(MANIFEST, ("author", "name"), "L&Co.LLC"),
        ),
        (
            "allowed_02_exact_legal_developer_is_accepted",
            "plugin",
            json_assertion(MANIFEST, ("interface", "developerName"), "L&Co.LLC"),
        ),
        (
            "allowed_03_technical_author_url_is_accepted",
            "plugin",
            json_assertion(MANIFEST, ("author", "url"), "https://github.com/landco-llc"),
        ),
        (
            "allowed_04_technical_homepage_is_accepted",
            "plugin",
            json_assertion(
                MANIFEST,
                ("homepage",),
                "https://github.com/landco-llc/agentic-change-audit",
            ),
        ),
        (
            "allowed_05_technical_repository_url_is_accepted",
            "plugin",
            json_assertion(
                MANIFEST,
                ("repository",),
                "https://github.com/landco-llc/agentic-change-audit",
            ),
        ),
        (
            "allowed_06_technical_website_url_is_accepted",
            "plugin",
            json_assertion(
                MANIFEST,
                ("interface", "websiteURL"),
                "https://github.com/landco-llc/agentic-change-audit",
            ),
        ),
        (
            "allowed_07_notice_and_legal_identity_are_accepted",
            "skill",
            notice_legal_assertion,
        ),
        (
            "allowed_08_canonical_skill_mirror_is_accepted",
            "plugin",
            mirror_assertion,
        ),
        (
            "allowed_09_neutral_submission_app_name_is_accepted",
            "submission",
            json_assertion(
                "submission/codex-plugin/listing.json",
                ("pluginName",),
                "Agentic Change Audit",
            ),
        ),
    ),
)


class StalePluginReadmeIdentityTests(IdentityPolicyTestCase):
    pass


README_CASES: list[tuple[str, str, Mutation]] = []
for index, relative in enumerate(PLUGIN_READMES, start=1):
    README_CASES.extend(
        (
            (
                f"readme_{index:02d}_old_internal_marketplace_name_is_rejected",
                "plugin",
                append_text(relative, "landco-llc-open-source"),
            ),
            (
                f"readme_{index + 3:02d}_old_marketplace_display_name_is_rejected",
                "plugin",
                append_text(relative, "L&Co.LLC Open Source"),
            ),
            (
                f"readme_{index + 6:02d}_stale_dev2_version_is_rejected",
                "plugin",
                append_text(relative, "0.1.0-dev.2"),
            ),
        )
    )

install_negative_cases(StalePluginReadmeIdentityTests, tuple(README_CASES))


class Issue11AttributionAndMirrorControls(IdentityPolicyTestCase):
    pass


install_negative_cases(
    Issue11AttributionAndMirrorControls,
    (
        (
            "issue11_01_notice_legal_identity_change_is_rejected",
            "skill",
            replace_bytes("NOTICE", b"L&Co.LLC", b"landco-llc"),
        ),
        (
            "issue11_02_license_byte_change_is_rejected",
            "skill",
            append_bytes("LICENSE", b"x"),
        ),
        (
            "issue11_03_legal_attribution_change_is_rejected",
            "skill",
            replace_bytes(
                "docs/legal-attribution.md",
                b"the legal identity is `L&Co.LLC`",
                b"the legal identity is `landco-llc`",
            ),
        ),
        (
            "issue11_04_bundled_skill_mirror_change_is_rejected",
            "plugin",
            append_bytes(
                "plugins/agentic-change-audit/skills/agentic-change-audit/SKILL.md",
                b"\nchanged\n",
            ),
        ),
    ),
)


class ExactPriorFalsePassRegressionTests(IdentityPolicyTestCase):
    """The exact 19 false-PASS probes from the fixed audit ledger."""


install_invalid_regression_cases(
    ExactPriorFalsePassRegressionTests,
    (
        InvalidRegressionCase(
            "prior_a26",
            "fresh A26: unexpected marketplace top-level key",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("freshUnexpectedA26",),
                "company catalog metadata",
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_a27",
            "fresh A27: unexpected marketplace interface key",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("interface", "freshUnexpectedA27"),
                "human display metadata",
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_a28",
            "fresh A28: unexpected marketplace entry key",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "freshUnexpectedA28"),
                "entry metadata",
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_a29",
            "fresh A29: unexpected marketplace source key",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "source", "freshUnexpectedA29"),
                "source metadata",
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_a30",
            "fresh A30: unexpected marketplace policy key",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "policy", "freshUnexpectedA30"),
                "policy metadata",
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_a31",
            "fresh A31: duplicate top-level name with malicious first value",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'  "name": "agentic-change-audit",',
                b'  "name": "landco-llc-fresh-duplicate-a31",\n'
                b'  "name": "agentic-change-audit",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_a32",
            "fresh A32: duplicate displayName with malicious first value",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'    "displayName": "Agentic Change Audit"',
                b'    "displayName": "L&Co.LLC Fresh Duplicate A32",\n'
                b'    "displayName": "Agentic Change Audit"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_b29",
            "fresh B29: duplicate version with malicious first value",
            "invalid",
            "plugin",
            replace_bytes(
                MANIFEST,
                b'  "version": "0.1.0-dev.3",',
                b'  "version": "0.1.0-dev.99-fresh-b29",\n'
                b'  "version": "0.1.0-dev.3",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_b30",
            "fresh B30: duplicate author name with malicious first value",
            "invalid",
            "plugin",
            replace_bytes(
                MANIFEST,
                b'    "name": "L&Co.LLC",',
                b'    "name": "landco-llc-fresh-b30",\n'
                b'    "name": "L&Co.LLC",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_b31",
            "fresh B31: duplicate displayName with malicious first value",
            "invalid",
            "plugin",
            replace_bytes(
                MANIFEST,
                b'    "displayName": "Agentic Change Audit",',
                b'    "displayName": "L&Co.LLC Fresh B31",\n'
                b'    "displayName": "Agentic Change Audit",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_d13",
            "fresh D13: append prohibited status claim",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[0],
                "Phase C desktop registration, discovery, installation, "
                "invocation, and working-tree verification are complete now. "
                "Fresh D13.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "prior_d18",
            "fresh D18: append conflicting future Plugin version",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "Fresh D18 identifies the current Plugin version as "
                "0.1.0-dev.30.",
            ),
            "Plugin README development-version mismatch",
        ),
        InvalidRegressionCase(
            "prior_e01",
            "fresh E01: unexpected nested human display array",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("interface", "freshNestedE01"),
                [{"label": "L&Co.LLC Fresh Product E01"}],
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_e02",
            "fresh E02: unexpected nested repository-like product field",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "freshNestedE02"),
                {"display": "landco-llc/fresh-e02"},
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "prior_e09",
            "fresh E09: duplicate source type malicious then canonical",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'        "source": "local",',
                b'        "source": "remote-fresh-e09",\n'
                b'        "source": "local",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_e10",
            "fresh E10: duplicate policy authentication malicious then canonical",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'        "authentication": "ON_INSTALL"',
                b'        "authentication": "NEVER-FRESH-E10",\n'
                b'        "authentication": "ON_INSTALL"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "prior_e11",
            "fresh E11: unexpected deeply nested policy product branding",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "policy", "freshNestedE11"),
                {"copy": ["L&Co.LLC Fresh Catalog E11"]},
            ),
            "keys mismatch",
        ),
    ),
)


class AdditionalMarketplaceShapeRegressionTests(IdentityPolicyTestCase):
    """Sixteen additional exact-key-set and malformed-shape subprocess cases."""


install_invalid_regression_cases(
    AdditionalMarketplaceShapeRegressionTests,
    (
        InvalidRegressionCase(
            "shape_01",
            "additional marketplace top-level object is rejected",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("metadata",), {"owner": "neutral"}),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_02",
            "additional marketplace top-level array is rejected",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("aliases",), ["agentic-change-audit"]),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_03",
            "missing plugins key is rejected by the exact top-level shape",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins",), DELETE),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_04",
            "empty interface object is rejected",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("interface",), {}),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_05",
            "array interface is rejected without an exception",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("interface",), ["Agentic Change Audit"]),
            "interface.displayName",
        ),
        InvalidRegressionCase(
            "shape_06",
            "missing plugin-entry category is rejected",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins", 0, "category"), DELETE),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_07",
            "additional plugin-entry object is rejected",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "documentation"),
                {"status": "draft"},
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_08",
            "array plugin entry is rejected without an exception",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins", 0), ["agentic-change-audit"]),
            "plugin entry must be an object",
        ),
        InvalidRegressionCase(
            "shape_09",
            "missing source type key is rejected",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins", 0, "source", "source"), DELETE),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_10",
            "missing source path key is rejected",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins", 0, "source", "path"), DELETE),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_11",
            "additional source object is rejected",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "source", "mirror"),
                {"path": "./plugins/agentic-change-audit"},
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_12",
            "array source is rejected without an exception",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins", 0, "source"), ["local"]),
            "entry 'source' must be an object",
        ),
        InvalidRegressionCase(
            "shape_13",
            "missing installation policy is rejected",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "policy", "installation"),
                DELETE,
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_14",
            "missing authentication policy is rejected",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "policy", "authentication"),
                DELETE,
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_15",
            "additional nested policy array is rejected",
            "invalid",
            "plugin",
            json_mutation(
                MARKETPLACE,
                ("plugins", 0, "policy", "approvalHistory"),
                ["PENDING"],
            ),
            "keys mismatch",
        ),
        InvalidRegressionCase(
            "shape_16",
            "array policy is rejected without an exception",
            "invalid",
            "plugin",
            json_mutation(MARKETPLACE, ("plugins", 0, "policy"), ["AVAILABLE"]),
            "entry 'policy' must be an object",
        ),
    ),
)


class AdditionalDuplicateJSONKeyRegressionTests(IdentityPolicyTestCase):
    """Sixteen recursive duplicate-key cases across all consumed JSON files."""


install_invalid_regression_cases(
    AdditionalDuplicateJSONKeyRegressionTests,
    (
        InvalidRegressionCase(
            "duplicate_01",
            "duplicate marketplace plugins key is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'  "plugins": [',
                b'  "plugins": [],\n  "plugins": [',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_02",
            "same-value marketplace displayName duplicate is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'    "displayName": "Agentic Change Audit"',
                b'    "displayName": "Agentic Change Audit",\n'
                b'    "displayName": "Agentic Change Audit"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_03",
            "duplicate marketplace entry category is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'      "category": "Productivity"',
                b'      "category": "Security",\n'
                b'      "category": "Productivity"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_04",
            "duplicate marketplace source path is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'        "path": "./plugins/agentic-change-audit"',
                b'        "path": "../outside",\n'
                b'        "path": "./plugins/agentic-change-audit"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_05",
            "duplicate marketplace installation policy is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MARKETPLACE,
                b'        "installation": "AVAILABLE",',
                b'        "installation": "HIDDEN",\n'
                b'        "installation": "AVAILABLE",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_06",
            "duplicate manifest top-level name is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MANIFEST,
                b'  "name": "agentic-change-audit",',
                b'  "name": "other",\n  "name": "agentic-change-audit",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_07",
            "duplicate manifest author URL is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MANIFEST,
                b'    "url": "https://github.com/landco-llc"',
                b'    "url": "https://example.invalid",\n'
                b'    "url": "https://github.com/landco-llc"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_08",
            "duplicate manifest interface category is rejected",
            "invalid",
            "plugin",
            replace_bytes(
                MANIFEST,
                b'    "category": "Productivity",',
                b'    "category": "Security",\n'
                b'    "category": "Productivity",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_09",
            "duplicate listing pluginName is rejected",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/listing.json",
                b'  "pluginName": "Agentic Change Audit",',
                b'  "pluginName": "Other",\n'
                b'  "pluginName": "Agentic Change Audit",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_10",
            "duplicate listing verificationStatus is rejected recursively",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/listing.json",
                b'    "verificationStatus": "PENDING HUMAN CHECK"',
                b'    "verificationStatus": "VERIFIED",\n'
                b'    "verificationStatus": "PENDING HUMAN CHECK"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_11",
            "duplicate listing skill path is rejected recursively",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/listing.json",
                b'      "path": "plugins/agentic-change-audit/skills/'
                b'agentic-change-audit"',
                b'      "path": "../outside",\n'
                b'      "path": "plugins/agentic-change-audit/skills/'
                b'agentic-change-audit"',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_12",
            "duplicate starterPrompts top-level key is rejected",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/starter-prompts.json",
                b'  "starterPrompts": [',
                b'  "starterPrompts": [],\n  "starterPrompts": [',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_13",
            "duplicate starter prompt id is rejected recursively",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/starter-prompts.json",
                b'      "id": "starter-full-pull-request-audit",',
                b'      "id": "malicious",\n'
                b'      "id": "starter-full-pull-request-audit",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_14",
            "duplicate testCases top-level key is rejected",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/test-cases.json",
                b'  "testCases": [',
                b'  "testCases": [],\n  "testCases": [',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_15",
            "duplicate test case id is rejected recursively",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/test-cases.json",
                b'      "id": "positive-explicit-invocation-docs-only",',
                b'      "id": "malicious",\n'
                b'      "id": "positive-explicit-invocation-docs-only",',
            ),
            "Duplicate JSON key",
        ),
        InvalidRegressionCase(
            "duplicate_16",
            "duplicate availability status is rejected",
            "invalid",
            "submission",
            replace_bytes(
                "submission/codex-plugin/availability.json",
                b'  "status": "PENDING HUMAN DECISION",',
                b'  "status": "AVAILABLE",\n'
                b'  "status": "PENDING HUMAN DECISION",',
            ),
            "Duplicate JSON key",
        ),
    ),
)


class AdditionalReadmeBoundaryRegressionTests(IdentityPolicyTestCase):
    """Canonical English contradiction and competing-version cases."""


install_invalid_regression_cases(
    AdditionalReadmeBoundaryRegressionTests,
    (
        InvalidRegressionCase(
            "readme_hardening_01",
            "English neutral-identity Phase C gate passed claim is rejected",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "The neutral-identity Phase C desktop gate passed.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_04",
            "English Phase C desktop verification completed claim is rejected",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[0],
                "Phase C desktop verification is complete and successful.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_07",
            "English current marketplace registration verified claim is rejected",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "Marketplace registration for 0.1.0-dev.3 is verified.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_10",
            "English current explicit invocation success claim is rejected",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[0],
                "Explicit invocation of 0.1.0-dev.3 was successful.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_13",
            "English competing development version is rejected",
            "invalid",
            "plugin",
            append_text(PLUGIN_READMES[0], "Plugin development version: 0.1.0-dev.4."),
            "Plugin README development-version mismatch",
        ),
        InvalidRegressionCase(
            "readme_hardening_16",
            "retaining the invalidation text cannot hide a new contradiction",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[0],
                "The renamed marketplace Phase C desktop gate is approved now.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_17",
            "English negation cannot license a later verified claim",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "The neutral Phase C desktop gate is not complete, but it is verified.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
    ),
)


class RemediationValidControlTests(IdentityPolicyTestCase):
    """Fresh real-subprocess controls for canonical, historical, and future text."""


install_positive_cases(
    RemediationValidControlTests,
    (
        (
            "remediation_valid_01_canonical_plugin_json_and_readmes_pass",
            "plugin",
            json_assertion(MANIFEST, ("version",), "0.1.0-dev.3"),
        ),
        (
            "remediation_valid_02_canonical_submission_json_passes",
            "submission",
            json_assertion(
                "submission/codex-plugin/availability.json",
                ("status",),
                "PENDING HUMAN DECISION",
            ),
        ),
        (
            "remediation_valid_03_english_historical_invalidation_passes",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "Earlier desktop evidence existed for the previous identity and is "
                "superseded and invalid for the neutral identity.",
            ),
        ),
        (
            "remediation_valid_06_english_future_phase_c_instruction_passes",
            "submission",
            append_text(
                PLUGIN_READMES[0],
                "Fresh Phase C desktop evidence remains required.",
            ),
        ),
        (
            "remediation_valid_09_english_install_instruction_passes",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "When local installation is complete, restart the ChatGPT desktop app.",
            ),
        ),
    ),
)


class ExactSecondRemediationResidualTests(IdentityPolicyTestCase):
    """Exact RF01/RF02 mutations preserved from fresh-probes.json."""


install_invalid_regression_cases(
    ExactSecondRemediationResidualTests,
    (
        InvalidRegressionCase(
            "exact_rdm_026",
            "RF01 RDM-026 exact English soft-line-break mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-RDM-026: The neutral marketplace identity Phase C "
                "desktop gate has been\nverified successfully.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_027",
            "RF01 RDM-027 exact current registration mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-RDM-027: Marketplace registration for the current "
                "identity is\ncomplete now.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_031",
            "RF01 RDM-031 exact Markdown hard-break mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-RDM-031: The renamed marketplace Phase C desktop gate "
                "has been  \nvalidated.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_032",
            "RF01 RDM-032 exact emphasis and line-break mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-RDM-032: The **neutral marketplace identity Phase C "
                "desktop gate** is\n**complete**.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_033",
            "RF01 RDM-033 exact marketplace discovery mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-RDM-033: Marketplace discovery for 0.1.0-dev.3 is"
                "\nverified.",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_039",
            "RF01 RDM-039 exact English denial replacement",
            "invalid",
            "plugin",
            replace_bytes(
                PLUGIN_READMES[0],
                "Phase C desktop verification is complete and accepted.".encode(),
                (
                    "Phase C desktop evidence is complete for the "
                    "Agentic Change Audit marketplace; ACA-FRESH-RDM-039"
                ).encode(),
            ),
            "Plugin README Phase C identity contradiction",
        ),
    ),
)

install_positive_cases(
    ExactSecondRemediationResidualTests,
    (
        (
            "exact_val_035",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-VAL-035: A unit-test fixture may say passed without "
                "asserting any desktop gate.",
            ),
        ),
    ),
)


class SecondRemediationAdditionalInvalidTests(IdentityPolicyTestCase):
    """Additional canonical English real-subprocess invalid controls."""


SECOND_REMEDIATION_ADDITIONAL_INVALID_CASES = (
    # English: 12
    ("second_invalid_en_01", PLUGIN_READMES[0], "The neutral marketplace identity Phase C Desktop gate has been\nverified."),
    ("second_invalid_en_02", PLUGIN_READMES[0], "The current marketplace\n- registration\n- has passed."),
    ("second_invalid_en_03", PLUGIN_READMES[0], "> Phase C Desktop gate\n> is approved."),
    ("second_invalid_en_04", PLUGIN_READMES[0], "The **neutral marketplace identity** Phase C [Desktop gate](https://example.invalid/gate)\nis complete."),
    ("second_invalid_en_05", PLUGIN_READMES[0], "Phase C is not pending; it passed."),
    ("second_invalid_en_06", PLUGIN_READMES[0], "Phase C is not unverified; it is verified."),
    ("second_invalid_en_07", PLUGIN_READMES[0], "Phase C is no longer pending and has completed."),
    ("second_invalid_en_08", PLUGIN_READMES[0], "The current neutral identity is documented. Desktop registration has succeeded."),
    ("second_invalid_en_09", PLUGIN_READMES[0], "Earlier Desktop evidence passed but is superseded and invalid. The current Desktop gate passed."),
    ("second_invalid_en_10_adversarial", PLUGIN_READMES[0], "This fixture must reject the claim \"Desktop gate passed.\" However, the current Desktop gate passed."),
    ("second_invalid_en_11", PLUGIN_READMES[0], "Current version 0.1.0-dev.3 uses marketplace discovery and working-tree non-mutation; both are validated."),
    ("second_invalid_en_12", PLUGIN_READMES[0], "The current result says \"Desktop gate passed.\""),
    ("second_invalid_en_13_adversarial", PLUGIN_READMES[0], "This document does not assert that a release passed, and the current Desktop gate passed."),
    ("second_invalid_en_14_adversarial", PLUGIN_READMES[0], "The current Desktop gate passed, and this document does not assert a release claim."),
    # Mixed language and Markdown boundaries: 12
)

install_invalid_regression_cases(
    SecondRemediationAdditionalInvalidTests,
    tuple(
        InvalidRegressionCase(
            case_id,
            "second-remediation additional invalid real-subprocess case",
            "invalid",
            "plugin",
            append_text(relative, text),
            "Plugin README Phase C identity contradiction",
        )
        for case_id, relative, text in SECOND_REMEDIATION_ADDITIONAL_INVALID_CASES
    ),
)


class SecondRemediationAdditionalValidTests(IdentityPolicyTestCase):
    """Additional canonical English real-subprocess valid controls."""


SECOND_REMEDIATION_ADDITIONAL_VALID_CASES = (
    # English: 6
    ("second_valid_en_01", PLUGIN_READMES[0], "This fixture must reject the claim \"Desktop gate passed.\""),
    ("second_valid_en_02", PLUGIN_READMES[0], "This document does not assert that the Desktop gate passed."),
    ("second_valid_en_03", PLUGIN_READMES[0], "A regression-test fixture may say verified without asserting any Desktop gate."),
    ("second_valid_en_04", PLUGIN_READMES[0], "Earlier Desktop gate evidence passed, but it is superseded and invalid for the current identity."),
    ("second_valid_en_05", PLUGIN_READMES[0], "Phase C Desktop registration must be re-verified in the future."),
    ("second_valid_en_06", PLUGIN_READMES[0], "When local installation is complete, restart the desktop application."),
    # Mixed language and Markdown boundaries: 6
)

install_positive_cases(
    SecondRemediationAdditionalValidTests,
    tuple(
        (case_id, "plugin", append_text(relative, text))
        for case_id, relative, text in SECOND_REMEDIATION_ADDITIONAL_VALID_CASES
    ),
)


class SecondRemediationCorpusContractTests(unittest.TestCase):
    def test_additional_real_subprocess_case_count_and_language_coverage(self):
        invalid_ids = [case[0] for case in SECOND_REMEDIATION_ADDITIONAL_INVALID_CASES]
        valid_ids = [case[0] for case in SECOND_REMEDIATION_ADDITIONAL_VALID_CASES]
        all_ids = invalid_ids + valid_ids
        self.assertEqual(14, len(invalid_ids))
        self.assertEqual(6, len(valid_ids))
        self.assertEqual(20, len(all_ids))
        self.assertEqual(20, sum("_en_" in case_id for case_id in all_ids))
        self.assertEqual(3, sum("adversarial" in case_id for case_id in all_ids))


class ThirdRemediationExactRf02Tests(IdentityPolicyTestCase):
    """Exact 16 RF02 false-reject mutations from the second re-audit ledger."""


THIRD_REMEDIATION_EXACT_RF02_CASES = (
    (
        "third_exact_second_en_pair_03_v",
        PLUGIN_READMES[0],
        "ACA-SECOND-SECOND-EN-PAIR-03-V: The fixture “current Desktop installation passed” is invalid.",
    ),
    (
        "third_exact_second_en_pair_04_v",
        PLUGIN_READMES[0],
        "ACA-SECOND-SECOND-EN-PAIR-04-V: The example “Phase C invocation succeeded” is prohibited as the current result.",
    ),
    (
        "third_exact_second_en_valid_01",
        PLUGIN_READMES[0],
        "ACA-SECOND-SECOND-EN-VALID-01: The same claim “current Phase C Desktop registration passed” is expected to be rejected.",
    ),
    (
        "third_exact_second_en_valid_08",
        PLUGIN_READMES[0],
        "ACA-SECOND-SECOND-EN-VALID-08: The code example `current marketplace discovery passed` is an invalid claim and must be rejected.",
    ),
)

install_positive_cases(
    ThirdRemediationExactRf02Tests,
    tuple(
        (case_id, "plugin", append_text(relative, text))
        for case_id, relative, text in THIRD_REMEDIATION_EXACT_RF02_CASES
    ),
)


class ThirdRemediationAdditionalValidTests(IdentityPolicyTestCase):
    """Twenty-four fresh same-claim explanatory real-subprocess controls."""


class ThirdRemediationAdditionalInvalidTests(IdentityPolicyTestCase):
    """Twenty-four minimally paired current-success real-subprocess controls."""


THIRD_REMEDIATION_ADDITIONAL_PAIRS = (
    # English: six pairs / twelve subprocess tests.
    (
        "third_pair_en_01",
        "English",
        PLUGIN_READMES[0],
        "This README does not assert the quoted claim “current Phase C Desktop registration passed”.",
        "This README asserts the quoted claim “current Phase C Desktop registration passed”.",
    ),
    (
        "third_pair_en_02",
        "English",
        PLUGIN_READMES[0],
        "The wording “Phase C explicit invocation succeeded” is prohibited as a current result.",
        "The wording “Phase C explicit invocation succeeded” is permitted as the current result.",
    ),
    (
        "third_pair_en_03",
        "English",
        PLUGIN_READMES[0],
        "The claim “current marketplace discovery\npassed” is expected to be rejected.",
        "The claim “current marketplace discovery\npassed” is expected to be accepted.",
    ),
    (
        "third_pair_en_04",
        "English",
        PLUGIN_READMES[0],
        "The code example `current Desktop marketplace installation passed` is an invalid claim.",
        "The code example `current Desktop marketplace installation passed` is the current result.",
    ),
    (
        "third_pair_en_05",
        "English",
        PLUGIN_READMES[0],
        "> The quoted text “current Phase C Desktop gate passed”\n> does not represent the current state.",
        "> The quoted text “current Phase C Desktop gate passed”\n> represents the current state.",
    ),
    (
        "third_pair_en_06",
        "English",
        PLUGIN_READMES[0],
        "The example “Phase C passed” is invalid.",
        "The example “Phase C passed” is invalid, but the current Desktop registration passed.",
    ),
)

install_positive_cases(
    ThirdRemediationAdditionalValidTests,
    tuple(
        (f"{case_id}_valid", "plugin", append_text(relative, valid_text))
        for case_id, _language, relative, valid_text, _invalid_text
        in THIRD_REMEDIATION_ADDITIONAL_PAIRS
    ),
)

install_invalid_regression_cases(
    ThirdRemediationAdditionalInvalidTests,
    tuple(
        InvalidRegressionCase(
            f"{case_id}_invalid",
            "third-remediation minimally paired current-success control",
            "invalid",
            "plugin",
            append_text(relative, invalid_text),
            "Plugin README Phase C identity contradiction",
        )
        for case_id, _language, relative, _valid_text, invalid_text
        in THIRD_REMEDIATION_ADDITIONAL_PAIRS
    ),
)


class ThirdRemediationCorpusContractTests(unittest.TestCase):
    def test_exact_and_additional_real_subprocess_contract(self):
        exact_ids = [case[0] for case in THIRD_REMEDIATION_EXACT_RF02_CASES]
        pair_ids = [case[0] for case in THIRD_REMEDIATION_ADDITIONAL_PAIRS]
        additional_valid_count = len(THIRD_REMEDIATION_ADDITIONAL_PAIRS)
        additional_invalid_count = len(THIRD_REMEDIATION_ADDITIONAL_PAIRS)
        self.assertEqual(4, len(exact_ids))
        self.assertEqual(len(exact_ids), len(set(exact_ids)))
        self.assertEqual(6, len(pair_ids))
        self.assertEqual(len(pair_ids), len(set(pair_ids)))
        self.assertEqual(6, additional_valid_count)
        self.assertEqual(6, additional_invalid_count)
        self.assertEqual(12, additional_valid_count + additional_invalid_count)
        languages = [case[1] for case in THIRD_REMEDIATION_ADDITIONAL_PAIRS]
        for language in (
            "English",
        ):
            self.assertGreaterEqual(languages.count(language) * 2, 12)


class FourthRemediationExactInvalidTests(IdentityPolicyTestCase):
    """Exact RF01 false-PASS records from the third re-audit ledger."""


FOURTH_REMEDIATION_EXACT_INVALID_CASES = (
    (
        "fourth_exact_third_en_rf01_06",
        PLUGIN_READMES[0],
        "ACA-THIRD-FRESH-EN-RF01-06: It is not true that the current Phase C Desktop gate has not passed.",
    ),
    (
        "fourth_exact_confirm_fp_en_01",
        PLUGIN_READMES[0],
        "ACA-THIRD-CONFIRM-FP-EN-01: The statement that the current Phase C Desktop gate did not pass is false.",
    ),
)

install_invalid_regression_cases(
    FourthRemediationExactInvalidTests,
    tuple(
        InvalidRegressionCase(
            case_id,
            "exact fourth-remediation RF01 real-subprocess regression",
            "invalid",
            "plugin",
            append_text(relative, text),
            "Plugin README Phase C identity contradiction",
        )
        for case_id, relative, text in FOURTH_REMEDIATION_EXACT_INVALID_CASES
    ),
)


class FourthRemediationExactValidTests(IdentityPolicyTestCase):
    """Exact RF02 false-reject records from the third re-audit ledger."""


FOURTH_REMEDIATION_EXACT_VALID_CASES = (
    (
        "fourth_exact_third_en_pair_13_v",
        PLUGIN_READMES[0],
        "ACA-THIRD-FRESH-EN-PAIR-13-V: The test case quotes “current Desktop registration succeeded” without asserting that result.",
    ),
    (
        "fourth_exact_confirm_fr_en_01",
        PLUGIN_READMES[0],
        "ACA-THIRD-CONFIRM-FR-EN-01: The current Phase C Desktop gate is not yet verified.",
    ),
    (
        "fourth_exact_confirm_fr_en_02",
        PLUGIN_READMES[0],
        "ACA-THIRD-CONFIRM-FR-EN-02: This fixture quotes “the current Desktop registration passed” without claiming that outcome.",
    ),
)

install_positive_cases(
    FourthRemediationExactValidTests,
    tuple(
        (case_id, "plugin", append_text(relative, text))
        for case_id, relative, text in FOURTH_REMEDIATION_EXACT_VALID_CASES
    ),
)


class FourthRemediationAdditionalValidTests(IdentityPolicyTestCase):
    """Thirty-two fresh predicate/reporting controls."""


class FourthRemediationAdditionalInvalidTests(IdentityPolicyTestCase):
    """Thirty-two minimally paired current-success controls."""


FOURTH_REMEDIATION_ADDITIONAL_PAIRS = (
    # English: eight pairs / sixteen subprocess tests.
    (
        "fourth_pair_en_01",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop gate remains unverified.",
        "The current Phase C Desktop gate is not unverified.",
    ),
    (
        "fourth_pair_en_02",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop gate remains incomplete.",
        "The current Phase C Desktop gate is not incomplete.",
    ),
    (
        "fourth_pair_en_03",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop gate remains pending.",
        "The current Phase C Desktop gate is not pending.",
    ),
    (
        "fourth_pair_en_04",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop registration remains unsuccessful.",
        "The current Phase C Desktop registration is not unsuccessful.",
    ),
    (
        "fourth_pair_en_05",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop check has not yet passed.",
        "The current Phase C Desktop check has now passed.",
    ),
    (
        "fourth_pair_en_06",
        "English",
        PLUGIN_READMES[0],
        "The fixture records the wording “current Desktop registration succeeded”.",
        "The fixture records “current Desktop registration succeeded” as the current result.",
    ),
    (
        "fourth_pair_en_07",
        "English",
        PLUGIN_READMES[0],
        "The test contains the input `current Phase C Desktop gate passed` for expected rejection.",
        "The test confirms `current Phase C Desktop gate passed` as the current outcome.",
    ),
    (
        "fourth_pair_en_08",
        "English",
        PLUGIN_READMES[0],
        "After the review, the current marketplace registration will be verified.",
        "A later review is planned, but the current marketplace registration is verified.",
    ),
    # Mixed language and Markdown: eight pairs / sixteen subprocess tests.
)

install_positive_cases(
    FourthRemediationAdditionalValidTests,
    tuple(
        (f"{case_id}_valid", "plugin", append_text(relative, valid_text))
        for case_id, _language, relative, valid_text, _invalid_text
        in FOURTH_REMEDIATION_ADDITIONAL_PAIRS
    ),
)

install_invalid_regression_cases(
    FourthRemediationAdditionalInvalidTests,
    tuple(
        InvalidRegressionCase(
            f"{case_id}_invalid",
            "fourth-remediation minimally paired semantic boundary control",
            "invalid",
            "plugin",
            append_text(relative, invalid_text),
            "Plugin README Phase C identity contradiction",
        )
        for case_id, _language, relative, _valid_text, invalid_text
        in FOURTH_REMEDIATION_ADDITIONAL_PAIRS
    ),
)


class FourthRemediationCorpusContractTests(unittest.TestCase):
    def test_exact_and_additional_real_subprocess_contract(self):
        exact_invalid_ids = [
            case[0] for case in FOURTH_REMEDIATION_EXACT_INVALID_CASES
        ]
        exact_valid_ids = [case[0] for case in FOURTH_REMEDIATION_EXACT_VALID_CASES]
        pair_ids = [case[0] for case in FOURTH_REMEDIATION_ADDITIONAL_PAIRS]
        self.assertEqual(2, len(exact_invalid_ids))
        self.assertEqual(3, len(exact_valid_ids))
        self.assertEqual(5, len(set(exact_invalid_ids + exact_valid_ids)))
        self.assertEqual(8, len(pair_ids))
        self.assertEqual(8, len(set(pair_ids)))
        self.assertEqual(8, len(FOURTH_REMEDIATION_ADDITIONAL_PAIRS))
        self.assertEqual(16, len(FOURTH_REMEDIATION_ADDITIONAL_PAIRS) * 2)
        languages = [case[1] for case in FOURTH_REMEDIATION_ADDITIONAL_PAIRS]
        for language in (
            "English",
        ):
            self.assertGreaterEqual(languages.count(language) * 2, 16)


class FifthRemediationExactInvalidTests(IdentityPolicyTestCase):
    """Exact RF01 false-PASS records from the regenerated fourth ledger."""


class FifthRemediationExactValidTests(IdentityPolicyTestCase):
    """Exact RF02 false-reject records from the regenerated fourth ledger."""


FIFTH_REMEDIATION_EXACT_CASES = (
    (
        "FOURTH-BOUNDARY-EN-01-B",
        "RF02",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FOURTH-BOUNDARY-EN-01-B: The fixture context context context context context context context context context context context context context context context records “the current Phase C Desktop gate passed” as sample wording.",
    ),
    (
        "FOURTH-BOUNDARY-EN-04-A",
        "RF02",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FOURTH-BOUNDARY-EN-04-A: The guide rejects [current Desktop registration succeeded](https://example.invalid/b-en-a) as prohibited wording.",
    ),
    (
        "FOURTH-CONFIRM-FR-EN-01",
        "RF02",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FOURTH-CONFIRM-EN-01: The fixture with extensive neutral context about locale, rendering, formatting, transport, archival, review, ownership, provenance, and retention records “the current Phase C Desktop gate passed” as sample wording.",
    ),
    (
        "FOURTH-SEGMENT-FP-EN-01",
        "RF01",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FOURTH-SEGMENT-EN-01: The fixture records sample wording\n\nThe current Phase C Desktop gate passed.",
    ),
)


install_positive_cases(
    FifthRemediationExactValidTests,
    tuple(
        (
            f"fifth_exact_{stable_id.lower().replace('-', '_')}",
            "plugin",
            append_text(relative, text),
        )
        for stable_id, _finding, _language, relative, expected, text
        in FIFTH_REMEDIATION_EXACT_CASES
        if expected == "valid"
    ),
)

install_invalid_regression_cases(
    FifthRemediationExactInvalidTests,
    tuple(
        InvalidRegressionCase(
            f"fifth_exact_{stable_id.lower().replace('-', '_')}",
            "exact superseding fifth-remediation RF01 real-subprocess regression",
            "invalid",
            "plugin",
            append_text(relative, text),
            "Plugin README Phase C identity contradiction",
        )
        for stable_id, _finding, _language, relative, expected, text
        in FIFTH_REMEDIATION_EXACT_CASES
        if expected == "invalid"
    ),
)


class FifthRemediationAdditionalValidTests(IdentityPolicyTestCase):
    """Additional structural Markdown claims that must remain valid."""


class FifthRemediationAdditionalInvalidTests(IdentityPolicyTestCase):
    """Additional structural Markdown claims that must be rejected."""


FIFTH_REMEDIATION_ADDITIONAL_CASES = (
    # Hard-boundary invalid: four per language.
    (
        "fifth_boundary_en_01",
        "hard_boundary_invalid",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-BOUNDARY-EN-01: The fixture records sample wording.\n\nThe current Phase C Desktop gate passed.",
        None,
    ),
    (
        "fifth_boundary_en_02",
        "hard_boundary_invalid",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-BOUNDARY-EN-02:\n- The guide quotes a prohibited claim.\n- The current Desktop registration succeeded.",
        None,
    ),
    (
        "fifth_boundary_en_03",
        "hard_boundary_invalid",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-BOUNDARY-EN-03:\n> The example records sample wording.\n>\n> The current marketplace installation succeeded.",
        None,
    ),
    (
        "fifth_boundary_en_04",
        "hard_boundary_invalid",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-BOUNDARY-EN-04: - Phase C\n  - Current Desktop discovery succeeded.",
        None,
    ),
    # Long-distance same-block valid: four per language.
    (
        "fifth_long_en_01",
        "same_block_long_distance_valid",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-LONG-EN-01: The fixture with extensive neutral context about locale rendering formatting transport archival review ownership provenance retention compatibility accessibility and maintenance records “the current Phase C Desktop gate passed” as sample wording.",
        None,
    ),
    (
        "fifth_long_en_02",
        "same_block_long_distance_valid",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-LONG-EN-02: The guide with extensive neutral context about locale rendering formatting transport archival review ownership provenance retention compatibility accessibility and maintenance rejects [current Desktop registration succeeded](https://example.invalid/fifth-long-en) as prohibited wording.",
        None,
    ),
    (
        "fifth_long_en_03",
        "same_block_long_distance_valid",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-LONG-EN-03: The documentation with extensive neutral context about locale rendering formatting transport archival review ownership provenance retention compatibility accessibility and maintenance stores `current marketplace installation succeeded` as a code example.",
        None,
    ),
    (
        "fifth_long_en_04",
        "same_block_long_distance_valid",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-LONG-EN-04: The report with extensive neutral context about locale rendering formatting transport archival review ownership provenance retention compatibility accessibility and maintenance mentions “current Desktop discovery passed” without asserting that outcome.",
        None,
    ),
    # Markdown visible-span cases: two valid and two invalid per language.
    (
        "fifth_span_en_01",
        "markdown_span_cases",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-SPAN-EN-01: The guide rejects [current Desktop registration succeeded](https://example.invalid/span-en) as prohibited wording.",
        None,
    ),
    (
        "fifth_span_en_02",
        "markdown_span_cases",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-SPAN-EN-02: The fixture records `the current Phase C Desktop gate passed` as a code example.",
        None,
    ),
    (
        "fifth_span_en_03",
        "markdown_span_cases",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-SPAN-EN-03: The current result is [Desktop registration succeeded](https://example.invalid/current-en).",
        None,
    ),
    (
        "fifth_span_en_04",
        "markdown_span_cases",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-SPAN-EN-04: The current result is “the Phase C Desktop gate passed”.",
        None,
    ),
    # Minimally paired adversarial cases: two pairs per language.
    (
        "fifth_pair_en_01_valid",
        "minimally_paired_adversarial",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-PAIR-EN-01: The fixture records “the current Phase C Desktop gate passed” as sample wording.",
        "same_block_vs_blank_line",
    ),
    (
        "fifth_pair_en_01_invalid",
        "minimally_paired_adversarial",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-PAIR-EN-01: The fixture records sample wording.\n\nThe current Phase C Desktop gate passed.",
        "same_block_vs_blank_line",
    ),
    (
        "fifth_pair_en_02_valid",
        "minimally_paired_adversarial",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "ACA-FIFTH-PAIR-EN-02: The guide rejects [current Desktop registration succeeded](https://example.invalid/pair-en) as prohibited wording.",
        "reported_link_vs_independent_link",
    ),
    (
        "fifth_pair_en_02_invalid",
        "minimally_paired_adversarial",
        "English",
        PLUGIN_READMES[0],
        "invalid",
        "ACA-FIFTH-PAIR-EN-02: The guide records a prohibited link.\n\n[current Desktop registration succeeded](https://example.invalid/pair-en)",
        "reported_link_vs_independent_link",
    ),
)


install_positive_cases(
    FifthRemediationAdditionalValidTests,
    tuple(
        (case_id, "plugin", append_text(relative, text))
        for case_id, _category, _language, relative, expected, text, _pair_id
        in FIFTH_REMEDIATION_ADDITIONAL_CASES
        if expected == "valid"
    ),
)

install_invalid_regression_cases(
    FifthRemediationAdditionalInvalidTests,
    tuple(
        InvalidRegressionCase(
            case_id,
            "superseding fifth-remediation structural Markdown control",
            "invalid",
            "plugin",
            append_text(relative, text),
            "Plugin README Phase C identity contradiction",
        )
        for case_id, _category, _language, relative, expected, text, _pair_id
        in FIFTH_REMEDIATION_ADDITIONAL_CASES
        if expected == "invalid"
    ),
)


class FifthRemediationCorpusContractTests(unittest.TestCase):
    def test_exact_and_additional_real_subprocess_contract(self):
        exact_ids = [case[0] for case in FIFTH_REMEDIATION_EXACT_CASES]
        self.assertEqual(4, len(exact_ids))
        self.assertEqual(4, len(set(exact_ids)))
        self.assertEqual(
            1,
            sum(
                1
                for _case_id, finding, _language, _relative, expected, _text
                in FIFTH_REMEDIATION_EXACT_CASES
                if finding == "RF01" and expected == "invalid"
            ),
        )
        self.assertEqual(
            3,
            sum(
                1
                for _case_id, finding, _language, _relative, expected, _text
                in FIFTH_REMEDIATION_EXACT_CASES
                if finding == "RF02" and expected == "valid"
            ),
        )

        additional_ids = [
            case[0] for case in FIFTH_REMEDIATION_ADDITIONAL_CASES
        ]
        self.assertEqual(16, len(additional_ids))
        self.assertEqual(16, len(set(additional_ids)))
        categories = [case[1] for case in FIFTH_REMEDIATION_ADDITIONAL_CASES]
        for category in (
            "hard_boundary_invalid",
            "same_block_long_distance_valid",
            "markdown_span_cases",
            "minimally_paired_adversarial",
        ):
            self.assertEqual(4, categories.count(category))
        languages = [case[2] for case in FIFTH_REMEDIATION_ADDITIONAL_CASES]
        for language in (
            "English",
        ):
            self.assertEqual(16, languages.count(language))
        pair_ids = {
            case[6]
            for case in FIFTH_REMEDIATION_ADDITIONAL_CASES
            if case[6] is not None
        }
        self.assertEqual(
            {
                "same_block_vs_blank_line",
                "reported_link_vs_independent_link",
            },
            pair_ids,
        )


class SixthRemediationExactValidTests(IdentityPolicyTestCase):
    """Exact false-reject records from the fifth-remediation re-audit."""


class SixthRemediationExactInvalidTests(IdentityPolicyTestCase):
    """Exact false-PASS records from the fifth-remediation re-audit."""


SIXTH_REMEDIATION_EXACT_CASES = (
    (
        "ACA-FIFTH-INDEP-EN-SPAN-10",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "The evidence note archives neutral sample terminology. The fixture records &ldquo;current Desktop registration succeeded&rdquo; as prohibited wording.\n\n<!-- ACA-FIFTH-INDEP-EN-SPAN-10 -->",
        "html_named_entity_reporting",
    ),
    (
        "ACA-FIFTH-INDEP-EN-SPAN-11",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "```text\nThe current Phase C Desktop gate passed.\n```\n\n<!-- ACA-FIFTH-INDEP-EN-SPAN-11 -->",
        "fenced_code_hidden_claim",
    ),
    (
        "ACA-FIFTH-INDEP-EN-SPAN-12",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "    The current Phase C Desktop gate passed.\n\n<!-- ACA-FIFTH-INDEP-EN-SPAN-12 -->",
        "indented_code_hidden_claim",
    ),
    (
        "ACA-FIFTH-INDEP-EN-SPAN-16",
        "English",
        PLUGIN_READMES[0],
        "valid",
        "[neutral source][destination-only]\n[destination-only]: https://example.invalid/current/Phase-C/Desktop/gate/passed\n\n<!-- ACA-FIFTH-INDEP-EN-SPAN-16 -->",
        "claimy_reference_destination_hidden",
    ),
)


def sixth_exact_mutation(case_id: str, relative: str, text: str) -> Mutation:
    """Apply canonical V2 replacements for host-contaminated exact cases."""

    if case_id.endswith(("SPAN-12", "SPAN-16")):
        if case_id.endswith("SPAN-16"):
            text = text.replace(
                "[neutral source][destination-only]\n[destination-only]:",
                "[neutral source][destination-only]\n\n[destination-only]:",
            )
        return replace_text(relative, text)
    return append_exact_text(relative, text)


install_positive_cases(
    SixthRemediationExactValidTests,
    tuple(
        (
            f"sixth_exact_{case_id.lower().replace('-', '_')}",
            "plugin",
            sixth_exact_mutation(case_id, relative, text),
        )
        for case_id, _language, relative, expected, text, _coverage
        in SIXTH_REMEDIATION_EXACT_CASES
        if expected == "valid"
    ),
)

install_invalid_regression_cases(
    SixthRemediationExactInvalidTests,
    tuple(
        InvalidRegressionCase(
            f"sixth_exact_{case_id.lower().replace('-', '_')}",
            "exact sixth-remediation false-PASS regression",
            "invalid",
            "plugin",
            sixth_exact_mutation(case_id, relative, text),
            "Plugin README Phase C identity contradiction",
        )
        for case_id, _language, relative, expected, text, _coverage
        in SIXTH_REMEDIATION_EXACT_CASES
        if expected == "invalid"
    ),
)


@dataclass(frozen=True)
class SixthLanguageSpec:
    slug: str
    language: str
    relative: str
    claim: str
    alternate_claim: str
    encoded_claim: str
    reported: str


@dataclass(frozen=True)
class SixthAdditionalCase:
    case_id: str
    category: str
    language: str
    relative: str
    expected: str
    text: str
    polarity: str


SIXTH_LANGUAGE_SPECS = (
    SixthLanguageSpec(
        "en",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop gate passed.",
        "Current Desktop registration succeeded.",
        "The current Phase C Desktop gate pass&#101;d.",
        "The fixture records “{claim}” as prohibited wording.",
    ),
)


def build_sixth_additional_cases() -> tuple[SixthAdditionalCase, ...]:
    cases: list[SixthAdditionalCase] = []

    def add(
        spec: SixthLanguageSpec,
        category: str,
        index: int,
        expected: str,
        text: str,
    ) -> None:
        cases.append(
            SixthAdditionalCase(
                f"sixth_{category}_{spec.slug}_{index:02d}",
                category,
                spec.language,
                spec.relative,
                expected,
                text,
                "positive" if expected == "invalid" else "negative",
            )
        )

    for spec in SIXTH_LANGUAGE_SPECS:
        reported_claim = spec.claim.rstrip(".")
        reported_alternate_claim = spec.alternate_claim.rstrip(".")
        reported_encoded_claim = spec.encoded_claim.rstrip(".")
        entity_valid = (
            spec.reported.format(claim=reported_claim)
            .replace("“", "&ldquo;")
            .replace("”", "&rdquo;"),
            spec.reported.format(claim=reported_alternate_claim)
            .replace("“", "&#8220;")
            .replace("”", "&#8221;"),
            spec.reported.format(claim=reported_claim)
            .replace("“", "&#x201c;")
            .replace("”", "&#x201d;"),
            spec.reported.format(claim=reported_encoded_claim),
        )
        entity_invalid = (
            spec.claim.replace(" ", "&#32;", 1),
            spec.alternate_claim.replace(" ", "&#x20;", 1),
            spec.encoded_claim,
            f"&#{ord(spec.claim[0])};{spec.claim[1:]}",
        )
        for index, text in enumerate(entity_valid + entity_invalid, 1):
            expected = "valid" if index <= len(entity_valid) else "invalid"
            add(spec, "entity", index, expected, text)

        code_valid = (
            f"```text\n{spec.claim}\n```",
            f"~~~text\n{spec.alternate_claim}\n~~~",
            f"````markdown\n```\n{spec.claim}\n```\n````",
            f"    {spec.claim}",
            f"The fixture stores `{spec.alternate_claim}` as code.",
            f"> ```text\n> {spec.claim}\n> ```",
        )
        code_invalid = (
            f"```text\nneutral fixture\n```\n\n{spec.claim}",
            f"`neutral code` {spec.claim}",
            f"- `{spec.alternate_claim}`\n- {spec.claim}",
            f"> ```text\n> neutral fixture\n> ```\n\n{spec.claim}",
            f"    neutral fixture\n\n{spec.alternate_claim}",
            f"~~~text\nneutral fixture\n~~~\n\n## Result\n{spec.claim}",
        )
        for index, text in enumerate(code_valid + code_invalid, 1):
            expected = "valid" if index <= len(code_valid) else "invalid"
            add(spec, "code", index, expected, text)

        destination = (
            "https://example.invalid/current/Phase-C/Desktop/gate/passed"
        )
        link_valid = (
            f"[neutral source][sixth-{spec.slug}-ref]\n"
            f"[sixth-{spec.slug}-ref]: {destination}",
            f'[neutral source](https://example.invalid/neutral "{spec.claim}")',
            spec.reported.format(
                claim=f"[{spec.alternate_claim}](https://example.invalid/sample)"
            ),
            f"<{destination}>",
        )
        link_invalid = (
            f"[{spec.claim}](https://example.invalid/neutral)",
            f"[{spec.alternate_claim}][sixth-{spec.slug}-plain]\n"
            f"[sixth-{spec.slug}-plain]: https://example.invalid/neutral",
            f"Current result: [{spec.alternate_claim}]"
            "(https://example.invalid/current)",
            f"[neutral](https://example.invalid/neutral)\n\n{spec.claim}",
        )
        for index, text in enumerate(link_valid + link_invalid, 1):
            expected = (
                "invalid"
                if index == 4
                else "valid" if index <= len(link_valid) else "invalid"
            )
            add(spec, "link", index, expected, text)

        cross_valid = (
            spec.reported.format(
                claim=f"[{spec.encoded_claim}]"
                "(https://example.invalid/entity-link)"
            ),
            f"```text\n{spec.encoded_claim}\n```\n\n[neutral](https://example.invalid)",
            f"> [neutral][sixth-{spec.slug}-cross]\n>\n"
            f"> [sixth-{spec.slug}-cross]: {destination}",
            f"- The fixture stores `{spec.encoded_claim}` as code.\n"
            "- Neutral rendered result.",
        )
        cross_invalid = (
            f"```text\nneutral\n```\n\n[{spec.encoded_claim}]"
            "(https://example.invalid/current)",
            f"[neutral][sixth-{spec.slug}-cross-invalid]\n"
            f"[sixth-{spec.slug}-cross-invalid]: https://example.invalid\n\n"
            f"{spec.encoded_claim}",
            f"> `neutral code`\n>\n> {spec.encoded_claim}",
            f"- [neutral](https://example.invalid)\n- {spec.encoded_claim}",
        )
        for index, text in enumerate(cross_valid + cross_invalid, 1):
            expected = "valid" if index <= len(cross_valid) else "invalid"
            add(spec, "cross", index, expected, text)

    return tuple(cases)


SIXTH_REMEDIATION_ADDITIONAL_CASES = build_sixth_additional_cases()


def sixth_additional_mutation(case: SixthAdditionalCase) -> Mutation:
    """Apply canonical V2 fixtures where appending inherited host structure."""

    if case.case_id.endswith("_04") and case.category == "code":
        return replace_text(case.relative, case.text)
    if case.case_id.endswith("_01") and case.category == "link":
        text = case.text.replace(
            f"[neutral source][sixth-{case.case_id[-5:-3]}-ref]\n",
            f"[neutral source][sixth-{case.case_id[-5:-3]}-ref]\n\n",
        )
        return replace_text(case.relative, text)
    return append_text(case.relative, case.text)


class SixthRemediationAdditionalValidTests(IdentityPolicyTestCase):
    """Entity, code, link, and cross-interaction negative controls."""


class SixthRemediationAdditionalInvalidTests(IdentityPolicyTestCase):
    """Entity, code, link, and cross-interaction positive controls."""


install_positive_cases(
    SixthRemediationAdditionalValidTests,
    tuple(
        (case.case_id, "plugin", sixth_additional_mutation(case))
        for case in SIXTH_REMEDIATION_ADDITIONAL_CASES
        if case.expected == "valid"
    ),
)

install_invalid_regression_cases(
    SixthRemediationAdditionalInvalidTests,
    tuple(
        InvalidRegressionCase(
            case.case_id,
            "sixth-remediation structural parser control",
            "invalid",
            "plugin",
            sixth_additional_mutation(case),
            "Plugin README Phase C identity contradiction",
        )
        for case in SIXTH_REMEDIATION_ADDITIONAL_CASES
        if case.expected == "invalid"
    ),
)


class SixthRemediationCorpusContractTests(unittest.TestCase):
    def test_exact_and_additional_real_subprocess_contract(self):
        exact_ids = [case[0] for case in SIXTH_REMEDIATION_EXACT_CASES]
        self.assertEqual(4, len(exact_ids))
        self.assertEqual(4, len(set(exact_ids)))
        self.assertEqual(
            {"valid": 4, "invalid": 0},
            {
                expected: sum(
                    case[3] == expected
                    for case in SIXTH_REMEDIATION_EXACT_CASES
                )
                for expected in ("valid", "invalid")
            },
        )

        additional = SIXTH_REMEDIATION_ADDITIONAL_CASES
        self.assertEqual(36, len(additional))
        self.assertEqual(36, len({case.case_id for case in additional}))
        self.assertEqual(
            {"valid": 17, "invalid": 19},
            {
                expected: sum(case.expected == expected for case in additional)
                for expected in ("valid", "invalid")
            },
        )
        self.assertEqual(
            {
                "sixth_link_en_04",
            },
            {
                case.case_id
                for case in additional
                if case.category == "link"
                and case.case_id.endswith("_04")
                and case.expected == "invalid"
            },
        )
        expected_category_counts = {
            "entity": 8,
            "code": 12,
            "link": 8,
            "cross": 8,
        }
        self.assertEqual(
            expected_category_counts,
            {
                category: sum(case.category == category for case in additional)
                for category in expected_category_counts
            },
        )
        for language in (spec.language for spec in SIXTH_LANGUAGE_SPECS):
            language_cases = [
                case for case in additional if case.language == language
            ]
            self.assertEqual(36, len(language_cases))
            self.assertEqual(
                {"positive", "negative"},
                {case.polarity for case in language_cases},
            )
            for category in expected_category_counts:
                category_cases = [
                    case
                    for case in language_cases
                    if case.category == category
                ]
                self.assertIn("valid", {case.expected for case in category_cases})
                self.assertIn(
                    "invalid",
                    {case.expected for case in category_cases},
                )


@dataclass(frozen=True)
class SeventhLanguageSpec:
    slug: str
    language: str
    relative: str
    claim: str
    entity_character: str


@dataclass(frozen=True)
class SeventhRegressionCase:
    case_id: str
    family: str
    language: str
    relative: str
    expected: str
    distinction: str
    text: str


SEVENTH_LANGUAGE_SPECS = (
    SeventhLanguageSpec(
        "en",
        "English",
        PLUGIN_READMES[0],
        "The current Phase C Desktop gate is verified.",
        "d",
    ),
)


def build_seventh_regression_cases() -> tuple[SeventhRegressionCase, ...]:
    cases: list[SeventhRegressionCase] = []

    def add(
        spec: SeventhLanguageSpec,
        family: str,
        ordinal: int,
        expected: str,
        distinction: str,
        body: str,
    ) -> None:
        case_id = f"seventh_{family}_{spec.slug}_{ordinal:02d}"
        cases.append(
            SeventhRegressionCase(
                case_id,
                family,
                spec.language,
                spec.relative,
                expected,
                distinction,
                f"{body}\n\n<!-- {case_id} -->",
            )
        )

    for spec in SEVENTH_LANGUAGE_SPECS:
        character = spec.entity_character
        codepoint = ord(character)
        claim_without_terminal = spec.claim.rstrip(".")
        valid_entity_literals = (
            (
                "semicolonless_decimal",
                spec.claim.replace(character, f"&#{codepoint}", 1),
            ),
            (
                "semicolonless_hexadecimal",
                spec.claim.replace(character, f"&#x{codepoint:x}", 1),
            ),
            (
                "overlong_decimal_reference",
                spec.claim.replace(character, f"&#{codepoint:08d};", 1),
            ),
            (
                "unknown_named_reference",
                spec.claim.replace(character, "&NotACommonMarkEntity;", 1),
            ),
        )
        invalid_entity_claims = (
            (
                "terminated_decimal_reference",
                spec.claim.replace(character, f"&#{codepoint};", 1),
            ),
            (
                "terminated_lower_hex_reference",
                spec.claim.replace(character, f"&#x{codepoint:x};", 1),
            ),
            (
                "terminated_upper_hex_reference",
                spec.claim.replace(character, f"&#X{codepoint:X};", 1),
            ),
            (
                "terminated_zero_padded_hex_reference",
                spec.claim.replace(character, f"&#x{codepoint:06x};", 1),
            ),
        )
        for ordinal, (distinction, body) in enumerate(
            valid_entity_literals + invalid_entity_claims,
            1,
        ):
            add(
                spec,
                "entity_boundary",
                ordinal,
                "valid" if ordinal <= 4 else "invalid",
                distinction,
                body,
            )

        paragraph_cases = (
            (
                "valid",
                "four_space_top_level_code",
                f"# Neutral separator\n\n    {spec.claim}",
            ),
            (
                "valid",
                "tab_top_level_code",
                f"---\n\n\t{spec.claim}",
            ),
            ("valid", "six_space_top_level_code", f"      {spec.claim}"),
            (
                "valid",
                "multiline_indented_code",
                f"Neutral boundary\n\n    neutral specimen\n    {spec.claim}",
            ),
            (
                "invalid",
                "four_space_open_paragraph_continuation",
                f"Neutral paragraph continues\n    {spec.claim}",
            ),
            (
                "invalid",
                "tab_open_paragraph_continuation",
                f"Neutral paragraph continues\n\t{spec.claim}",
            ),
            (
                "invalid",
                "three_space_paragraph_continuation",
                f"Neutral paragraph continues\n   {spec.claim}",
            ),
            (
                "invalid",
                "two_space_paragraph_continuation",
                f"Neutral paragraph continues\n  {spec.claim}",
            ),
        )
        for ordinal, (expected, distinction, body) in enumerate(
            paragraph_cases,
            1,
        ):
            add(
                spec,
                "paragraph_indentation",
                ordinal,
                expected,
                distinction,
                body,
            )

        fence_cases = (
            (
                "valid",
                "closed_backtick_fence",
                f"```text\n{spec.claim}\n```",
            ),
            (
                "valid",
                "closed_tilde_fence",
                f"~~~~text\n{spec.claim}\n~~~~",
            ),
            (
                "valid",
                "long_fence_contains_short_fence",
                f"`````markdown\n```\n{spec.claim}\n```\n`````",
            ),
            (
                "valid",
                "unclosed_fence_to_container_end",
                f"```text\n{spec.claim}",
            ),
            (
                "invalid",
                "backtick_in_three_tick_info_string",
                f"```bad`info\n{spec.claim}\n```",
            ),
            (
                "invalid",
                "backtick_in_four_tick_info_string",
                f"````bad`info\n{spec.claim}\n````",
            ),
            (
                "invalid",
                "claim_after_exact_closing_fence",
                f"```text\nneutral specimen\n```\n{spec.claim}",
            ),
            (
                "invalid",
                "claim_after_indented_closing_fence",
                f"```text\nneutral specimen\n  ```\n{spec.claim}",
            ),
        )
        for ordinal, (expected, distinction, body) in enumerate(fence_cases, 1):
            add(
                spec,
                "fence_validity",
                ordinal,
                expected,
                distinction,
                body,
            )

        blockquote_cases = (
            (
                "valid",
                "blockquote_fenced_code",
                f"> ```text\n> {spec.claim}\n> ```",
            ),
            (
                "valid",
                "nested_blockquote_fenced_code",
                f"> > ~~~text\n> > {spec.claim}\n> > ~~~",
            ),
            (
                "valid",
                "blockquote_indented_code",
                f">     {spec.claim}",
            ),
            (
                "valid",
                "blockquote_list_nested_fence",
                f"> - ```text\n>   {spec.claim}\n>   ```",
            ),
            (
                "invalid",
                "lazy_blockquote_paragraph_continuation",
                f"> Neutral paragraph\n{spec.claim}",
            ),
            (
                "invalid",
                "explicit_blockquote_paragraph_continuation",
                f"> Neutral paragraph\n> {spec.claim}",
            ),
            (
                "invalid",
                "nested_blockquote_lazy_continuation",
                f"> > Neutral paragraph\n{spec.claim}",
            ),
            (
                "invalid",
                "claim_after_blockquote_fence",
                f"> ```text\n> neutral specimen\n> ```\n{spec.claim}",
            ),
        )
        for ordinal, (expected, distinction, body) in enumerate(
            blockquote_cases,
            1,
        ):
            add(
                spec,
                "blockquote_container",
                ordinal,
                expected,
                distinction,
                body,
            )

        list_cases = (
            (
                "valid",
                "bullet_item_direct_fence",
                f"- ```text\n  {spec.claim}\n  ```",
            ),
            (
                "valid",
                "ordered_item_direct_tilde_fence",
                f"1. ~~~text\n   {spec.claim}\n   ~~~",
            ),
            (
                "valid",
                "bullet_item_second_block_fence",
                f"- neutral item\n\n  ```text\n  {spec.claim}\n  ```",
            ),
            (
                "valid",
                "nested_list_item_fence",
                f"- outer item\n  - ```text\n    {spec.claim}\n    ```",
            ),
            (
                "invalid",
                "same_item_paragraph_after_fence",
                f"- ```text\n  neutral specimen\n  ```\n  {spec.claim}",
            ),
            (
                "invalid",
                "next_ordered_item_visible_claim",
                f"1. ```text\n   neutral specimen\n   ```\n2. {spec.claim}",
            ),
            (
                "invalid",
                "nested_sibling_item_visible_claim",
                f"- outer item\n  - ```text\n    neutral specimen\n    ```\n  - {spec.claim}",
            ),
            (
                "invalid",
                "top_level_claim_after_list_fence",
                f"- ```text\n  neutral specimen\n  ```\n\n{spec.claim}",
            ),
        )
        for ordinal, (expected, distinction, body) in enumerate(list_cases, 1):
            add(
                spec,
                "list_item_fence",
                ordinal,
                expected,
                distinction,
                body,
            )

        historical_cases = (
            (
                "valid",
                "invalidation_before_quoted_occurrence",
                f"An earlier superseded and invalid record says “{spec.claim}”",
            ),
            (
                "valid",
                "invalidation_after_unquoted_occurrence",
                f"An earlier record said {claim_without_terminal}, and that old result is invalid.",
            ),
            (
                "valid",
                "prior_invalid_record_unquoted_occurrence",
                f"The prior invalid marketplace record stated {spec.claim}",
            ),
            (
                "valid",
                "reported_prohibited_quotation",
                f"The historical fixture records “{claim_without_terminal}” as prohibited wording.",
            ),
            (
                "invalid",
                "historical_then_independent_paragraph",
                f"An earlier invalid record said “{spec.claim}”\n\n{spec.claim}",
            ),
            (
                "invalid",
                "historical_then_current_contrast",
                f"An earlier invalid record said “{spec.claim}”, but currently {spec.claim}",
            ),
            (
                "invalid",
                "historical_list_then_current_item",
                f"- An earlier invalid record said “{spec.claim}”\n- {spec.claim}",
            ),
            (
                "invalid",
                "historical_blockquote_then_current_prose",
                f"> An earlier invalid record said “{spec.claim}”\n\n{spec.claim}",
            ),
        )
        for ordinal, (expected, distinction, body) in enumerate(
            historical_cases,
            1,
        ):
            add(
                spec,
                "historical_relation",
                ordinal,
                expected,
                distinction,
                body,
            )

    return tuple(cases)


SEVENTH_REMEDIATION_REGRESSION_CASES = build_seventh_regression_cases()


class SeventhRemediationAdditionalValidTests(IdentityPolicyTestCase):
    """CommonMark structural and relation preservation controls."""


class SeventhRemediationAdditionalInvalidTests(IdentityPolicyTestCase):
    """CommonMark structural and relation rejection controls."""


install_positive_cases(
    SeventhRemediationAdditionalValidTests,
    tuple(
        (case.case_id, "plugin", append_text(case.relative, case.text))
        for case in SEVENTH_REMEDIATION_REGRESSION_CASES
        if case.expected == "valid"
    ),
)

install_invalid_regression_cases(
    SeventhRemediationAdditionalInvalidTests,
    tuple(
        InvalidRegressionCase(
            case.case_id,
            f"seventh-remediation {case.family} CommonMark control",
            "invalid",
            "plugin",
            append_text(case.relative, case.text),
            "Plugin README Phase C identity contradiction",
        )
        for case in SEVENTH_REMEDIATION_REGRESSION_CASES
        if case.expected == "invalid"
    ),
)


class SeventhRemediationCorpusContractTests(unittest.TestCase):
    def test_unique_balanced_real_subprocess_regression_contract(self):
        cases = SEVENTH_REMEDIATION_REGRESSION_CASES
        self.assertEqual(48, len(cases))
        self.assertEqual(48, len({case.case_id for case in cases}))
        self.assertEqual(
            48,
            len(
                {
                    hashlib.sha256(case.text.encode("utf-8")).hexdigest()
                    for case in cases
                }
            ),
        )
        self.assertEqual(
            {"valid": 24, "invalid": 24},
            {
                expected: sum(case.expected == expected for case in cases)
                for expected in ("valid", "invalid")
            },
        )
        expected_families = {
            "entity_boundary",
            "paragraph_indentation",
            "fence_validity",
            "blockquote_container",
            "list_item_fence",
            "historical_relation",
        }
        self.assertEqual(expected_families, {case.family for case in cases})
        for family in expected_families:
            family_cases = [case for case in cases if case.family == family]
            self.assertEqual(8, len(family_cases))
            self.assertEqual(4, sum(case.expected == "valid" for case in family_cases))
            self.assertEqual(4, sum(case.expected == "invalid" for case in family_cases))
        for language in (spec.language for spec in SEVENTH_LANGUAGE_SPECS):
            language_cases = [case for case in cases if case.language == language]
            self.assertEqual(48, len(language_cases))
            self.assertEqual(24, sum(case.expected == "valid" for case in language_cases))
            self.assertEqual(24, sum(case.expected == "invalid" for case in language_cases))
        self.assertEqual(
            48,
            len(
                {
                    (case.family, case.language, case.distinction)
                    for case in cases
                }
            ),
        )


if __name__ == "__main__":
    unittest.main()
