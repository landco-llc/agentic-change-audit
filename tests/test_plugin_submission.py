from __future__ import annotations

"""Compatibility test entry point for the post-W010 submission state.

The prior test body is preserved byte-for-byte in
``plugin_submission_core_tests.py``. Only assertions whose purpose was to keep
Phase C in a pending state are rebound to the accepted ACA-W010 completion
marker. All other regression tests remain unchanged, and explicit post-W010
regressions are added below.
"""

import importlib.util
import sys
from pathlib import Path


CORE_TEST_PATH = Path(__file__).with_name("plugin_submission_core_tests.py")
CORE_TEST_MODULE_NAME = "_aca_plugin_submission_core_tests"


def _load_core_tests():
    spec = importlib.util.spec_from_file_location(CORE_TEST_MODULE_NAME, CORE_TEST_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load preserved submission tests: {CORE_TEST_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[CORE_TEST_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(CORE_TEST_MODULE_NAME, None)
        raise
    return module


_core_tests = _load_core_tests()
_marker = _core_tests.submission_module.POST_W010_PHASE_C_MARKER
_plugin_readme = _core_tests.submission_module.PLUGIN_README_RELATIVE


def _post_w010_plugin_readme_boundary_removal_fails(self):
    with _core_tests.tempfile.TemporaryDirectory() as temp:
        root = _core_tests.build_repo(temp)
        _core_tests.remove_text(root, _plugin_readme, _marker + ".")
        self.assert_rejected(_core_tests.run_validator(root), "must state the boundary")


# Patch only test fixtures that explicitly encoded the superseded pending state.
for _value in vars(_core_tests).values():
    if not isinstance(_value, type):
        continue

    if hasattr(_value, "test_plugin_readme_boundary_removal_fails"):
        setattr(
            _value,
            "test_plugin_readme_boundary_removal_fails",
            _post_w010_plugin_readme_boundary_removal_fails,
        )

    _safe_boundaries = getattr(_value, "SAFE_BOUNDARIES", None)
    if isinstance(_safe_boundaries, dict) and _plugin_readme in _safe_boundaries:
        _updated = []
        for _boundary in _safe_boundaries[_plugin_readme]:
            if _boundary == "Phase C desktop evidence is pending.":
                _updated.append(_marker + ".")
            else:
                _updated.append(_boundary)
        _copy = dict(_safe_boundaries)
        _copy[_plugin_readme] = tuple(_updated)
        setattr(_value, "SAFE_BOUNDARIES", _copy)


# Unittest discovery can discover the preserved TestCase classes through these
# bindings; their methods still execute the original core test body except for
# the two Phase C fixtures patched above.
for _name, _value in vars(_core_tests).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


class PostW010PhaseCStateTests(_core_tests.RepoInvariantTestCase):
    """Fail closed if the accepted Phase C state regresses to pending."""

    def test_post_w010_current_surfaces_use_completion_marker(self):
        for relative in (
            _core_tests.submission_module.PLUGIN_README_RELATIVE,
            _core_tests.submission_module.SUBMISSION_README_RELATIVE,
            _core_tests.submission_module.RELEASE_NOTES_RELATIVE,
        ):
            text = (_core_tests.ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(_marker, text, relative)
            self.assertNotIn("Phase C desktop evidence is pending", text, relative)
            self.assertNotIn("Phase C desktop evidence remains pending", text, relative)

    def test_reintroduced_phase_c_pending_claim_fails(self):
        with _core_tests.tempfile.TemporaryDirectory() as temp:
            root = _core_tests.build_repo(temp)
            _core_tests.append_text(
                root,
                _plugin_readme,
                "\nPhase C desktop verification is pending.\n",
            )
            self.assert_rejected(
                _core_tests.run_validator(root),
                "must not claim Phase C pending after ACA-W010 acceptance",
            )

    def test_historic_phase_c_acceptance_does_not_allow_submission_claim(self):
        historic_fact = (
            "ACA-W010 desktop verification was completed and Human accepted "
            "for fixed binding 26af2687d0bac87089abd975b571ace5398a1a0b, "
            "Plugin 0.1.0-dev.3, and package SHA-256 "
            "af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57"
        )
        claims = (
            "the Plugin has been submitted to OpenAI",
            "the Plugin is approved and publicly listed",
            "the Plugin is published, released, and available",
            "publisher identity verification is complete",
            "the Apps Management portal has a saved draft",
            "the policy attestation is complete",
        )
        for claim in claims:
            with self.subTest(claim=claim), _core_tests.tempfile.TemporaryDirectory() as temp:
                root = _core_tests.build_repo(temp)
                _core_tests.append_text(
                    root,
                    _plugin_readme,
                    f"\n{historic_fact}; {claim}.\n",
                )

                result = _core_tests.run_validator(root)

                self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertNotIn("Plugin submission validation: PASS", result.stdout)
