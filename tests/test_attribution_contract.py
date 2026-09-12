from __future__ import annotations

"""Compatibility entry point for ACA-W013 attribution/version scope tests.

The complete pre-W013 body is preserved byte-for-byte in
``attribution_contract_core_tests.py``. Only the deliberately changed display
name and the new exact listing hash are rebound here.
"""

import importlib.util
import sys
from pathlib import Path


CORE_TEST_PATH = Path(__file__).with_name("attribution_contract_core_tests.py")
CORE_TEST_MODULE_NAME = "_aca_attribution_contract_core_tests"
POST_W013_DISPLAY_NAME = "ACA - Agentic Change Audit"
POST_W013_LISTING_SHA256 = "50671f8b923fc07dee0aff267d4b7d8df499a12a0154ad2edb33c7a74ba71624"


def _load_core_tests():
    spec = importlib.util.spec_from_file_location(CORE_TEST_MODULE_NAME, CORE_TEST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load preserved attribution tests: {CORE_TEST_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[CORE_TEST_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(CORE_TEST_MODULE_NAME, None)
        raise
    return module


_core_tests = _load_core_tests()
_core_tests.PROHIBITED_SUBMISSION_IDENTITY_FILE_SHA256 = dict(
    _core_tests.PROHIBITED_SUBMISSION_IDENTITY_FILE_SHA256
)
_core_tests.PROHIBITED_SUBMISSION_IDENTITY_FILE_SHA256[
    "submission/codex-plugin/listing.json"
] = POST_W013_LISTING_SHA256


def _version_scope_06_w013(self):
    marketplace = _core_tests.json.loads(
        (_core_tests.ROOT / ".agents/plugins/marketplace.json").read_text(
            encoding="utf-8"
        )
    )
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

    for relative, expected_sha256 in (
        _core_tests.PROHIBITED_SUBMISSION_IDENTITY_FILE_SHA256.items()
    ):
        self.assertEqual(
            expected_sha256,
            _core_tests.sha256((_core_tests.ROOT / relative).read_bytes()),
            relative,
        )


_core_tests.VersionAndScopeContractTests.test_version_scope_06_marketplace_semantics_and_submission_files_match_base = (
    _version_scope_06_w013
)

for _name, _value in vars(_core_tests).items():
    if not _name.startswith("__"):
        globals()[_name] = _value
