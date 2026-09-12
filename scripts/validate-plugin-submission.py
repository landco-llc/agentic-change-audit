#!/usr/bin/env python3
"""Post-W010/W013 entry point for the Codex Plugin submission validator.

The validated implementation body is preserved byte-for-byte in
``validate-plugin-submission-core.py``. This adapter retains the accepted
ACA-W010 Phase C contract and rebinds only the Human-approved ACA-W013
user-facing listing name and its canonical repository-status markers.

This adapter is not a general natural-language semantic layer. All other
listing, privacy, support, capability, human-prerequisite, secret, path,
version, and portal-state checks remain owned by the preserved core.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


CORE_PATH = Path(__file__).with_name("validate-plugin-submission-core.py")
CORE_MODULE_NAME = "_aca_validate_plugin_submission_core"
POST_W010_PHASE_C_MARKER = "Phase C desktop verification is complete and accepted"
POST_W013_DISPLAY_NAME = "ACA - Agentic Change Audit"


def _load_core():
    spec = importlib.util.spec_from_file_location(CORE_MODULE_NAME, CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load preserved validator core: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[CORE_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(CORE_MODULE_NAME, None)
        raise
    return module


_core = _load_core()

# ACA-W013 changes only the public Plugin/listing display name.
_core.EXPECTED_PLUGIN_NAME = POST_W013_DISPLAY_NAME

_phase_c_replacements = {
    "Phase C desktop evidence remains pending": POST_W010_PHASE_C_MARKER,
    "Phase C desktop evidence is pending": POST_W010_PHASE_C_MARKER,
}

_canonical_status_replacements = {
    _core.SUBMISSION_README_RELATIVE: {
        "Marketplace identity: neutral `Agentic Change Audit marketplace`": (
            POST_W013_DISPLAY_NAME
        ),
        "Earlier desktop evidence is historical, superseded, and non-transferable": (
            "That result is immutable historical evidence for its exact candidate."
        ),
        "Translation parity is not a machine validation gate": (
            "English is the sole canonical language for specifications, machine fields, and\n"
            "exact tokens."
        ),
    },
    _core.RELEASE_NOTES_RELATIVE: {
        "historical, superseded, and non-transferable": (
            "candidate-bound, and non-transferable to the W013 final candidate."
        ),
    },
}


def _rebind_status_marker(relative: str, marker: str) -> str:
    marker = _phase_c_replacements.get(marker, marker)
    return _canonical_status_replacements.get(relative, {}).get(marker, marker)


_plugin_boundaries = []
for _label, _wordings in _core.PLUGIN_README_REQUIRED_BOUNDARIES[
    _core.PLUGIN_README_RELATIVE
]:
    _new_label = _phase_c_replacements.get(_label, _label)
    _new_wordings = tuple(_phase_c_replacements.get(item, item) for item in _wordings)
    _plugin_boundaries.append((_new_label, _new_wordings))
_core.PLUGIN_README_REQUIRED_BOUNDARIES = dict(_core.PLUGIN_README_REQUIRED_BOUNDARIES)
_core.PLUGIN_README_REQUIRED_BOUNDARIES[_core.PLUGIN_README_RELATIVE] = tuple(
    _plugin_boundaries
)

_core.CANONICAL_STATUS_MARKERS = {
    relative: tuple(_rebind_status_marker(relative, marker) for marker in markers)
    for relative, markers in _core.CANONICAL_STATUS_MARKERS.items()
}

_core.FORBIDDEN_CURRENT_STATUS_PATTERNS = tuple(
    item
    for item in _core.FORBIDDEN_CURRENT_STATUS_PATTERNS
    if not (
        isinstance(item, tuple)
        and len(item) == 2
        and item[1] == "must keep Phase C pending"
    )
) + (
    (
        re.compile(
            r"Phase\s+C\s+desktop\s+(?:evidence|verification).{0,48}"
            r"\b(?:pending|outstanding)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "must not claim Phase C pending after ACA-W010 acceptance",
    ),
)

for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def cli() -> int:
    """Fail closed on unexpected defects without exposing runtime details."""
    try:
        return main()
    except Exception:
        print("ERROR: Unexpected Plugin submission validator failure.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
