from __future__ import annotations

"""Compatibility entry point for ACA-W013 display-name reconciliation.

The complete pre-W013 regression corpus is preserved byte-for-byte in
``marketplace_identity_core_tests.py``. Only tests whose fixtures encode the
previous canonical display name are rebound here.
"""

import importlib.util
import sys
from pathlib import Path


CORE_TEST_PATH = Path(__file__).with_name("marketplace_identity_core_tests.py")
CORE_TEST_MODULE_NAME = "_aca_marketplace_identity_core_tests"
POST_W013_DISPLAY_NAME = "ACA - Agentic Change Audit"


def _load_core_tests():
    spec = importlib.util.spec_from_file_location(CORE_TEST_MODULE_NAME, CORE_TEST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load preserved marketplace tests: {CORE_TEST_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[CORE_TEST_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(CORE_TEST_MODULE_NAME, None)
        raise
    return module


_core_tests = _load_core_tests()


def _marketplace_01_exact_w013_identity_is_accepted(self):
    self.assert_accepted(
        "plugin",
        _core_tests.json_assertion(
            _core_tests.MARKETPLACE,
            ("interface", "displayName"),
            POST_W013_DISPLAY_NAME,
        ),
    )


def _duplicate_02_w013(self):
    before = f'    "displayName": "{POST_W013_DISPLAY_NAME}"'.encode()
    self.assert_rejected_with_family(
        "plugin",
        _core_tests.replace_bytes(
            _core_tests.MARKETPLACE,
            before,
            before + b",\n" + before,
        ),
        "Duplicate JSON key",
    )


def _duplicate_09_w013(self):
    before = f'  "pluginName": "{POST_W013_DISPLAY_NAME}",'.encode()
    self.assert_rejected_with_family(
        "submission",
        _core_tests.replace_bytes(
            "submission/codex-plugin/listing.json",
            before,
            b'  "pluginName": "Other",\n' + before,
        ),
        "Duplicate JSON key",
    )


def _prior_a32_w013(self):
    before = f'    "displayName": "{POST_W013_DISPLAY_NAME}"'.encode()
    self.assert_rejected_with_family(
        "plugin",
        _core_tests.replace_bytes(
            _core_tests.MARKETPLACE,
            before,
            b'    "displayName": "L&Co.LLC Fresh Duplicate A32",\n' + before,
        ),
        "Duplicate JSON key",
    )


def _prior_b31_w013(self):
    before = f'    "displayName": "{POST_W013_DISPLAY_NAME}",'.encode()
    self.assert_rejected_with_family(
        "plugin",
        _core_tests.replace_bytes(
            _core_tests.MANIFEST,
            before,
            b'    "displayName": "L&Co.LLC Fresh B31",\n' + before,
        ),
        "Duplicate JSON key",
    )


_core_tests.MarketplaceExactIdentityTests.test_marketplace_01_exact_neutral_identity_is_accepted = (
    _marketplace_01_exact_w013_identity_is_accepted
)
_core_tests.AdditionalDuplicateJSONKeyRegressionTests.test_duplicate_02 = _duplicate_02_w013
_core_tests.AdditionalDuplicateJSONKeyRegressionTests.test_duplicate_09 = _duplicate_09_w013
_core_tests.ExactPriorFalsePassRegressionTests.test_prior_a32 = _prior_a32_w013
_core_tests.ExactPriorFalsePassRegressionTests.test_prior_b31 = _prior_b31_w013

for _name, _value in vars(_core_tests).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


class PostW013DisplayNameRegressionTests(_core_tests.IdentityPolicyTestCase):
    def test_w013_manifest_marketplace_and_listing_are_aligned(self):
        manifest = _core_tests.json.loads(
            (_core_tests.ROOT / _core_tests.MANIFEST).read_text(encoding="utf-8")
        )
        marketplace = _core_tests.json.loads(
            (_core_tests.ROOT / _core_tests.MARKETPLACE).read_text(encoding="utf-8")
        )
        listing = _core_tests.json.loads(
            (_core_tests.ROOT / "submission/codex-plugin/listing.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(POST_W013_DISPLAY_NAME, manifest["interface"]["displayName"])
        self.assertEqual(POST_W013_DISPLAY_NAME, marketplace["interface"]["displayName"])
        self.assertEqual(POST_W013_DISPLAY_NAME, listing["pluginName"])
        self.assertEqual("agentic-change-audit", manifest["name"])
        self.assertEqual("agentic-change-audit", marketplace["name"])
