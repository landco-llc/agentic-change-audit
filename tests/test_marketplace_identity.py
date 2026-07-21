from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
