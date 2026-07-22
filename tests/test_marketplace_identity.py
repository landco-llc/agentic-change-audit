from __future__ import annotations

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
    "plugins/agentic-change-audit/README.ja.md",
    "plugins/agentic-change-audit/README.zh-Hant.md",
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
            "prior_d14",
            "fresh D14: append prohibited status claim",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[1],
                "Phase Cのdesktop登録、発見、install、明示呼び出し、working "
                "tree確認はすべて完了しました。Fresh D14。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "prior_d15",
            "fresh D15: append prohibited status claim",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[2],
                "Phase C 的桌面註冊、探索、安裝、明確叫用與工作樹檢查現已全部完成。"
                "Fresh D15。",
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
    """Sixteen multilingual contradiction and competing-version cases."""


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
            "readme_hardening_02",
            "Japanese neutral-identity Phase C gate completed claim is rejected",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "neutral identityのPhase C desktop gateは完了しました。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_03",
            "Traditional Chinese Phase C desktop gate passed claim is rejected",
            "invalid",
            "plugin",
            append_text(PLUGIN_READMES[2], "中性 identity 的 Phase C 桌面 gate 已通過。"),
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
            "readme_hardening_05",
            "Japanese Phase C desktop approval claim is rejected",
            "invalid",
            "submission",
            append_text(PLUGIN_READMES[1], "Phase Cのdesktop gateは承認済みです。"),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_06",
            "Traditional Chinese Phase C desktop success claim is rejected",
            "invalid",
            "submission",
            append_text(PLUGIN_READMES[2], "Phase C 桌面驗證現已成功。"),
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
            "readme_hardening_08",
            "Japanese current marketplace discovery verified claim is rejected",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "0.1.0-dev.3のmarketplace発見は検証済みです。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_09",
            "Traditional Chinese current install completion claim is rejected",
            "invalid",
            "plugin",
            append_text(PLUGIN_READMES[2], "0.1.0-dev.3 的 marketplace 安裝已完成。"),
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
            "readme_hardening_11",
            "Japanese current working-tree non-mutation claim is rejected",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[1],
                "0.1.0-dev.3のGit working tree非変更は確認済みです。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_12",
            "Traditional Chinese current working-tree verification is rejected",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[2],
                "0.1.0-dev.3 的工作樹未變更已驗證。",
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
            "readme_hardening_14",
            "Japanese competing development version is rejected",
            "invalid",
            "plugin",
            append_text(PLUGIN_READMES[1], "Plugin development versionは1.2.3-dev.9です。"),
            "Plugin README development-version mismatch",
        ),
        InvalidRegressionCase(
            "readme_hardening_15",
            "Traditional Chinese competing development version is rejected",
            "invalid",
            "plugin",
            append_text(PLUGIN_READMES[2], "Plugin development version 為 0.1.0-dev.30。"),
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
        InvalidRegressionCase(
            "readme_hardening_18",
            "Japanese invalidation cannot license a later completion claim",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "neutral identityの旧証拠は失効していますが、Phase C desktop gateは完了しました。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "readme_hardening_19",
            "Traditional Chinese pending wording cannot hide a later verified claim",
            "invalid",
            "submission",
            append_text(
                PLUGIN_READMES[2],
                "neutral identity 的 Phase C 桌面 gate 尚未完成，但是現已驗證。",
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
            "remediation_valid_04_japanese_historical_invalidation_passes",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "以前のdesktop証拠は存在しましたが、旧identity向けで失効しています。",
            ),
        ),
        (
            "remediation_valid_05_traditional_chinese_history_passes",
            "plugin",
            append_text(
                PLUGIN_READMES[2],
                "先前的 desktop 證據確實存在，但僅適用舊 identity 且已失效。",
            ),
        ),
        (
            "remediation_valid_06_english_future_phase_c_instruction_passes",
            "submission",
            append_text(
                PLUGIN_READMES[0],
                "Phase C desktop registration must be re-verified in the future.",
            ),
        ),
        (
            "remediation_valid_07_japanese_future_phase_c_instruction_passes",
            "submission",
            append_text(
                PLUGIN_READMES[1],
                "Phase Cのdesktop登録は将来再検証する予定です。",
            ),
        ),
        (
            "remediation_valid_08_traditional_chinese_future_instruction_passes",
            "submission",
            append_text(
                PLUGIN_READMES[2],
                "須於未來 Phase C 重新驗證 desktop marketplace 註冊。",
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
        (
            "remediation_valid_10_japanese_install_instruction_passes",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "local installが完了したらChatGPT desktop appを再起動してください。",
            ),
        ),
        (
            "remediation_valid_11_traditional_chinese_install_instruction_passes",
            "plugin",
            append_text(
                PLUGIN_READMES[2],
                "local 安裝完成後，請重新啟動 ChatGPT desktop app。",
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
            "exact_rdm_028",
            "RF01 RDM-028 exact Japanese soft-line-break mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "ACA-FRESH-RDM-028: 中立な marketplace identity の Phase C "
                "desktop gate は\n検証済みです。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_029",
            "RF01 RDM-029 exact Traditional Chinese line-break mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[2],
                "ACA-FRESH-RDM-029: 中性 marketplace identity 的 Phase C 桌面 "
                "gate\n現已通過。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_030",
            "RF01 RDM-030 exact mixed-language approval mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[0],
                "ACA-FRESH-RDM-030: Neutral identity の Phase C desktop gate は"
                "\napproved now.",
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
            "exact_rdm_034",
            "RF01 RDM-034 exact Japanese registration mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[1],
                "ACA-FRESH-RDM-034: 0.1.0-dev.3のmarketplace登録は\n完了しました。",
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_035",
            "RF01 RDM-035 exact Traditional Chinese install mutation",
            "invalid",
            "plugin",
            append_text(
                PLUGIN_READMES[2],
                "ACA-FRESH-RDM-035: 0.1.0-dev.3 的 marketplace 安裝\n現已完成。",
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
                (
                    "It does not verify the renamed **Agentic Change Audit "
                    "marketplace** or Plugin version `0.1.0-dev.3`;"
                ).encode(),
                (
                    "It verifies the renamed **Agentic Change Audit marketplace** "
                    "and Plugin version `0.1.0-dev.3`; ACA-FRESH-RDM-039"
                ).encode(),
            ),
            "Plugin README Phase C identity contradiction",
        ),
        InvalidRegressionCase(
            "exact_rdm_040",
            "RF01 RDM-040 exact Japanese denial replacement",
            "invalid",
            "plugin",
            replace_bytes(
                PLUGIN_READMES[1],
                (
                    "名称変更後の**Agentic Change Audit marketplace**またはPlugin "
                    "version `0.1.0-dev.3`を検証するものではありません。"
                ).encode(),
                (
                    "名称変更後の**Agentic Change Audit marketplace**とPlugin "
                    "version `0.1.0-dev.3`は検証済みです。 ACA-FRESH-RDM-040"
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
    """Fifty additional multilingual real-subprocess invalid controls."""


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
    # Japanese: 12
    ("second_invalid_ja_01", PLUGIN_READMES[1], "中立な marketplace identity の Phase C desktop gate は\n検証済みです。"),
    ("second_invalid_ja_02", PLUGIN_READMES[1], "現行marketplace\n- 登録\n- は完了しました。"),
    ("second_invalid_ja_03", PLUGIN_READMES[1], "> Phase Cのdesktop gate\n> は承認済みです。"),
    ("second_invalid_ja_04", PLUGIN_READMES[1], "**中立 identity** の [desktop gate](https://example.invalid/ja) は\n合格済みです。"),
    ("second_invalid_ja_05", PLUGIN_READMES[1], "Phase Cは未完了ではなく、検証済みです。"),
    ("second_invalid_ja_06", PLUGIN_READMES[1], "Phase Cは未検証ではなく、合格済みです。"),
    ("second_invalid_ja_07", PLUGIN_READMES[1], "Phase Cはもはやpendingではなく、完了しました。"),
    ("second_invalid_ja_08", PLUGIN_READMES[1], "現行の中立identityを説明します。desktop登録は成功しました。"),
    ("second_invalid_ja_09", PLUGIN_READMES[1], "旧desktop証拠は合格済みでしたが失効しています。現在のPhase C desktop gateは合格済みです。"),
    ("second_invalid_ja_10_adversarial", PLUGIN_READMES[1], "fixtureは「Desktop gate通過」を拒否します。しかし現在のDesktop gateは通過しました。"),
    ("second_invalid_ja_11", PLUGIN_READMES[1], "現行version 0.1.0-dev.3のmarketplace発見とworking tree非変更は\n確認済みです。"),
    ("second_invalid_ja_12", PLUGIN_READMES[1], "現在のmarketplace明示呼び出しは承認済みです。"),
    # Taiwan Traditional Chinese: 12
    ("second_invalid_zh_01", PLUGIN_READMES[2], "中性 marketplace identity 的 Phase C 桌面 gate\n現已通過。"),
    ("second_invalid_zh_02", PLUGIN_READMES[2], "目前 marketplace\n- 註冊\n- 已完成。"),
    ("second_invalid_zh_03", PLUGIN_READMES[2], "> Phase C 桌面 gate\n> 已獲核准。"),
    ("second_invalid_zh_04", PLUGIN_READMES[2], "**中性 identity** 的 [桌面 gate](https://example.invalid/zh)\n驗證完成。"),
    ("second_invalid_zh_05", PLUGIN_READMES[2], "Phase C 並非尚未完成，而是已通過。"),
    ("second_invalid_zh_06", PLUGIN_READMES[2], "Phase C 並非未驗證，而是現已驗證。"),
    ("second_invalid_zh_07", PLUGIN_READMES[2], "Phase C 已不再 pending 且已完成。"),
    ("second_invalid_zh_08", PLUGIN_READMES[2], "目前中性 identity 已記錄。桌面註冊已成功。"),
    ("second_invalid_zh_09", PLUGIN_READMES[2], "舊桌面證據曾通過但已失效。目前 Phase C 桌面 gate 已通過。"),
    ("second_invalid_zh_10_adversarial", PLUGIN_READMES[2], "fixture 用來拒絕「Desktop gate 已通過」。但是目前 Desktop gate 已通過。"),
    ("second_invalid_zh_11", PLUGIN_READMES[2], "目前 0.1.0-dev.3 的 marketplace 探索與工作樹未變更\n已驗證。"),
    ("second_invalid_zh_12", PLUGIN_READMES[2], "更名後 marketplace 的明確叫用已核准。"),
    # Mixed language and Markdown boundaries: 12
    ("second_invalid_mixed_01", PLUGIN_READMES[0], "Current neutral identity の Phase C desktop gate は\n検証済みです。"),
    ("second_invalid_mixed_02", PLUGIN_READMES[1], "現在の marketplace registration\n- 已完成。"),
    ("second_invalid_mixed_03", PLUGIN_READMES[2], "> Phase C Desktop gate は\n> approved now。"),
    ("second_invalid_mixed_04", PLUGIN_READMES[0], "The [中性 marketplace identity](https://example.invalid/mixed) Phase C gate is **完了済み**."),
    ("second_invalid_mixed_05", PLUGIN_READMES[1], "Phase C is not pending；現已通過。"),
    ("second_invalid_mixed_06", PLUGIN_READMES[2], "Phase Cは未完了ではなく；verified successfully。"),
    ("second_invalid_mixed_07", PLUGIN_READMES[0], "The current neutral identity is documented。desktop註冊は成功しました。"),
    ("second_invalid_mixed_08_adversarial", PLUGIN_READMES[1], "「Desktop gate passed」は禁止例です。しかし current Desktop gate 已通過。"),
    ("second_invalid_mixed_09_adversarial", PLUGIN_READMES[2], "Earlier desktop gate passed and is superseded。現在のDesktop gateは合格済みです。"),
    ("second_invalid_mixed_10_adversarial", PLUGIN_READMES[0], "The current Phase C statement is:\n```text\nDesktop gate passed.\n```"),
    ("second_invalid_mixed_11", PLUGIN_READMES[1], "0.1.0-dev.3 の marketplace [discovery](https://example.invalid/discovery)\n驗證完成。"),
    ("second_invalid_mixed_12", PLUGIN_READMES[2], "Current working-tree non-mutation と明示呼び出しは approved。"),
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
    """Twenty-four additional multilingual real-subprocess valid controls."""


SECOND_REMEDIATION_ADDITIONAL_VALID_CASES = (
    # English: 6
    ("second_valid_en_01", PLUGIN_READMES[0], "This fixture must reject the claim \"Desktop gate passed.\""),
    ("second_valid_en_02", PLUGIN_READMES[0], "This document does not assert that the Desktop gate passed."),
    ("second_valid_en_03", PLUGIN_READMES[0], "A regression-test fixture may say verified without asserting any Desktop gate."),
    ("second_valid_en_04", PLUGIN_READMES[0], "Earlier Desktop gate evidence passed, but it is superseded and invalid for the current identity."),
    ("second_valid_en_05", PLUGIN_READMES[0], "Phase C Desktop registration must be re-verified in the future."),
    ("second_valid_en_06", PLUGIN_READMES[0], "When local installation is complete, restart the desktop application."),
    # Japanese: 6
    ("second_valid_ja_01", PLUGIN_READMES[1], "「Desktop gate通過」は禁止される例で、現在状態を示しません。"),
    ("second_valid_ja_02", PLUGIN_READMES[1], "この文書はDesktop gateが合格済みだと主張しません。"),
    ("second_valid_ja_03", PLUGIN_READMES[1], "このfixtureは「Desktop gate合格」という主張を拒否するための説明であり、合格を主張しません。"),
    ("second_valid_ja_04", PLUGIN_READMES[1], "過去のDesktop gateは合格済みでしたが、その証拠は失効しており現行identityには無効です。"),
    ("second_valid_ja_05", PLUGIN_READMES[1], "Phase Cのdesktop登録は将来再検証する予定です。"),
    ("second_valid_ja_06", PLUGIN_READMES[1], "local installが完了したらdesktop appを再起動してください。"),
    # Taiwan Traditional Chinese: 6
    ("second_valid_zh_01", PLUGIN_READMES[2], "此 fixture 用來拒絕「Desktop gate 已通過」的說法，並未主張已通過。"),
    ("second_valid_zh_02", PLUGIN_READMES[2], "本文件並未主張目前 Desktop gate 已通過。"),
    ("second_valid_zh_03", PLUGIN_READMES[2], "「Desktop gate 已完成」是禁止範例，不表示目前狀態。"),
    ("second_valid_zh_04", PLUGIN_READMES[2], "先前 Desktop gate 曾通過，但該證據已失效且不代表目前 identity。"),
    ("second_valid_zh_05", PLUGIN_READMES[2], "須於未來重新驗證 Phase C 的 desktop marketplace 註冊。"),
    ("second_valid_zh_06", PLUGIN_READMES[2], "local 安裝完成後，請重新啟動 desktop app。"),
    # Mixed language and Markdown boundaries: 6
    ("second_valid_mixed_01", PLUGIN_READMES[0], "This fixture must reject `Desktop gate 已通過`; it does not assert that result."),
    ("second_valid_mixed_02", PLUGIN_READMES[1], "このdocument does not assert that [Desktop gate passed](https://example.invalid/claim)。"),
    ("second_valid_mixed_03", PLUGIN_READMES[2], "此 fixture must reject the claim 「Desktop gate passed」，並未主張通過。"),
    ("second_valid_mixed_04", PLUGIN_READMES[0], "Phase C の Desktop registration will be re-verified 未來."),
    ("second_valid_mixed_05", PLUGIN_READMES[1], "Earlier Desktop gateはpassedでしたが、旧identity向けでsuperseded and invalidです。"),
    ("second_valid_mixed_06", PLUGIN_READMES[2], "Legal developer identity: [L&Co.LLC](https://github.com/landco-llc); this does not assert a Desktop gate passed."),
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
        self.assertEqual(50, len(invalid_ids))
        self.assertEqual(24, len(valid_ids))
        self.assertEqual(74, len(all_ids))
        self.assertGreaterEqual(sum("_en_" in case_id for case_id in all_ids), 15)
        self.assertGreaterEqual(sum("_ja_" in case_id for case_id in all_ids), 15)
        self.assertGreaterEqual(sum("_zh_" in case_id for case_id in all_ids), 15)
        self.assertGreaterEqual(
            sum("_mixed_" in case_id for case_id in all_ids),
            15,
        )
        self.assertGreaterEqual(sum("adversarial" in case_id for case_id in all_ids), 6)


if __name__ == "__main__":
    unittest.main()
