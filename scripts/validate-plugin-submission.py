#!/usr/bin/env python3
"""Post-W010 entry point for the Codex Plugin submission validator.

The validated implementation body is preserved byte-for-byte in
``validate-plugin-submission-core.py``. This adapter changes only the Phase C
current-state contract after the accepted ACA-W010 desktop verification:
current public surfaces must now record that Phase C is complete and accepted,
and must reject reintroduction of a current "pending" Phase C claim.

All other listing, privacy, support, capability, human-prerequisite, secret,
path, version, and portal-state checks remain owned by the preserved core.
This remains a bounded validator, not a general natural-language theorem prover.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


CORE_PATH = Path(__file__).with_name("validate-plugin-submission-core.py")
CORE_MODULE_NAME = "_aca_validate_plugin_submission_core"
POST_W010_PHASE_C_MARKER = "Phase C desktop verification is complete and accepted"


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

# Replace only the three Phase C current-state markers that existed before
# ACA-W010. The surrounding validator contract remains unchanged.
_phase_c_replacements = {
    "Phase C desktop evidence remains pending": POST_W010_PHASE_C_MARKER,
    "Phase C desktop evidence is pending": POST_W010_PHASE_C_MARKER,
}

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
    relative: tuple(_phase_c_replacements.get(marker, marker) for marker in markers)
    for relative, markers in _core.CANONICAL_STATUS_MARKERS.items()
}

# The pre-W010 validator rejected any Phase C completion claim. Remove only that
# obsolete rule, then add the inverse fail-closed rule: current public status may
# not regress to Phase C pending/outstanding after the accepted W010 result.
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

# Re-export the preserved validator API. Existing tests and callers import this
# path, while function globals continue to resolve against the patched core.
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
