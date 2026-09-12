from __future__ import annotations

"""Compatibility test entry point for post-W010/W013 Plugin state."""

import importlib.util
import sys
from pathlib import Path


CORE_TEST_PATH = Path(__file__).with_name("codex_plugin_core_tests.py")
CORE_TEST_MODULE_NAME = "_aca_codex_plugin_core_tests"
POST_W013_DISPLAY_NAME = "ACA - Agentic Change Audit"


def _load_core_tests():
    spec = importlib.util.spec_from_file_location(CORE_TEST_MODULE_NAME, CORE_TEST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load preserved Plugin tests: {CORE_TEST_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[CORE_TEST_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(CORE_TEST_MODULE_NAME, None)
        raise
    return module


_core_tests = _load_core_tests()
_core_build_plugin_repo = _core_tests.build_plugin_repo


def _build_plugin_repo_with_validator_core(temp: str):
    root = _core_build_plugin_repo(temp)
    core = _core_tests.ROOT / "scripts/validate-codex-plugin-core.py"
    destination = root / "scripts/validate-codex-plugin-core.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    _core_tests.shutil.copy2(core, destination)
    return root


_core_tests.build_plugin_repo = _build_plugin_repo_with_validator_core


def _post_w013_marketplace_contract(self):
    marketplace = _core_tests.load_json(_core_tests.MARKETPLACE_PATH)
    self.assertEqual("agentic-change-audit", marketplace["name"])
    self.assertEqual(
        POST_W013_DISPLAY_NAME,
        marketplace["interface"]["displayName"],
    )
    self.assertEqual(1, len(marketplace["plugins"]))

    entry = marketplace["plugins"][0]
    self.assertEqual("agentic-change-audit", entry["name"])
    self.assertEqual("local", entry["source"]["source"])
    self.assertEqual("./plugins/agentic-change-audit", entry["source"]["path"])
    self.assertEqual("AVAILABLE", entry["policy"]["installation"])
    self.assertEqual("ON_INSTALL", entry["policy"]["authentication"])
    self.assertEqual("Productivity", entry["category"])


_core_tests.MarketplaceTests.test_marketplace_contract = _post_w013_marketplace_contract

for _name, _value in vars(_core_tests).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


class PostW010PhaseCStateTests(_core_tests.unittest.TestCase):
    """Fail closed if the accepted Phase C record regresses to pending."""

    def test_phase_c_exception_requires_the_fixed_w010_binding(self):
        with _core_tests.tempfile.TemporaryDirectory() as temp:
            root = _core_tests.build_plugin_repo(temp)
            readme = root / _core_tests.validate_module.PLUGIN_RELATIVE / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8").replace(
                    "26af2687d0bac87089abd975b571ace5398a1a0b",
                    "0" * 40,
                ),
                encoding="utf-8",
            )

            result = _core_tests.run_validator(root)

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Phase C identity contradiction", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_reintroduced_phase_c_pending_claim_fails(self):
        with _core_tests.tempfile.TemporaryDirectory() as temp:
            root = _core_tests.build_plugin_repo(temp)
            readme = root / _core_tests.validate_module.PLUGIN_RELATIVE / "README.md"
            with readme.open("a", encoding="utf-8") as stream:
                stream.write("\nPhase C desktop verification is pending.\n")

            result = _core_tests.run_validator(root)

            self.assertNotEqual(0, result.returncode)
            self.assertIn(
                "must not claim Phase C pending after ACA-W010 acceptance",
                result.stderr,
            )
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)


class PostW013DisplayNameTests(_core_tests.unittest.TestCase):
    """Bind the user-facing Plugin and marketplace display names."""

    def test_manifest_and_marketplace_display_names_match_w013(self):
        manifest = _core_tests.load_json(_core_tests.MANIFEST_PATH)
        marketplace = _core_tests.load_json(_core_tests.MARKETPLACE_PATH)
        self.assertEqual(
            POST_W013_DISPLAY_NAME,
            manifest["interface"]["displayName"],
        )
        self.assertEqual(
            POST_W013_DISPLAY_NAME,
            marketplace["interface"]["displayName"],
        )
        self.assertEqual("agentic-change-audit", manifest["name"])
        self.assertEqual("0.1.0-dev.3", manifest["version"])
