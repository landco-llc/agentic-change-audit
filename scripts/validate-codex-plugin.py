#!/usr/bin/env python3
"""Post-W010/W013 entry point for the Codex Plugin validator.

The validated implementation body is preserved byte-for-byte in
``validate-codex-plugin-core.py``. This adapter keeps the accepted ACA-W010
Phase C evidence contract and rebinds only the Human-approved ACA-W013
user-facing display name.

All manifest, Skill, capability, identity, and fail-closed submission controls
remain owned by the preserved core.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


CORE_PATH = Path(__file__).with_name("validate-codex-plugin-core.py")
CORE_MODULE_NAME = "_aca_validate_codex_plugin_core"
POST_W010_PHASE_C_MARKER = "Phase C desktop verification is complete and accepted"
POST_W013_DISPLAY_NAME = "ACA - Agentic Change Audit"
POST_W010_ALLOWED_PHASE_C_CLAUSES = frozenset(
    {
        POST_W010_PHASE_C_MARKER,
        "ACA-W010 verified marketplace discovery, installation, explicit "
        "invocation, and Git working-tree non-mutation for the fixed "
        "pre-reconciliation candidate at 26af2687d0bac87089abd975b571ace5398a1a0b, "
        "Plugin 0.1.0-dev.3, and package SHA-256 "
        "af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57",
        "ACA-W010 completed Phase C for its fixed source identity",
    }
)
POST_W010_FIXED_BINDING = (
    "26af2687d0bac87089abd975b571ace5398a1a0b",
    "Plugin `0.1.0-dev.3`",
    "af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57",
)
POST_W010_PHASE_C_PENDING_PATTERN = re.compile(
    r"Phase\s+C\s+desktop\s+(?:evidence|verification).{0,48}"
    r"\b(?:pending|outstanding)\b",
    re.IGNORECASE | re.DOTALL,
)


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

# ACA-W013 changes only user-facing display identity. Technical slug, Skill
# name, version, legal identity, capabilities, and policy boundaries are fixed.
_core.EXPECTED_DISPLAY_NAME = POST_W013_DISPLAY_NAME
_core.EXPECTED_MARKETPLACE_DISPLAY_NAME = POST_W013_DISPLAY_NAME

_core.REQUIRED_README_MARKERS = tuple(
    POST_W010_PHASE_C_MARKER
    if marker == "Phase C desktop evidence is pending"
    else marker
    for marker in _core.REQUIRED_README_MARKERS
)
_core_validate_readmes = _core.validate_readmes


def _is_allowed_phase_c_error(error: str, has_fixed_binding: bool) -> bool:
    """Allow only the literal clauses that record the fixed W010 result."""
    return has_fixed_binding and error.startswith(
        "Plugin README Phase C identity contradiction:"
    ) and any(
        error.endswith(f"{clause!r}.")
        for clause in POST_W010_ALLOWED_PHASE_C_CLAUSES
    )


def validate_readmes(root: Path, errors: list[str]) -> None:
    start = len(errors)
    _core_validate_readmes(root, errors)
    plugin_readme = root / _core.PLUGIN_RELATIVE / "README.md"
    has_fixed_binding = plugin_readme.is_file() and all(
        value in plugin_readme.read_text(encoding="utf-8")
        for value in POST_W010_FIXED_BINDING
    )
    errors[start:] = [
        error
        for error in errors[start:]
        if not _is_allowed_phase_c_error(error, has_fixed_binding)
    ]

    for name in _core.README_NAMES:
        candidate = root / _core.PLUGIN_RELATIVE / name
        if not candidate.is_file():
            continue
        for clause in _core.readme_claim_clauses(candidate.read_text(encoding="utf-8")):
            if POST_W010_PHASE_C_PENDING_PATTERN.search(clause.text):
                errors.append(
                    "Plugin README must not claim Phase C pending after ACA-W010 "
                    f"acceptance: {name}: {clause.text!r}."
                )


_core.validate_readmes = validate_readmes

for _name, _value in vars(_core).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


if __name__ == "__main__":
    # Preserve the pre-W012 CLI facade.
    raise SystemExit(_core.cli())
