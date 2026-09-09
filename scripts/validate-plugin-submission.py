#!/usr/bin/env python3
"""Validate the Codex Plugin submission package without submitting anything.

The package is preparation material. This validator enforces that it stays
that way: exact listing contract, no overclaimed status, no leaked local
path, address, or secret, and an unchanged skills-only Plugin runtime.

This module itself uses the standard library only and makes no network
request. It does shell out to scripts/validate-codex-plugin.py, which needs
the repository's existing validation dependencies from
requirements-validation.txt.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

SUPPORT_RELATIVE = "SUPPORT.md"
PRIVACY_RELATIVE = "PRIVACY.md"
SUBMISSION_RELATIVE = "submission/codex-plugin"
LISTING_RELATIVE = f"{SUBMISSION_RELATIVE}/listing.json"
STARTER_PROMPTS_RELATIVE = f"{SUBMISSION_RELATIVE}/starter-prompts.json"
TEST_CASES_RELATIVE = f"{SUBMISSION_RELATIVE}/test-cases.json"
AVAILABILITY_RELATIVE = f"{SUBMISSION_RELATIVE}/availability.json"
RELEASE_NOTES_RELATIVE = f"{SUBMISSION_RELATIVE}/release-notes.md"
HUMAN_PREREQUISITES_RELATIVE = f"{SUBMISSION_RELATIVE}/human-prerequisites.md"
VISUAL_ASSETS_RELATIVE = f"{SUBMISSION_RELATIVE}/visual-assets.md"
SUBMISSION_README_RELATIVE = f"{SUBMISSION_RELATIVE}/README.md"

PLUGIN_RELATIVE = "plugins/agentic-change-audit"
MANIFEST_RELATIVE = f"{PLUGIN_RELATIVE}/.codex-plugin/plugin.json"
PLUGIN_VALIDATOR_RELATIVE = "scripts/validate-codex-plugin.py"

PLUGIN_README_RELATIVE = f"{PLUGIN_RELATIVE}/README.md"

# Files the submission package must provide.
REQUIRED_FILES = (
    SUPPORT_RELATIVE,
    PRIVACY_RELATIVE,
    SUBMISSION_README_RELATIVE,
    LISTING_RELATIVE,
    STARTER_PROMPTS_RELATIVE,
    TEST_CASES_RELATIVE,
    AVAILABILITY_RELATIVE,
    RELEASE_NOTES_RELATIVE,
    HUMAN_PREREQUISITES_RELATIVE,
    VISUAL_ASSETS_RELATIVE,
)

# Plugin-facing public content. These are not submission deliverables, but a
# reader reaches them from the listing, so they carry the same claim and
# leak boundaries and must exist.
PLUGIN_README_FILES = (
    PLUGIN_README_RELATIVE,
)

# Files scanned for local paths, addresses, and secret-like values.
SCANNED_FILES = REQUIRED_FILES + PLUGIN_README_FILES

# Canonical English prose surfaces carrying marketplace and portal-state facts.
CLAIM_SCAN_FILES = (
    RELEASE_NOTES_RELATIVE,
    SUBMISSION_README_RELATIVE,
) + PLUGIN_README_FILES
PORTAL_STATE_SCAN_FILES = (SUBMISSION_README_RELATIVE,) + PLUGIN_README_FILES

EXPECTED_LISTING_KEYS = {
    "submissionType",
    "pluginName",
    "publisher",
    "shortDescription",
    "longDescription",
    "category",
    "websiteUrl",
    "supportUrl",
    "privacyUrl",
    "termsUrl",
    "developerIdentity",
    "logoStatus",
    "skills",
    "releaseStatus",
    "publicDirectoryStatus",
}
EXPECTED_DEVELOPER_IDENTITY_KEYS = {"type", "name", "verificationStatus"}
EXPECTED_SKILL_KEYS = {"name", "path"}

EXPECTED_SUBMISSION_TYPE = "skills-only"
EXPECTED_PLUGIN_NAME = "Agentic Change Audit"
EXPECTED_PUBLISHER = "L&Co.LLC"
EXPECTED_SHORT_DESCRIPTION = "Audit software changes with evidence before merge or release."
EXPECTED_LONG_DESCRIPTION = (
    "Agentic Change Audit reviews a fixed software change, records the checks "
    "and evidence actually available, identifies findings and required human "
    "checks, and returns one structured Verdict before merge, release, or "
    "deployment. It is evidence-first, agent-neutral, and read-only by default."
)
EXPECTED_CATEGORY = "Productivity"
EXPECTED_WEBSITE_URL = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_SUPPORT_URL = "https://github.com/landco-llc/agentic-change-audit/issues"
EXPECTED_PRIVACY_URL = (
    "https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md"
)
EXPECTED_TERMS_URL = "https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE"
EXPECTED_DEVELOPER_TYPE = "business"
EXPECTED_DEVELOPER_NAME = "L&Co.LLC"
EXPECTED_VERIFICATION_STATUS = "PENDING HUMAN CHECK"
EXPECTED_LOGO_STATUS = "PENDING APPROVED ASSET"
EXPECTED_SKILL_NAME = "agentic-change-audit"
EXPECTED_SKILL_PATH = "plugins/agentic-change-audit/skills/agentic-change-audit"
EXPECTED_RELEASE_STATUS = "draft-materials-only"
EXPECTED_PUBLIC_DIRECTORY_STATUS = "not-submitted"

URL_LISTING_KEYS = ("websiteUrl", "supportUrl", "privacyUrl", "termsUrl")

EXPECTED_AVAILABILITY_STATUS = "PENDING HUMAN DECISION"
EXPECTED_LANGUAGE_SUPPORT = [
    "Conversation language for runtime narrative",
    "English for canonical machine tokens",
]

STARTER_PROMPT_FIELDS = ("id", "title", "prompt", "expectedMode", "expectedBoundary")
TEST_CASE_FIELDS = (
    "id",
    "type",
    "title",
    "input",
    "preconditions",
    "expectedSelection",
    "expectedBehavior",
    "forbiddenBehavior",
    "acceptanceCriteria",
)
EXPECTED_STARTER_PROMPT_COUNT = 5
EXPECTED_TEST_CASE_COUNT = 8
EXPECTED_POSITIVE_COUNT = 5
EXPECTED_NEGATIVE_COUNT = 3
VALID_TEST_TYPES = ("positive", "negative")
VALID_MODES = ("FULL", "FOCUSED_REAUDIT", "RELEASE", "DOCS_ONLY")

EXPECTED_MANIFEST_VERSION = "0.1.0-dev.3"
EXPECTED_SUBMISSION_RELEASE_NOTES_VERSION = "0.1.0-dev.3"
EXPECTED_MANIFEST_CAPABILITIES = ["Read"]
FORBIDDEN_MANIFEST_KEYS = ("mcpServers", "apps", "hooks")

HUMAN_PREREQUISITE_ITEMS = (
    "OpenAI Platform organization selected",
    "Apps Management Write permission",
    "L&Co.LLC business identity verification",
    "Public website review",
    "Support URL review",
    "Privacy URL review",
    "Terms URL review",
    "Availability decision",
    "Logo approval",
    "Final Skill ZIP upload",
    "Submission portal draft creation",
    "Policy attestations",
    "Final submit decision",
)
PENDING_HUMAN_CHECK = "PENDING HUMAN CHECK"

# Each entry is one boundary: a label plus the accepted wordings. At least
# one wording must survive, so a single deletion cannot be masked by the
# other boundaries still being present.
PRIVACY_REQUIRED_BOUNDARIES = (
    ("skills-only Plugin", ("skills-only Plugin",)),
    ("no MCP server", ("no MCP server",)),
    ("no ChatGPT app", ("no ChatGPT app",)),
    ("no connector", ("no connector",)),
    ("no external service", ("no external service",)),
    ("no telemetry", ("no telemetry",)),
    ("no analytics", ("no analytics",)),
    ("no authentication flow", ("no authentication flow",)),
    ("no network client", ("no network client",)),
    (
        "the Plugin itself does not collect, transmit, sell, or share user data",
        ("does not collect, transmit, sell, or share user data",),
    ),
    (
        "L&Co.LLC does not receive task contents merely because the Plugin is installed",
        ("does not receive your task contents merely because the Plugin is installed",),
    ),
    (
        "the Plugin reads only data made available to the active task under the "
        "user's environment and permissions",
        ("reads only the data that is already made available to the active",),
    ),
    (
        "host-product and configured-tool data remains governed by those products "
        "and tools",
        ("remains governed by the host product and by the tools you have configured",),
    ),
    (
        "this policy does not change or override the host product's terms",
        ("does not change or override those terms",),
    ),
    (
        "users must not paste secrets unnecessarily",
        ("unnecessarily",),
    ),
    (
        "audit outputs may include paths, SHAs, branches, filenames, evidence, "
        "and findings",
        ("repository paths, commit SHAs, branch names, filenames",),
    ),
    (
        "users control where outputs are stored or shared",
        ("You control where those outputs are stored, pasted, or shared",),
    ),
    (
        "a future stateful or hosted component requires a new policy and review",
        ("requires a new privacy policy and a new review",),
    ),
)

SUPPORT_REQUIRED_BOUNDARIES = (
    ("the only support channel is GitHub Issues", ("only support channel", "GitHub Issues")),
    (
        "the public support URL",
        ("https://github.com/landco-llc/agentic-change-audit/issues",),
    ),
    (
        "secrets must not be published in a public report",
        ("Do not publish secrets, credentials, tokens",),
    ),
    ("support is best effort", ("best effort",)),
    ("no guaranteed response time", ("no guaranteed response time",)),
    ("no guarantee of a reply", ("no guarantee of a reply",)),
    (
        "no free implementation or integration work",
        ("free implementation work or integration work",),
    ),
    (
        "no audit, security certification, or compliance certification service",
        ("audit services, security certification, or compliance certification",),
    ),
    ("no legal advice", ("legal advice",)),
    (
        "no production support, incident response, or uptime commitment",
        ("production support, incident response, or uptime commitments",),
    ),
    (
        "no commercial or organization-specific support",
        ("commercial or organization-specific support",),
    ),
    (
        "paid professional services are separate from the open-source license",
        ("They are not part of this repository's license",),
    ),
)

SUPPORT_CHANNEL_HEADING = "## Support channel"
CANONICAL_SUPPORT_URL = "https://github.com/landco-llc/agentic-change-audit/issues"

# Bounded English phrases that explicitly assign a support/contact channel
# role. Localized prose is distribution content, not a machine-semantic lane.
# A URL path such as /help or /support is never proof by itself: the assertion
# must appear in the visible label or adjacent English text.
SUPPORT_ASSERTION_PATTERNS = (
    re.compile(r"\bofficial\s+(?:customer\s+)?support\b", re.IGNORECASE),
    re.compile(r"\bsupport\s+is\s+(?:also\s+)?available\s+(?:at|via|through|from)\b", re.IGNORECASE),
    re.compile(r"\bsupport\s+(?:channel|portal|contact)\b", re.IGNORECASE),
    re.compile(r"\bcontact\s+support\b", re.IGNORECASE),
    re.compile(r"\bhelp\s*desk\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+support\s+(?:hotline|line|desk|team|portal)\b", re.IGNORECASE),
)
URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"'`]+")

# Explanatory wording: a line qualified as documentation, reference, or
# terminology material is describing support concepts, not assigning the URL
# a channel role.
SUPPORT_DOC_QUALIFIER_PATTERN = re.compile(
    r"\b(?:documentation|reference|background|terminology|vocabulary|glossary"
    r"|implementation\s+notes|explains|discusses|compares)\b",
    re.IGNORECASE,
)


def decode_label_punctuation(label: str) -> str:
    """Decode backslash escapes in a label.

    Escaped brackets become separators rather than literal characters, so
    "official \\[support\\]" still classifies as an official-support
    assertion instead of hiding the keyword behind punctuation. Unicode
    letters are never removed.
    """
    decoded = re.sub(r"\\([\[\]])", " ", label)
    return MD_BACKSLASH_ESCAPE_PATTERN.sub(lambda m: m.group(1), decoded)


def normalize_reference_label(label: str) -> str:
    return " ".join(decode_label_punctuation(label).split()).lower()


def parse_reference_definitions(text: str) -> dict[str, str]:
    """Collect reference definitions, honouring CommonMark's first-wins rule.

    Bare and angle-bracket destinations are both accepted; an optional title
    is metadata and never becomes visible support prose.
    """
    definitions: dict[str, str] = {}
    for line in text.splitlines():
        match = MD_DEFINITION_LINE_PATTERN.match(line)
        if match:
            destination = match.group(2) if match.group(2) is not None else match.group(3)
            # setdefault: a later duplicate definition never overrides the
            # first, which is the one a CommonMark renderer resolves.
            definitions.setdefault(normalize_reference_label(match.group(1)), destination)
    return definitions


def support_line_targets(line: str, definitions: dict[str, str]) -> tuple[str, list[str]]:
    """Resolve a line to its visible text and every URL it points at.

    Covers raw URLs, inline links, full, collapsed, and shortcut reference
    links, and images. Image alt text stays visible and the image
    destination is a target, because an image can present an alternative
    support destination just as a link can; for a linked image the outer
    destination is captured too. Each target is returned separately so a
    canonical URL on the line cannot hide an alternative.
    """
    targets: list[str] = []

    def record(destination: str | None) -> None:
        if destination and destination.startswith(("http://", "https://")):
            targets.append(destination)

    def take_inline(match: re.Match) -> str:
        record(match.group(2))
        return decode_label_punctuation(match.group(1))

    def take_reference(match: re.Match) -> str:
        label, reference = match.group(1), match.group(2)
        key = normalize_reference_label(reference) or normalize_reference_label(label)
        record(definitions.get(key))
        return decode_label_punctuation(label)

    def take_shortcut(match: re.Match) -> str:
        label = match.group(1)
        record(definitions.get(normalize_reference_label(label)))
        return decode_label_punctuation(label)

    # Images first, so a linked image reduces to a plain link whose outer
    # destination is then captured by the inline-link pass.
    work = MD_IMAGE_INLINE_PATTERN.sub(take_inline, line)
    work = MD_IMAGE_REFERENCE_PATTERN.sub(take_reference, work)
    work = MD_IMAGE_SHORTCUT_PATTERN.sub(take_shortcut, work)
    work = MD_INLINE_LINK_PATTERN.sub(take_inline, work)
    work = MD_REFERENCE_LINK_PATTERN.sub(take_reference, work)
    work = MD_SHORTCUT_LINK_PATTERN.sub(take_shortcut, work)
    for match in URL_PATTERN.finditer(work):
        targets.append(match.group(0))
    return work, targets

# Material equivalents each Plugin README must still state. Presence alone is
# not sufficient: the claim scan runs over the same files, so an appended
# availability claim still fails even with every phrase below intact.
PLUGIN_README_REQUIRED_BOUNDARIES = {
    PLUGIN_README_RELATIVE: (
        ("development preview", ("development preview",)),
        (
            "not submitted to or approved for the public Plugins Directory",
            ("has not been submitted to or approved for",),
        ),
        (
            "Phase C desktop evidence remains pending",
            ("Phase C desktop evidence is pending",),
        ),
        (
            "earlier desktop evidence is historical and non-transferable",
            ("historical, superseded, and non-transferable",),
        ),
        (
            "human prerequisites remain pending",
            ("human prerequisites remain pending",),
        ),
        (
            "English is the sole canonical machine language",
            ("English is the sole canonical language for machine semantics",),
        ),
    ),
}

# External portal state is not observable from this repository lane. These
# bounded patterns inspect only the canonical English submission surfaces;
# they are not a general natural-language or translation-equivalence oracle.
PORTAL_CONTEXT_PATTERNS = (
    re.compile(
        r"(?<![A-Za-z0-9_])(?:portal|"
        r"(?:submission|application|review|developer|application[-\s]+review)\s+"
        r"(?:portal|dashboard|console|interface|workspace|site|page|screen|system|queue)|"
        r"repository\s+of\s+applications)(?![A-Za-z0-9_])",
        re.IGNORECASE,
    ),
)

# Generic surfaces need a material application/submission/review object in the
# same segment. This keeps ordinary mentions of a system, page, or queue out of
# scope while still recognizing natural names such as "review queue".
PORTAL_GENERIC_SURFACE_PATTERNS = (
    re.compile(
        r"\b(?:dashboard|console|interface|workspace|site|page|screen|system|queue)\b",
        re.IGNORECASE,
    ),
)

PORTAL_STATE_OBJECT_PATTERNS = (
    re.compile(
        r"\b(?:drafts?|(?:saved|pending|existing|application|submission|review)\s+drafts?|"
        r"(?:pending|saved|returned|approved|completed|rejected)\s+"
        r"(?:(?:application|submission|review)\s+)?"
        r"(?:applications?|submissions?|items?|entr(?:y|ies)|records?|files?|forms?|"
        r"materials?|content|requests?|cases?)|(?:application|submission|submitted|uploaded)\s+"
        r"(?:content|data|materials?|files?|records?|entr(?:y|ies)|packets?|forms?|cases?|requests?)|"
        r"materials?|content|files?|records?|entr(?:y|ies)|packets?|forms?|cases?|requests?|nothing|"
        r"applications?(?=\s*(?:$|[.,;:!?)}\]]|\b(?:is|are|was|were|has|have|had|"
        r"exists?|remains?|remained|awaits?|awaited|awaiting)\b))|"
        r"submissions?(?=\s*(?:$|[.,;:!?)}\]]|\b(?:is|are|was|were|has|have|had|"
        r"exists?|remains?|remained|awaits?|awaited|awaiting)\b)))",
        re.IGNORECASE,
    ),
)

# English quantity pronouns are state objects only when they are attached to
# a material display/containment predicate. Portal context and discourse scope
# are still evaluated separately, so ordinary uses of "one" and "none" do not
# become portal assertions by themselves.
PORTAL_ANAPHORIC_STATE_OBJECT_PATTERN = re.compile(
    r"\b(?:another\s+(?:one|entry|item|draft|record|file)|"
    r"one\s+such\s+(?:entry|item|application|draft|record|file)|"
    r"one\s+(?:pending|saved|submitted|review)\s+"
    r"(?:entry|item|application|draft|record|file)|"
    r"one\s+(?:entry|item|draft|record|file)(?=\s*(?:$|[.,;:!?)}\]]|"
    r"\b(?:after|before|now|already|still|currently|here|there|today|yesterday)\b))|"
    r"one(?=\s*(?:$|[.,;:!?)}\]]|\b(?:after|before|now|already|still|currently|"
    r"here|there|today|yesterday)\b))|none)\b",
    re.IGNORECASE,
)
PORTAL_ANAPHORIC_MATERIAL_PREDICATE_PATTERN = re.compile(
    r"\b(?:holds?|contains?|shows?|display(?:s|ed|ing)?|stores?|"
    r"list(?:s|ed|ing)?|present(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)

# A generic UI noun is portal context only when its own clause names a strong
# application/submission/review object. In particular, an anaphoric quantity
# such as ``one`` cannot turn an ordinary dashboard, console, or site into a
# portal surface; it needs an explicitly qualified surface or bounded context
# inherited from a qualifying antecedent.
PORTAL_STRONG_CONTEXTUAL_OBJECT_PATTERN = re.compile(
    r"\b(?:drafts?|submitted\s+(?:content|materials?|files?)|"
    r"(?:pending|saved)\s+(?:applications?|submissions?|items?|entr(?:y|ies)|records?|"
    r"files?|forms?|materials?)|"
    r"applications?(?=\s*(?:$|[.,;:!?)}\]]|\b(?:is|are|was|were|has|have|had|"
    r"exists?|remains?|awaits?)\b))|"
    r"submissions?(?=\s*(?:$|[.,;:!?)}\]]|\b(?:is|are|was|were|has|have|had|"
    r"exists?|remains?|awaits?)\b))|review\s+queue)\b",
    re.IGNORECASE,
)

# A display predicate says that a surface exposes material. Remaining state
# predicates say that the material itself has or is in a state. Keeping these
# roles separate prevents words such as ``present`` from being treated as
# either globally safe or globally unsafe.
PORTAL_MATERIAL_DISPLAY_PREDICATE_PATTERNS = (
    re.compile(
        r"\b(?:has|have|had|holds?|held|holding|contains?|contained|containing|shows?|"
        r"showed|showing|display(?:s|ed|ing)?|stores?|stored|storing|"
        r"list(?:s|ed|ing)?|present(?:s|ed|ing)?|retains?|retained|retaining|"
        r"records?|recorded|recording|does\s+not\s+contain|do\s+not\s+contain)\b",
        re.IGNORECASE,
    ),
)

# In the canonical English submission-status files, draft objects carry their
# own application context even when a sentence omits the noun "portal".
PORTAL_IMPLICIT_CONTEXT_PATTERNS = (
    re.compile(r"\b(?:saved\s+|pending\s+|existing\s+)?drafts?\b", re.IGNORECASE),
)

# The portal/system itself is the state object for empty/present/absent
# assertions, so these do not require a separate draft/content noun.
PORTAL_SELF_STATE_PATTERNS = (
    re.compile(
        r"\b(?:portal|dashboard|console|interface|workspace|site|page|screen|system|queue)\s+"
        r"(?:is|are|was|were)\s+(?:not\s+)?(?:present|absent|empty)\b",
        re.IGNORECASE,
    ),
)

PORTAL_STATE_PREDICATE_PATTERNS = (
    re.compile(r"\bthere\s+(?:is|are)\s+(?:no\s+)?", re.IGNORECASE),
    re.compile(r"\b(?:exists?|existed|existing|does\s+not\s+exist)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:is|are|was|were)\s+(?:not\s+)?(?:present|absent|empty|pending|approved|"
        r"rejected|returned|complete|completed|processed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:has|have|had|holds?|held|holding|contains?|contained|containing|shows?|"
        r"showed|showing|display(?:s|ed|ing)?|stores?|stored|storing|"
        r"list(?:s|ed|ing)?|present(?:s|ed|ing)?|retains?|retained|retaining|"
        r"records?|recorded|recording|does\s+not\s+contain|do\s+not\s+contain)\s+"
        r"(?:no\s+|an?\s+|the\s+|any\s+)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:remains?|remained|remaining|retains?|retained|holds?|held|holding)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:has|have|had)\s+(?:not\s+|already\s+|still\s+)?been\s+"
        r"(?:saved|created|registered|recorded|filed|lodged|submitted|sent|uploaded|"
        r"transmitted|queued|enqueued|approved|rejected|returned|completed|processed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are|was|were)\s+(?:not\s+|already\s+|still\s+|currently\s+)?"
        r"(?:saved|created|registered|recorded|filed|lodged|submitted|sent|uploaded|"
        r"transmitted|queued|enqueued|approved|rejected|returned|completed|processed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:not\s+|already\s+|still\s+|currently\s+)?(?:saved|created|registered|"
        r"recorded|filed|lodged|submitted|sent|uploaded|transmitted|queued|enqueued|"
        r"approved|rejected|returned|completed|processed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:is|are|was|were)\s+(?:already\s+|currently\s+|not\s+)?"
        r"(?:under|being)\s+review(?:ed)?\b|\b(?:awaits?|awaited|awaiting|queued\s+for|"
        r"sent\s+for)\s+review\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:is|are|was|were)\s+(?:still\s+)?on\s+file\b", re.IGNORECASE),
    re.compile(r"\b(?:on\s+file|filed|lodged|sent\s+for\s+review)\b", re.IGNORECASE),
    re.compile(r"\b(?:not\s+)?pending\b", re.IGNORECASE),
)

# Discourse modes are segment-local. Structural segmentation runs first, so a
# safe outer sentence cannot license a later clause or nested bracketed claim.
class DiscourseMode(Enum):
    CURRENT_ASSERTION = auto()
    QUESTION_OR_VERIFICATION = auto()
    FUTURE_OR_HYPOTHETICAL = auto()
    DOCUMENTATION_OR_EXAMPLE = auto()
    REPOSITORY_EVIDENCE_BOUNDARY = auto()
    HUMAN_GATE = auto()


class SurfaceContext(Enum):
    NONE = auto()
    GENERIC_UI = auto()
    GOVERNED_PORTAL = auto()


class Actuality(Enum):
    CURRENT_ASSERTION = auto()
    NON_CURRENT_OR_NON_ASSERTIVE = auto()


class ObjectKind(Enum):
    NONE = auto()
    STRONG_MATERIAL_OBJECT = auto()
    BOUNDED_ANAPHORIC_OBJECT = auto()


class PredicateKind(Enum):
    NONE = auto()
    STATE = auto()
    MATERIAL_DISPLAY = auto()


@dataclass(frozen=True)
class PortalSemanticRoles:
    """Independently classified roles for one portal-state assertion span."""

    surface_context: SurfaceContext
    actuality: Actuality
    object_kind: ObjectKind
    predicate_kind: PredicateKind

    @property
    def is_current_material_portal_assertion(self) -> bool:
        return (
            self.surface_context is SurfaceContext.GOVERNED_PORTAL
            and self.actuality is Actuality.CURRENT_ASSERTION
            and self.object_kind
            in {
                ObjectKind.STRONG_MATERIAL_OBJECT,
                ObjectKind.BOUNDED_ANAPHORIC_OBJECT,
            }
            and self.predicate_kind
            in {PredicateKind.STATE, PredicateKind.MATERIAL_DISPLAY}
        )


@dataclass(frozen=True)
class AssertionSpan:
    """One predicate-bearing clause with its own attached discourse scope."""

    text: str
    start: int
    end: int
    predicate_kind: str
    discourse_scope: DiscourseMode
    structure_id: int = -1
    paragraph_id: int = 0
    sentence_id: int = 0
    parent_bracket_id: int | None = None
    nesting_depth: int = 0
    boundary_before: str = ""
    boundary_after: str = ""
    quoted_ranges: tuple[tuple[int, int], ...] = ()


@dataclass
class StructuredSpan:
    """Visible-source span retaining the relationships needed after splitting."""

    span_id: int
    text: str
    start: int
    end: int
    paragraph_id: int
    sentence_id: int
    parent_bracket_id: int | None
    nesting_depth: int
    boundary_before: str
    boundary_after: str
    quoted_ranges: tuple[tuple[int, int], ...]
    previous_sibling: int | None = None
    next_sibling: int | None = None


@dataclass(frozen=True)
class StructuredSpanGraph:
    spans: tuple[StructuredSpan, ...]
    bracket_antecedents: dict[int, int | None]
    bracket_parents: dict[int, int | None]
    continuation_antecedents: dict[int, int]


PORTAL_REPOSITORY_EVIDENCE_SAFE_PATTERNS = (
    re.compile(
        r"\bno\s+portal\s+action\s+is\s+performed\s+or\s+evidenced\s+by\s+this\s+repository\s+lane\b",
        re.IGNORECASE,
    ),
)
PORTAL_HUMAN_GATE_SAFE_PATTERNS = (
    re.compile(r"\bportal\s+state\s+remains\s+a\s+human\s+verification\s+gate\b", re.IGNORECASE),
    re.compile(r"\b(?:final\s+)?portal\s+state\s+must\s+be\s+checked\s+by\s+a\s+human\b", re.IGNORECASE),
    re.compile(r"\bhuman\s+(?:review|verification)\s+is\s+required\b", re.IGNORECASE),
)
PORTAL_EXPLANATORY_SEGMENT_PATTERNS = (
    re.compile(
        r"\b(?:documentation|document|schema|field|field\s+named|fixture|sample|example|"
        r"test\s+example|terminology|term|phrase|wording|quotes?|quoted|"
        r"defines?|explains?|describes?|hypothetical)\b",
        re.IGNORECASE,
    ),
)
PORTAL_FUTURE_SEGMENT_PATTERNS = (
    re.compile(
        r"\b(?:future|may|might|could|will|would|if|unless|suppose|assuming|"
        r"were\s+(?:the|an?|this|that)\s+[^.!?;]{0,60}\s+to\s+"
        r"(?:show|display|list|present|contain|hold|store|record|return|approve|complete|reject)|"
        r"should\s+[^.!?;]{0,80}\s+later|"
        r"in\s+a\s+hypothetical\s+scenario|for\s+example\s*,?\s*if|"
        r"when\s+a\s+human\s+later|after\s+(?:human\s+)?approval|"
        r"following\s+human\s+approval|hypothetical|conditional|counterfactual)\b",
        re.IGNORECASE,
    ),
)
PORTAL_QUESTION_VERIFICATION_PATTERNS = (
    re.compile(r"^(?:does|do|is|are|has|have|was|were|can|could)\b.*\?$", re.IGNORECASE),
    re.compile(r"\b(?:whether|if)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:must|needs?\s+to|required\s+to)\s+(?:determine|verify|check|confirm)\b|"
        r"\b(?:requires?|needs?)\s+confirmation\b|\bhuman\s+verification\s+is\s+required\b|"
        r"\bcannot\s+be\s+determined\s+from\s+this\s+repository\b|"
        r"\b(?:the\s+)?actual\s+state\s+is\s+unknown\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:(?:remains?|is|are)\s+(?:still\s+)?(?:unchecked|unverified|unconfirmed)|"
        r"(?:has|have)\s+not\s+been\s+(?:checked|verified)|"
        r"(?:is|are)\s+awaiting\s+human\s+verification|"
        r"still\s+requires?\s+human\s+review)\b",
        re.IGNORECASE,
    ),
)
PORTAL_CURRENT_STATE_CUE_PATTERNS = (
    re.compile(
        r"\b(?:already|currently|now|still|actually|exists?|remains?|remained|present|absent|"
        r"empty|has\s+no|contains?\s+no|does\s+not\s+contain|has\s+been|was|were|"
        r"under\s+review|being\s+reviewed|awaiting\s+review|queued\s+for\s+review|on\s+file)\b",
        re.IGNORECASE,
    ),
)
PORTAL_EXPLICIT_CURRENT_TIME_PATTERNS = (
    re.compile(r"\b(?:already|currently|now|actually)\b", re.IGNORECASE),
)

QUOTED_TEXT_PATTERNS = (
    re.compile(r'"[^"\n]*"'),
    re.compile(r"'[^'\n]*'"),
    re.compile(r"“[^”\n]*”"),
    re.compile(r"‘[^’\n]*’"),
)

# A private local path leaking into a public submission artifact.
LOCAL_PATH_PATTERNS = (
    re.compile(r"(?<![\w./])/Users/[A-Za-z0-9._-]+"),
    re.compile(r"(?<![\w./])/home/[A-Za-z0-9._-]+"),
    re.compile(r"(?<![\w./])/private/(?:tmp|var)/"),
    re.compile(r"(?<![\w./])/var/folders/"),
    re.compile(r"\b[A-Za-z]:\\\\?(?:Users|Documents)\b"),
    re.compile(r"\bfile:///"),
)

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ALLOWED_EMAIL_DOMAIN = "example.invalid"

SECRET_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
)

# --- Product and submission status claims -----------------------------------
#
# Negation is bound to the specific claim it negates. Explicitly negated
# status spans are masked out of the text first (replaced with spaces), and
# every status claim remaining anywhere afterwards fails. There is no
# sentence-, clause-, or window-level exemption: an unrelated negation cannot
# license a later claim, so "No submission has occurred — this Plugin is
# published." fails on the second span while "This Plugin is not published."
# is fully consumed by the negated-span mask.

# One coordinated status term inside an explicit English negation. The
# repetition groups let a single negation cover a coordinated list such as
# "not listed in, available from, or approved for" without consuming past
# the coordination into an independent clause.
_NEG_STATUS_TERM = (
    r"(?:submitted(?:\s+to)?|listed(?:\s+in)?|available(?:\s+(?:from|in|on))?"
    r"|approved(?:\s+for)?|published|released|stable|claimed"
    r"|(?:generally|publicly)\s+available"
    r"|a\s+(?:public|stable)\s+(?:release|version))"
)
_NEG_STATUS_COORD = (
    rf"{_NEG_STATUS_TERM}(?:\s*,\s*{_NEG_STATUS_TERM})*"
    rf"(?:\s*,?\s*(?:or|and|nor)\s+{_NEG_STATUS_TERM})*"
)

NEGATED_STATUS_PATTERNS = (
    # English: "is not published", "has not been submitted to, listed in, or
    # approved for", "not a public release".
    re.compile(
        rf"\b(?:is|are|was|were|has|have|had)\s+not\s+(?:yet\s+)?(?:been\s+)?"
        rf"{_NEG_STATUS_COORD}",
        re.IGNORECASE,
    ),
    re.compile(rf"\bnot\s+(?:yet\s+)?{_NEG_STATUS_COORD}", re.IGNORECASE),
    # "No submission has occurred", "no listing has been published",
    # "nothing has been submitted".
    re.compile(
        r"\b(?:no\s+[A-Za-z]+|nothing|none)\s+has\s+(?:yet\s+)?"
        r"(?:been\s+[A-Za-z]+|occurred)\b",
        re.IGNORECASE,
    ),
    # "Stable, approved, and published status are not claimed."
    re.compile(r"[\w,\s-]{0,60}\bstatus\s+(?:is|are)\s+not\s+claimed\b", re.IGNORECASE),
    re.compile(r"\bnever\s+(?:been\s+)?[A-Za-z]+\b", re.IGNORECASE),
)

# Positive status claims scanned over the masked text. These target the
# status of the Plugin itself, not benign wording such as "Public policy
# URLs are prepared." or policy files "published from this repository".
POSITIVE_STATUS_PATTERNS = (
    # English.
    re.compile(
        r"\b(?:is|are|was|were)\s+(?:now\s+|currently\s+)?published\b"
        r"(?!\s+from\s+this\s+repository)",
        re.IGNORECASE,
    ),
    re.compile(r"\bhas\s+been\s+(?:published|approved|submitted|released)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+(?:now\s+|currently\s+)?(?:approved|submitted)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are)\s+(?:now\s+|currently\s+)?stable\b", re.IGNORECASE),
    re.compile(r"\bstable\s+(?:release|version)\b", re.IGNORECASE),
    re.compile(
        r"\b(?:is|are|was|were)\s+(?:now\s+|currently\s+)?(?:officially\s+)?released\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bpublicly\s+available\b", re.IGNORECASE),
    re.compile(r"\bgenerally\s+available\b", re.IGNORECASE),
    re.compile(r"\bpublic\s+release\b", re.IGNORECASE),
    re.compile(r"\blisted\s+in\b[^\n]{0,60}?\bDirectory\b", re.IGNORECASE),
    re.compile(r"\bavailable\s+(?:from|in|on)\b[^\n]{0,60}?\bDirectory\b", re.IGNORECASE),
)

# Structural separators are shared by portal-state and product-status scans.
# The capturing group lets direct questions retain their question mark for
# discourse classification. Brackets are handled separately so nested inner
# and outer text is always inspected as independent segments.
STRUCTURAL_SEPARATOR_PATTERN = re.compile(
    r"([.!?;:\n]"
    r"|[—–]"
    r"|,\s*(?:and|or)\s+"
    r"|(?<![A-Za-z])(?:even\s+though|even\s+so|but|however|yet|although|though|"
    r"whereas|nevertheless|nonetheless)(?![A-Za-z]))",
    re.IGNORECASE,
)
STRUCTURAL_BRACKET_PATTERN = re.compile(r"[()\[\]{}]")
QUESTION_BOUNDARIES = {"?"}
STRUCTURAL_OPENING_BRACKETS = {"(": ")", "[": "]", "{": "}"}
MAX_PORTAL_CONTEXT_SOURCE_DISTANCE = 240
MAX_PORTAL_BRACKET_CONTEXT_DEPTH = 4

# These are predicate/clause boundaries inside one structural segment. A
# separator becomes active only when both sides contain either an assertion
# candidate or a safe-scope operator. This avoids treating every comma or
# conjunction as a boundary while still isolating independently governed
# predicates such as "asks whether ... while the portal currently ...".
ASSERTION_SCOPE_SEPARATOR_PATTERN = re.compile(
    r"\b(?:even\s+though|even\s+so|at\s+the\s+same\s+time|simultaneously|while|whereas|"
    r"although|though|and|but)\b"
    r"|,",
    re.IGNORECASE,
)

# Structural discourse markers become explicit graph edges. Some of these
# tokens are separators themselves and therefore no longer appear in the next
# span's text; matching the retained boundary is what preserves their meaning.
CONTINUATION_LEAD_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:however|nevertheless|nonetheless|even\s+so|still|also|yet)(?![A-Za-z])",
    re.IGNORECASE,
)
CONTINUATION_BOUNDARY_PATTERN = re.compile(
    r"[;:—–]|\b(?:even\s+though|even\s+so|and|or|but|however|yet|although|"
    r"though|whereas|nevertheless|nonetheless|while)\b",
    re.IGNORECASE,
)
PORTAL_BOUNDED_SURFACE_ANAPHOR_PATTERN = re.compile(
    r"^(?:(?:however|nevertheless|nonetheless|even\s+so|still)\s*,?\s*)?"
    r"(?:it|this|that)\b",
    re.IGNORECASE,
)
def mask_negated_status_spans(text: str) -> str:
    """Blank every explicitly negated status span, preserving offsets."""
    masked = text
    for pattern in NEGATED_STATUS_PATTERNS:
        masked = pattern.sub(lambda match: " " * len(match.group(0)), masked)
    return masked


# --- Markdown visible-text normalization (standard library only) -------------

MD_FENCE_MARKER_PATTERN = re.compile(r"^\s{0,3}(?:```|~~~)")
MD_INLINE_CODE_PATTERN = re.compile(r"`[^`\n]*`")
MD_IMAGE_INLINE_PATTERN = re.compile(r"!\[([^\]]*)\]\(\s*<?([^)\s>]*)>?(?:\s+[^)]*)?\)")
MD_IMAGE_REFERENCE_PATTERN = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]")
MD_IMAGE_SHORTCUT_PATTERN = re.compile(r"!\[([^\]]+)\](?![\[(:])")
MD_DEFINITION_LINE_PATTERN = re.compile(
    r"^\s{0,3}\[([^\]]+)\]:\s*(?:<([^>]*)>|(\S+))\s*"
    r"(?:\"[^\"]*\"|'[^']*'|\([^)]*\))?\s*$"
)
MD_INLINE_LINK_PATTERN = re.compile(
    r"\[([^\]]*)\]\(\s*<?([^)\s>]*)>?(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
MD_REFERENCE_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\[([^\]]*)\]")
MD_SHORTCUT_LINK_PATTERN = re.compile(r"\[([^\]]+)\](?![\[(:])")
MD_HTML_EMPHASIS_PATTERN = re.compile(r"</?(?:strong|em|b|i)\s*/?>", re.IGNORECASE)
MD_HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
MD_STRIKETHROUGH_PATTERN = re.compile(r"~~[^~\n]*~~")
MD_SINGLE_ASTERISK_PATTERN = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")
MD_SINGLE_UNDERSCORE_PATTERN = re.compile(r"(?<![\w_])_([^_\n]+)_(?![\w_])")
MD_HEADING_LINE_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+")
MD_LIST_MARKER_LINE_PATTERN = re.compile(r"^(\s*)(?:[-+*]|\d+[.)])\s+")
MD_BLOCKQUOTE_LINE_PATTERN = re.compile(r"^\s{0,3}>\s?")
MD_THEMATIC_BREAK_PATTERN = re.compile(r"^\s{0,3}(?:\*\s*){3,}$|^\s{0,3}(?:[-_]\s*){3,}$")
MD_INDENTED_CODE_PATTERN = re.compile(r"^(?: {4}|\t)")
# CommonMark allows a backslash to escape any ASCII punctuation character.
MD_BACKSLASH_ESCAPE_PATTERN = re.compile(r"\\([!-/:-@\[-`{-~])")

def strip_code_blocks(text: str) -> list[str]:
    """Blank out fenced and top-level indented code blocks, keeping line count.

    An indented code block cannot interrupt a paragraph and cannot appear
    inside a list, where the same indentation is ordinary item continuation
    prose. Both conditions are tracked so real examples are excluded while
    list text is still scanned.
    """
    lines: list[str] = []
    in_fence = False
    in_indented_code = False
    in_list = False
    previous_blank = True

    for line in text.splitlines():
        stripped = line.strip()

        if MD_FENCE_MARKER_PATTERN.match(line):
            in_fence = not in_fence
            lines.append("")
            previous_blank = False
            continue
        if in_fence:
            lines.append("")
            continue

        if not stripped:
            # A blank line continues an indented code block but ends nothing
            # else that matters here; list context survives blank lines.
            lines.append("")
            previous_blank = True
            continue

        indent_match = MD_LIST_MARKER_LINE_PATTERN.match(line)
        if indent_match:
            in_list = True
        elif not MD_INDENTED_CODE_PATTERN.match(line):
            in_list = False

        is_indented = bool(MD_INDENTED_CODE_PATTERN.match(line))
        if is_indented and not in_list and (previous_blank or in_indented_code):
            in_indented_code = True
            lines.append("")
            previous_blank = False
            continue

        in_indented_code = False
        lines.append(line)
        previous_blank = False

    return lines


def join_soft_line_breaks(lines: list[str]) -> str:
    """Join soft line breaks inside a paragraph, as a renderer would.

    Canonical English lines are joined with one space. Blank lines, headings,
    list items, blockquotes, and thematic breaks start a new block and are
    never joined across.
    """
    blocks: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if not current:
            return
        joined = current[0]
        for part in current[1:]:
            left = joined.rstrip()
            right = part.lstrip()
            if not right:
                continue
            if not left:
                joined = right
                continue
            joined = left + " " + right
        blocks.append(joined)
        current.clear()

    for line in lines:
        if not line.strip():
            flush()
            continue

        if MD_THEMATIC_BREAK_PATTERN.match(line):
            flush()
            continue

        starts_block = False
        content = line
        if MD_HEADING_LINE_PATTERN.match(content):
            content = MD_HEADING_LINE_PATTERN.sub("", content)
            starts_block = True
        elif MD_LIST_MARKER_LINE_PATTERN.match(content):
            content = MD_LIST_MARKER_LINE_PATTERN.sub("", content)
            starts_block = True
        elif MD_BLOCKQUOTE_LINE_PATTERN.match(content):
            content = MD_BLOCKQUOTE_LINE_PATTERN.sub("", content)
            starts_block = True

        if starts_block:
            flush()
        current.append(content)

    flush()
    return "\n".join(blocks)


def markdown_visible_text(text: str) -> str:
    """Reduce Markdown to the prose a reader actually sees.

    Processing order, which the edge cases depend on:

    1. exclude fenced code blocks;
    2. exclude top-level indented code blocks;
    3. remove HTML comments, so a comment cannot split a word or hide a claim;
    4. decode named and numeric HTML character references;
    5. resolve CommonMark backslash escapes for ASCII punctuation;
    6. resolve visible link and image labels, dropping destinations and
       reference definitions;
    7. remove HTML emphasis tags;
    8. process emphasis, strong, and strikethrough delimiters;
    9. remove block markers, retaining visible prose;
    10. join soft line breaks inside each paragraph;
    11. keep paragraphs separated, so unrelated lines never fuse.

    Inline code spans and fenced blocks are excluded because they are
    examples, not statements; strikethrough contents are excluded because
    struck text reads as deleted, so "~~not~~ published" asserts publication.

    This is a conservative submission-policy normalizer, not a complete
    CommonMark renderer.
    """
    # 1-2: code blocks.
    lines = strip_code_blocks(text)
    visible = "\n".join(lines)

    # 3: HTML comments, including multiline.
    visible = MD_HTML_COMMENT_PATTERN.sub("", visible)

    # 4: character references, before emphasis so &ast; behaves like *.
    visible = html.unescape(visible)

    # 5: backslash escapes, before emphasis for the same reason.
    visible = MD_BACKSLASH_ESCAPE_PATTERN.sub(lambda m: m.group(1), visible)

    # 6: inline code spans, then labels; reference definitions become blank.
    visible = MD_INLINE_CODE_PATTERN.sub(" ", visible)
    visible = "\n".join(
        "" if MD_DEFINITION_LINE_PATTERN.match(line) else line
        for line in visible.splitlines()
    )
    visible = MD_IMAGE_INLINE_PATTERN.sub(lambda m: m.group(1), visible)
    visible = MD_IMAGE_REFERENCE_PATTERN.sub(lambda m: m.group(1), visible)
    visible = MD_IMAGE_SHORTCUT_PATTERN.sub(lambda m: m.group(1), visible)
    visible = MD_INLINE_LINK_PATTERN.sub(lambda m: m.group(1), visible)
    visible = MD_REFERENCE_LINK_PATTERN.sub(lambda m: m.group(1), visible)
    # Keep bracket boundaries around shortcut labels. The visible label still
    # participates in claim scans, while a plain bracketed aside remains
    # structurally isolated from surrounding safe prose.
    visible = MD_SHORTCUT_LINK_PATTERN.sub(lambda m: f"[{m.group(1)}]", visible)

    # 7-8: emphasis.
    visible = MD_HTML_EMPHASIS_PATTERN.sub("", visible)
    visible = MD_STRIKETHROUGH_PATTERN.sub(" ", visible)
    visible = visible.replace("**", "").replace("__", "")
    visible = MD_SINGLE_ASTERISK_PATTERN.sub(lambda m: m.group(1), visible)
    visible = MD_SINGLE_UNDERSCORE_PATTERN.sub(lambda m: m.group(1), visible)

    # 9-11: block markers, soft line breaks, paragraph separation.
    return join_soft_line_breaks(visible.splitlines())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the Codex Plugin submission package."
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


class DuplicateJSONKeyError(ValueError):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise DuplicateJSONKeyError(key)
        document[key] = value
    return document


def load_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"File does not exist: {path}") from exc
    except DuplicateJSONKeyError as exc:
        raise ValueError(f"Duplicate JSON key in {path}: {exc.key!r}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def check_exact(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"{label} must equal {expected!r}; found {actual!r}.")


def check_key_set(errors: list[str], label: str, actual: set[str], expected: set[str]) -> None:
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        errors.append(f"{label} keys mismatch; missing={missing}, extra={extra}")


def validate_required_files(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        candidate = root / relative
        if not candidate.is_file():
            errors.append(f"Required submission file is missing: {relative}")
        elif candidate.stat().st_size == 0:
            errors.append(f"Required submission file is empty: {relative}")


def find_empty_strings(value: Any, path: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        if not value.strip():
            found.append(path or "<root>")
    elif isinstance(value, dict):
        for key, sub_value in value.items():
            found.extend(find_empty_strings(sub_value, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(find_empty_strings(item, f"{path}[{index}]"))
    return found


def validate_listing(root: Path, errors: list[str]) -> None:
    try:
        listing = load_json(root / LISTING_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(listing, dict):
        errors.append("listing.json must be a JSON object.")
        return

    check_key_set(errors, "listing.json top-level", set(listing), EXPECTED_LISTING_KEYS)

    check_exact(
        errors, "listing.json submissionType", listing.get("submissionType"),
        EXPECTED_SUBMISSION_TYPE,
    )
    check_exact(errors, "listing.json pluginName", listing.get("pluginName"), EXPECTED_PLUGIN_NAME)
    check_exact(errors, "listing.json publisher", listing.get("publisher"), EXPECTED_PUBLISHER)
    check_exact(
        errors, "listing.json shortDescription", listing.get("shortDescription"),
        EXPECTED_SHORT_DESCRIPTION,
    )
    check_exact(
        errors, "listing.json longDescription", listing.get("longDescription"),
        EXPECTED_LONG_DESCRIPTION,
    )
    check_exact(errors, "listing.json category", listing.get("category"), EXPECTED_CATEGORY)
    check_exact(errors, "listing.json websiteUrl", listing.get("websiteUrl"), EXPECTED_WEBSITE_URL)
    check_exact(errors, "listing.json supportUrl", listing.get("supportUrl"), EXPECTED_SUPPORT_URL)
    check_exact(errors, "listing.json privacyUrl", listing.get("privacyUrl"), EXPECTED_PRIVACY_URL)
    check_exact(errors, "listing.json termsUrl", listing.get("termsUrl"), EXPECTED_TERMS_URL)
    check_exact(errors, "listing.json logoStatus", listing.get("logoStatus"), EXPECTED_LOGO_STATUS)
    check_exact(
        errors, "listing.json releaseStatus", listing.get("releaseStatus"),
        EXPECTED_RELEASE_STATUS,
    )
    check_exact(
        errors, "listing.json publicDirectoryStatus", listing.get("publicDirectoryStatus"),
        EXPECTED_PUBLIC_DIRECTORY_STATUS,
    )

    for key in URL_LISTING_KEYS:
        value = listing.get(key)
        if isinstance(value, str) and not value.startswith("https://"):
            errors.append(f"listing.json {key} must be an HTTPS URL; found {value!r}.")

    identity = listing.get("developerIdentity")
    if not isinstance(identity, dict):
        errors.append("listing.json 'developerIdentity' must be an object.")
    else:
        check_key_set(
            errors, "listing.json developerIdentity", set(identity),
            EXPECTED_DEVELOPER_IDENTITY_KEYS,
        )
        check_exact(
            errors, "listing.json developerIdentity.type", identity.get("type"),
            EXPECTED_DEVELOPER_TYPE,
        )
        check_exact(
            errors, "listing.json developerIdentity.name", identity.get("name"),
            EXPECTED_DEVELOPER_NAME,
        )
        # An agent must never assert that OpenAI has verified this business.
        check_exact(
            errors, "listing.json developerIdentity.verificationStatus",
            identity.get("verificationStatus"), EXPECTED_VERIFICATION_STATUS,
        )

    skills = listing.get("skills")
    if not isinstance(skills, list) or len(skills) != 1:
        errors.append("listing.json 'skills' must contain exactly one entry.")
    else:
        entry = skills[0]
        if not isinstance(entry, dict):
            errors.append("listing.json skills entry must be an object.")
        else:
            check_key_set(errors, "listing.json skills[0]", set(entry), EXPECTED_SKILL_KEYS)
            check_exact(
                errors, "listing.json skills[0].name", entry.get("name"), EXPECTED_SKILL_NAME
            )
            check_exact(
                errors, "listing.json skills[0].path", entry.get("path"), EXPECTED_SKILL_PATH
            )
            path_value = entry.get("path")
            if isinstance(path_value, str) and not (root / path_value).is_dir():
                errors.append(
                    f"listing.json skills[0].path does not exist in the repository: {path_value}"
                )

    for location in find_empty_strings(listing, ""):
        errors.append(f"listing.json contains an empty string at: {location}")


def validate_starter_prompts(root: Path, errors: list[str]) -> None:
    try:
        document = load_json(root / STARTER_PROMPTS_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(document, dict) or "starterPrompts" not in document:
        errors.append("starter-prompts.json must be an object with a 'starterPrompts' key.")
        return

    prompts = document["starterPrompts"]
    if not isinstance(prompts, list):
        errors.append("starter-prompts.json 'starterPrompts' must be a list.")
        return

    if len(prompts) != EXPECTED_STARTER_PROMPT_COUNT:
        errors.append(
            f"starter-prompts.json must contain exactly {EXPECTED_STARTER_PROMPT_COUNT} "
            f"prompts; found {len(prompts)}."
        )

    seen: set[str] = set()
    for index, prompt in enumerate(prompts):
        label = f"starter-prompts.json[{index}]"
        if not isinstance(prompt, dict):
            errors.append(f"{label} must be an object.")
            continue

        check_key_set(errors, label, set(prompt), set(STARTER_PROMPT_FIELDS))

        for field in STARTER_PROMPT_FIELDS:
            value = prompt.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} field {field!r} must be a non-empty string.")

        prompt_id = prompt.get("id")
        if isinstance(prompt_id, str):
            if prompt_id in seen:
                errors.append(f"starter-prompts.json has a duplicate id: {prompt_id}")
            seen.add(prompt_id)

        mode = prompt.get("expectedMode")
        if isinstance(mode, str) and mode not in VALID_MODES:
            errors.append(
                f"{label} expectedMode must be one of {list(VALID_MODES)}; found {mode!r}."
            )

    for location in find_empty_strings(document, ""):
        errors.append(f"starter-prompts.json contains an empty string at: {location}")


def validate_test_cases(root: Path, errors: list[str]) -> None:
    try:
        document = load_json(root / TEST_CASES_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(document, dict) or "testCases" not in document:
        errors.append("test-cases.json must be an object with a 'testCases' key.")
        return

    cases = document["testCases"]
    if not isinstance(cases, list):
        errors.append("test-cases.json 'testCases' must be a list.")
        return

    if len(cases) != EXPECTED_TEST_CASE_COUNT:
        errors.append(
            f"test-cases.json must contain exactly {EXPECTED_TEST_CASE_COUNT} test cases; "
            f"found {len(cases)}."
        )

    seen: set[str] = set()
    positive = 0
    negative = 0

    for index, case in enumerate(cases):
        label = f"test-cases.json[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{label} must be an object.")
            continue

        check_key_set(errors, label, set(case), set(TEST_CASE_FIELDS))

        for field in TEST_CASE_FIELDS:
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label} field {field!r} must be a non-empty string.")

        case_id = case.get("id")
        if isinstance(case_id, str):
            if case_id in seen:
                errors.append(f"test-cases.json has a duplicate id: {case_id}")
            seen.add(case_id)

        case_type = case.get("type")
        if case_type == "positive":
            positive += 1
        elif case_type == "negative":
            negative += 1
        else:
            errors.append(
                f"{label} type must be one of {list(VALID_TEST_TYPES)}; found {case_type!r}."
            )

    if positive != EXPECTED_POSITIVE_COUNT:
        errors.append(
            f"test-cases.json must contain exactly {EXPECTED_POSITIVE_COUNT} positive test "
            f"cases; found {positive}."
        )
    if negative != EXPECTED_NEGATIVE_COUNT:
        errors.append(
            f"test-cases.json must contain exactly {EXPECTED_NEGATIVE_COUNT} negative test "
            f"cases; found {negative}."
        )

    for location in find_empty_strings(document, ""):
        errors.append(f"test-cases.json contains an empty string at: {location}")


def validate_availability(root: Path, errors: list[str]) -> None:
    try:
        availability = load_json(root / AVAILABILITY_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(availability, dict):
        errors.append("availability.json must be a JSON object.")
        return

    # Availability is a human decision; the file may only record a recommendation.
    check_exact(
        errors, "availability.json status", availability.get("status"),
        EXPECTED_AVAILABILITY_STATUS,
    )

    for key in ("recommendedInitialAvailability", "languageSupport", "excludedRegions"):
        if not isinstance(availability.get(key), list):
            errors.append(f"availability.json {key!r} must be a list.")

    check_exact(
        errors,
        "availability.json languageSupport",
        availability.get("languageSupport"),
        EXPECTED_LANGUAGE_SUPPORT,
    )

    notes = availability.get("decisionNotes")
    if not isinstance(notes, str) or not notes.strip():
        errors.append("availability.json 'decisionNotes' must be a non-empty string.")

    for location in find_empty_strings(availability, ""):
        errors.append(f"availability.json contains an empty string at: {location}")


def check_boundaries(
    errors: list[str],
    label: str,
    text: str,
    boundaries: tuple[tuple[str, tuple[str, ...]], ...],
) -> None:
    lowered = text.lower()
    for name, wordings in boundaries:
        if not all(wording.lower() in lowered for wording in wordings):
            errors.append(f"{label} must state the boundary: {name}")


def validate_privacy(root: Path, errors: list[str]) -> None:
    path = root / PRIVACY_RELATIVE
    if not path.is_file():
        return
    check_boundaries(
        errors, "PRIVACY.md", path.read_text(encoding="utf-8"), PRIVACY_REQUIRED_BOUNDARIES
    )


def section_text(text: str, heading: str) -> str:
    """Return the body under an exact Markdown heading, up to the next
    heading of the same level."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    collected: list[str] = []
    inside = False
    for line in lines:
        if line.strip() == heading:
            inside = True
            continue
        if inside:
            stripped = line.strip()
            if stripped.startswith("#"):
                current_level = len(stripped) - len(stripped.lstrip("#"))
                if current_level <= level:
                    break
            collected.append(line)
    return "\n".join(collected)


def validate_support(root: Path, errors: list[str]) -> None:
    path = root / SUPPORT_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    check_boundaries(errors, "SUPPORT.md", text, SUPPORT_REQUIRED_BOUNDARIES)

    if not section_text(text, SUPPORT_CHANNEL_HEADING).strip():
        errors.append(f"SUPPORT.md must contain a {SUPPORT_CHANNEL_HEADING!r} section.")

    # GitHub Issues is the only support channel. A noncanonical URL —
    # written raw, as an inline link, or through a reference definition — is
    # rejected only when visible prose or a link label on its own line
    # materially assigns it a support/contact/help-desk role, or when the
    # line immediately above (across blank lines or a fence marker only)
    # asserts a channel and introduces a URL-only destination. Documentation
    # and reference wording is explanatory and never a channel assertion; a
    # URL path alone is never proof; an unused reference definition alone is
    # never a finding.
    definitions = parse_reference_definitions(text)
    pending_assertion = ""
    for line in text.splitlines():
        stripped_line = line.strip()
        if not stripped_line or MD_FENCE_MARKER_PATTERN.match(line):
            continue
        if MD_DEFINITION_LINE_PATTERN.match(line):
            # Definitions are inert; findings attach to the lines that
            # reference them. A definition also ends any pending context.
            pending_assertion = ""
            continue

        visible, targets = support_line_targets(line, definitions)
        line_asserts = any(
            pattern.search(visible) for pattern in SUPPORT_ASSERTION_PATTERNS
        ) and not SUPPORT_DOC_QUALIFIER_PATTERN.search(visible)
        residue = URL_PATTERN.sub("", visible)
        url_only = not re.search(r"[A-Za-z0-9_]", residue)

        for raw_url in targets:
            url = raw_url.rstrip(".,;):")
            if url == CANONICAL_SUPPORT_URL:
                continue
            if line_asserts or (url_only and pending_assertion):
                errors.append(
                    "SUPPORT.md declares GitHub Issues as the only support channel, so "
                    f"it must not present another support channel: {stripped_line!r}"
                )

        if targets:
            # Any URL-bearing line consumes the pending context.
            pending_assertion = ""
        elif (
            line_asserts
            and stripped_line.endswith(":")
        ):
            # The line materially introduces a destination that follows.
            pending_assertion = stripped_line
        else:
            # Unrelated prose, headings, and list items end the context.
            pending_assertion = ""


def validate_plugin_readmes(root: Path, errors: list[str]) -> None:
    for relative in PLUGIN_README_FILES:
        path = root / relative
        if not path.is_file():
            errors.append(f"Required Plugin README is missing: {relative}")
            continue
        if path.stat().st_size == 0:
            errors.append(f"Required Plugin README is empty: {relative}")
            continue
        check_boundaries(
            errors,
            relative,
            path.read_text(encoding="utf-8"),
            PLUGIN_README_REQUIRED_BOUNDARIES[relative],
        )


def build_structured_span_graph(visible: str) -> StructuredSpanGraph:
    """Split visible prose without discarding source or discourse structure.

    Quote ranges are captured before any structural boundary is considered.
    Separators and brackets inside those ranges therefore remain part of the
    governing example/quotation span. Offsets refer to the normalized visible
    source returned by ``markdown_visible_text``.
    """
    quoted_ranges = quoted_text_ranges(visible)
    events: list[tuple[int, int, str, str]] = []
    for match in STRUCTURAL_SEPARATOR_PATTERN.finditer(visible):
        if position_is_quoted(match.start(), quoted_ranges):
            continue
        raw = match.group(0)
        events.append((match.start(), match.end(), "separator", raw))
    for match in STRUCTURAL_BRACKET_PATTERN.finditer(visible):
        if position_is_quoted(match.start(), quoted_ranges):
            continue
        raw = match.group(0)
        kind = "open" if raw in STRUCTURAL_OPENING_BRACKETS else "close"
        events.append((match.start(), match.end(), kind, raw))
    events.sort(key=lambda event: (event[0], event[1]))

    spans: list[StructuredSpan] = []
    bracket_antecedents: dict[int, int | None] = {}
    bracket_parents: dict[int, int | None] = {}
    bracket_stack: list[int] = []
    paragraph_id = 0
    sentence_id = 0
    next_bracket_id = 0
    cursor = 0
    pending_boundary = ""

    def emit(end: int) -> int | None:
        nonlocal pending_boundary
        start = cursor
        while start < end and (visible[start].isspace() or visible[start] == ","):
            start += 1
        stop = end
        while stop > start and (visible[stop - 1].isspace() or visible[stop - 1] == ","):
            stop -= 1
        if start >= stop:
            pending_boundary += visible[cursor:end]
            return None

        before = pending_boundary + visible[cursor:start]
        after = visible[stop:end]
        intersections = tuple(
            (quote_start, quote_end)
            for quote_start, quote_end in quoted_ranges
            if quote_start < stop and quote_end > start
        )
        span = StructuredSpan(
            span_id=len(spans),
            text=visible[start:stop],
            start=start,
            end=stop,
            paragraph_id=paragraph_id,
            sentence_id=sentence_id,
            parent_bracket_id=bracket_stack[-1] if bracket_stack else None,
            nesting_depth=len(bracket_stack),
            boundary_before=before,
            boundary_after=after,
            quoted_ranges=intersections,
        )
        spans.append(span)
        pending_boundary = after
        return span.span_id

    for start, end, kind, raw in events:
        emitted_id = emit(start)
        if spans:
            spans[-1].boundary_after += raw
        pending_boundary += raw

        if kind == "open":
            bracket_id = next_bracket_id
            next_bracket_id += 1
            bracket_antecedents[bracket_id] = emitted_id
            bracket_parents[bracket_id] = bracket_stack[-1] if bracket_stack else None
            bracket_stack.append(bracket_id)
        elif kind == "close":
            if bracket_stack:
                bracket_stack.pop()
        else:
            if raw in QUESTION_BOUNDARIES and emitted_id is not None:
                spans[emitted_id].text += raw
                spans[emitted_id].end = end
            if "\n" in raw:
                paragraph_id += raw.count("\n")
                sentence_id += raw.count("\n")
            elif any(boundary in raw for boundary in ".!?"):
                sentence_id += 1
        cursor = end

    emit(len(visible))

    last_sibling: dict[tuple[int, int | None], int] = {}
    for span in spans:
        key = (span.paragraph_id, span.parent_bracket_id)
        previous = last_sibling.get(key)
        span.previous_sibling = previous
        if previous is not None:
            spans[previous].next_sibling = span.span_id
        last_sibling[key] = span.span_id

    continuation_antecedents: dict[int, int] = {}
    for span in spans:
        if span.previous_sibling is None or "\n" in span.boundary_before:
            continue
        antecedent = spans[span.previous_sibling]
        same_sentence = span.sentence_id == antecedent.sentence_id
        next_sentence = span.sentence_id == antecedent.sentence_id + 1
        if (
            same_sentence
            and CONTINUATION_BOUNDARY_PATTERN.search(span.boundary_before)
        ) or (
            next_sentence
            and (
                CONTINUATION_LEAD_PATTERN.search(span.boundary_before)
                or CONTINUATION_LEAD_PATTERN.match(span.text)
            )
        ):
            continuation_antecedents[span.span_id] = antecedent.span_id

    return StructuredSpanGraph(
        tuple(spans),
        bracket_antecedents,
        bracket_parents,
        continuation_antecedents,
    )


def structural_atomic_segments(visible: str) -> list[str]:
    """Compatibility view for scans that need only independent span text."""
    return [span.text for span in build_structured_span_graph(visible).spans]


def portal_patterns_match(
    patterns: tuple[re.Pattern[str], ...], segment: str
) -> bool:
    return any(pattern.search(segment) for pattern in patterns)


def matches_any(patterns: tuple[re.Pattern[str], ...], segment: str) -> bool:
    return any(pattern.search(segment) for pattern in patterns)


def classify_object_kind(text: str) -> ObjectKind:
    if portal_patterns_match(PORTAL_STATE_OBJECT_PATTERNS, text) or any(
        pattern.search(text) for pattern in PORTAL_SELF_STATE_PATTERNS
    ):
        return ObjectKind.STRONG_MATERIAL_OBJECT
    if (
        PORTAL_ANAPHORIC_STATE_OBJECT_PATTERN.search(text) is not None
        and PORTAL_ANAPHORIC_MATERIAL_PREDICATE_PATTERN.search(text) is not None
    ):
        return ObjectKind.BOUNDED_ANAPHORIC_OBJECT
    return ObjectKind.NONE


def portal_text_has_state_object(text: str) -> bool:
    return classify_object_kind(text) is not ObjectKind.NONE


def classify_predicate_kind(text: str) -> PredicateKind:
    if matches_any(PORTAL_MATERIAL_DISPLAY_PREDICATE_PATTERNS, text):
        return PredicateKind.MATERIAL_DISPLAY
    if portal_patterns_match(PORTAL_STATE_PREDICATE_PATTERNS, text):
        return PredicateKind.STATE
    return PredicateKind.NONE


def portal_text_has_state_predicate(text: str) -> bool:
    return classify_predicate_kind(text) is not PredicateKind.NONE


def portal_text_has_explicit_context(text: str) -> bool:
    return portal_patterns_match(PORTAL_CONTEXT_PATTERNS, text) or (
        portal_patterns_match(PORTAL_GENERIC_SURFACE_PATTERNS, text)
        and PORTAL_STRONG_CONTEXTUAL_OBJECT_PATTERN.search(text) is not None
    )


def classify_surface_context(
    text: str, inherited_portal_context: bool = False
) -> SurfaceContext:
    if (
        portal_text_has_explicit_context(text)
        or inherited_portal_context
        or any(pattern.search(text) for pattern in PORTAL_IMPLICIT_CONTEXT_PATTERNS)
    ):
        return SurfaceContext.GOVERNED_PORTAL
    if portal_patterns_match(PORTAL_GENERIC_SURFACE_PATTERNS, text):
        return SurfaceContext.GENERIC_UI
    return SurfaceContext.NONE


def portal_text_materially_assertive(
    text: str, inherited_portal_context: bool = False
) -> bool:
    """Return whether one clause contains a complete portal-state predicate."""
    return (
        classify_surface_context(text, inherited_portal_context)
        is SurfaceContext.GOVERNED_PORTAL
        and classify_object_kind(text) is not ObjectKind.NONE
        and classify_predicate_kind(text) is not PredicateKind.NONE
    )


def product_text_materially_assertive(text: str) -> bool:
    return any(pattern.search(text) for pattern in POSITIVE_STATUS_PATTERNS)


def text_has_safe_scope_operator(text: str) -> bool:
    return any(
        matches_any(patterns, text)
        for patterns in (
            PORTAL_REPOSITORY_EVIDENCE_SAFE_PATTERNS,
            PORTAL_EXPLANATORY_SEGMENT_PATTERNS,
            PORTAL_QUESTION_VERIFICATION_PATTERNS,
            PORTAL_FUTURE_SEGMENT_PATTERNS,
            PORTAL_HUMAN_GATE_SAFE_PATTERNS,
        )
    )


def text_has_assertion_candidate(text: str) -> bool:
    """A boundary is useful only when each side carries a proposition."""
    return (
        text_has_safe_scope_operator(text)
        or portal_text_materially_assertive(text)
        or (
            portal_text_has_state_object(text)
            and portal_text_has_state_predicate(text)
        )
        or product_text_materially_assertive(text)
    )


def quoted_text_ranges(text: str) -> list[tuple[int, int]]:
    return sorted(
        {
            (match.start(), match.end())
            for pattern in QUOTED_TEXT_PATTERNS
            for match in pattern.finditer(text)
        }
    )


def position_is_quoted(position: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in ranges)


def trimmed_range(text: str, start: int, end: int) -> tuple[int, int] | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def trailing_safe_scope_governs_question(left: str, right: str) -> bool:
    """Keep a governed question intact when its operator follows a comma."""
    left_has_question_object = bool(
        re.search(r"\bwhether\b[^.!?]*$", left, re.IGNORECASE)
    )
    right_is_governing_operator = bool(
        re.search(
            r"\b(?:cannot|can\s+not|must|needs?\s+to)\b[^.!?]*"
            r"\b(?:determine|verify|check|confirm)\b",
            right,
            re.IGNORECASE,
        )
    )
    return left_has_question_object and right_is_governing_operator


def leading_safe_scope_governs_predicate(left: str, right: str) -> bool:
    """Keep a short future/example modifier attached to its predicate."""
    return bool(
        re.fullmatch(
            r"(?:in\s+the\s+future|in\s+this\s+example|for\s+example|future|later|"
            r"in\s+(?:a\s+)?(?:hypothetical|conditional|counterfactual)"
            r"(?:\s+[a-z]+){0,2})",
            left.strip(),
            re.IGNORECASE,
        )
        and text_has_assertion_candidate(right)
    )


def predicate_clause_ranges(segment: str) -> list[tuple[int, int]]:
    """Extract independently governed clauses inside one structural segment.

    Commas and conjunctions are candidate boundaries, not unconditional ones.
    A split is retained only when both sides contain an assertion or a
    discourse operator, and separators inside quoted example text are ignored.
    """
    ranges: list[tuple[int, int]] = []
    cursor = 0
    quoted_ranges = quoted_text_ranges(segment)

    for match in ASSERTION_SCOPE_SEPARATOR_PATTERN.finditer(segment):
        if position_is_quoted(match.start(), quoted_ranges):
            continue
        left_range = trimmed_range(segment, cursor, match.start())
        right_range = trimmed_range(segment, match.end(), len(segment))
        if left_range is None or right_range is None:
            continue
        left = segment[left_range[0] : left_range[1]]
        right = segment[right_range[0] : right_range[1]]
        if trailing_safe_scope_governs_question(
            left, right
        ) or leading_safe_scope_governs_predicate(left, right):
            continue
        if not (
            text_has_assertion_candidate(left)
            and text_has_assertion_candidate(right)
        ):
            continue
        ranges.append(left_range)
        cursor = match.end()

    final_range = trimmed_range(segment, cursor, len(segment))
    if final_range is not None:
        ranges.append(final_range)
    return ranges


def classify_predicate_scope(text: str) -> DiscourseMode:
    """Attach one safe operator only to the clause/predicate it governs."""
    if matches_any(PORTAL_REPOSITORY_EVIDENCE_SAFE_PATTERNS, text):
        return DiscourseMode.REPOSITORY_EVIDENCE_BOUNDARY
    if matches_any(PORTAL_FUTURE_SEGMENT_PATTERNS, text):
        return DiscourseMode.FUTURE_OR_HYPOTHETICAL
    if matches_any(PORTAL_QUESTION_VERIFICATION_PATTERNS, text):
        return DiscourseMode.QUESTION_OR_VERIFICATION
    if matches_any(PORTAL_EXPLANATORY_SEGMENT_PATTERNS, text):
        return DiscourseMode.DOCUMENTATION_OR_EXAMPLE
    if matches_any(PORTAL_HUMAN_GATE_SAFE_PATTERNS, text):
        return DiscourseMode.HUMAN_GATE
    return DiscourseMode.CURRENT_ASSERTION


def extract_assertion_spans(
    segment: str | StructuredSpan, predicate_kind: str
) -> list[AssertionSpan]:
    text = segment.text if isinstance(segment, StructuredSpan) else segment
    ranges = predicate_clause_ranges(text)
    spans: list[AssertionSpan] = []
    for index, (start, end) in enumerate(ranges):
        clause = text[start:end]
        if isinstance(segment, StructuredSpan):
            absolute_start = segment.start + start
            absolute_end = segment.start + end
            boundary_before = (
                segment.boundary_before
                if index == 0
                else text[ranges[index - 1][1] : start]
            )
            boundary_after = (
                segment.boundary_after
                if index == len(ranges) - 1
                else text[end : ranges[index + 1][0]]
            )
            quote_ranges = tuple(
                quote_range
                for quote_range in segment.quoted_ranges
                if quote_range[0] < absolute_end and quote_range[1] > absolute_start
            )
            structure_id = segment.span_id
            paragraph_id = segment.paragraph_id
            sentence_id = segment.sentence_id
            parent_bracket_id = segment.parent_bracket_id
            nesting_depth = segment.nesting_depth
        else:
            absolute_start = start
            absolute_end = end
            boundary_before = "" if index == 0 else text[ranges[index - 1][1] : start]
            boundary_after = "" if index == len(ranges) - 1 else text[end : ranges[index + 1][0]]
            quote_ranges = tuple(quoted_text_ranges(clause))
            structure_id = -1
            paragraph_id = 0
            sentence_id = 0
            parent_bracket_id = None
            nesting_depth = 0
        spans.append(
            AssertionSpan(
                text=clause,
                start=absolute_start,
                end=absolute_end,
                predicate_kind=predicate_kind,
                discourse_scope=classify_predicate_scope(clause),
                structure_id=structure_id,
                paragraph_id=paragraph_id,
                sentence_id=sentence_id,
                parent_bracket_id=parent_bracket_id,
                nesting_depth=nesting_depth,
                boundary_before=boundary_before,
                boundary_after=boundary_after,
                quoted_ranges=quote_ranges,
            )
        )
    return spans


def mask_documentation_example_terms(span: AssertionSpan) -> str:
    """Mask quoted terms only in the predicate span governed as an example."""
    if span.discourse_scope is not DiscourseMode.DOCUMENTATION_OR_EXAMPLE:
        return span.text
    masked = span.text
    for pattern in QUOTED_TEXT_PATTERNS:
        masked = pattern.sub(lambda match: " " * len(match.group(0)), masked)
    return masked


def classify_actuality(
    span: AssertionSpan,
    effective_text: str,
    inherited_portal_context: bool = False,
) -> Actuality:
    """Classify assertion force independently from surface and vocabulary."""
    if span.discourse_scope in {
        DiscourseMode.QUESTION_OR_VERIFICATION,
        DiscourseMode.REPOSITORY_EVIDENCE_BOUNDARY,
    }:
        return Actuality.NON_CURRENT_OR_NON_ASSERTIVE
    if span.discourse_scope is DiscourseMode.FUTURE_OR_HYPOTHETICAL:
        if matches_any(PORTAL_EXPLICIT_CURRENT_TIME_PATTERNS, effective_text):
            return Actuality.CURRENT_ASSERTION
        return Actuality.NON_CURRENT_OR_NON_ASSERTIVE
    if span.discourse_scope is DiscourseMode.DOCUMENTATION_OR_EXAMPLE:
        return Actuality.NON_CURRENT_OR_NON_ASSERTIVE
    if span.discourse_scope is DiscourseMode.HUMAN_GATE:
        if portal_text_materially_assertive(
            effective_text, inherited_portal_context
        ):
            return Actuality.CURRENT_ASSERTION
        return Actuality.NON_CURRENT_OR_NON_ASSERTIVE
    return Actuality.CURRENT_ASSERTION


def classify_portal_semantics(
    span: AssertionSpan, inherited_portal_context: bool = False
) -> PortalSemanticRoles:
    """Return the four inspectable roles required for a coherent rejection."""
    effective_text = mask_documentation_example_terms(span)
    return PortalSemanticRoles(
        surface_context=classify_surface_context(
            effective_text, inherited_portal_context
        ),
        actuality=classify_actuality(
            span, effective_text, inherited_portal_context
        ),
        object_kind=classify_object_kind(effective_text),
        predicate_kind=classify_predicate_kind(effective_text),
    )


def portal_assertion_span_is_unsafe(
    span: AssertionSpan, inherited_portal_context: bool = False
) -> bool:
    return classify_portal_semantics(
        span, inherited_portal_context
    ).is_current_material_portal_assertion


PORTAL_DOMAIN_GATE_PATTERN = re.compile(
    r"\bhuman\s+(?:review|verification)\s+is\s+required\b|"
    r"\b(?:must|needs?\s+to|required\s+to)\s+(?:determine|verify|check|confirm)\b",
    re.IGNORECASE,
)


def portal_span_can_supply_context(antecedent: AssertionSpan, current: AssertionSpan) -> bool:
    """Return only direct portal/domain antecedents; inherited spans cannot relay."""
    if portal_text_has_explicit_context(antecedent.text):
        return True
    return bool(
        PORTAL_DOMAIN_GATE_PATTERN.search(antecedent.text)
        and PORTAL_STRONG_CONTEXTUAL_OBJECT_PATTERN.search(current.text)
    )


def portal_state_component_source_offset(span: AssertionSpan) -> int:
    """Return the real source start of this span's state object/predicate.

    A structural span may begin with arbitrarily long non-state prose. Using
    ``span.start`` would let that prose make a distant state claim look close
    enough to inherit portal context.
    """
    relative_offsets = [
        match.start()
        for patterns in (
            PORTAL_STATE_OBJECT_PATTERNS,
            PORTAL_STATE_PREDICATE_PATTERNS,
            PORTAL_SELF_STATE_PATTERNS,
        )
        for pattern in patterns
        for match in (pattern.search(span.text),)
        if match is not None
    ]
    return span.start + min(relative_offsets) if relative_offsets else span.start


def portal_context_is_within_source_distance(
    antecedent: AssertionSpan, current: AssertionSpan
) -> bool:
    return (
        portal_state_component_source_offset(current) - antecedent.end
        <= MAX_PORTAL_CONTEXT_SOURCE_DISTANCE
    )


def adjacent_boundary_allows_context(
    antecedent: AssertionSpan, current: AssertionSpan
) -> bool:
    if antecedent.paragraph_id != current.paragraph_id:
        return False
    if not portal_context_is_within_source_distance(antecedent, current):
        return False
    boundary = current.boundary_before
    if "\n" in boundary:
        return False
    if antecedent.structure_id == current.structure_id:
        return bool(boundary.strip())
    if antecedent.sentence_id == current.sentence_id:
        return bool(CONTINUATION_BOUNDARY_PATTERN.search(boundary))
    return bool(
        current.sentence_id == antecedent.sentence_id + 1
        and CONTINUATION_LEAD_PATTERN.match(current.text)
    )


def inherited_portal_context(
    current_index: int,
    spans: list[AssertionSpan],
    graph: StructuredSpanGraph,
    spans_by_structure: dict[int, list[AssertionSpan]],
) -> bool:
    """Resolve one direct continuation/outer context edge.

    Only portal context crosses the edge. The antecedent's safe discourse mode
    never does: ``portal_assertion_span_is_unsafe`` always classifies the
    current predicate independently.
    """
    current = spans[current_index]
    if not (portal_text_has_state_object(current.text) and portal_text_has_state_predicate(current.text)):
        return False
    if portal_text_has_explicit_context(current.text):
        return False

    bracket_id = current.parent_bracket_id
    traversed = 0
    while bracket_id is not None and traversed < MAX_PORTAL_BRACKET_CONTEXT_DEPTH:
        structure_id = graph.bracket_antecedents.get(bracket_id)
        if structure_id is not None:
            for antecedent in reversed(spans_by_structure.get(structure_id, [])):
                if (
                    antecedent.paragraph_id == current.paragraph_id
                    and portal_context_is_within_source_distance(antecedent, current)
                    and portal_span_can_supply_context(antecedent, current)
                ):
                    return True
        bracket_id = graph.bracket_parents.get(bracket_id)
        traversed += 1

    if current_index > 0:
        antecedent = spans[current_index - 1]
        if antecedent.structure_id == current.structure_id:
            return adjacent_boundary_allows_context(
                antecedent, current
            ) and portal_span_can_supply_context(antecedent, current)

    # A subject pronoun can resolve the immediately preceding sentence's
    # named portal without inheriting that sentence's safe modality. This is
    # deliberately narrower than continuation inheritance: the current span
    # must be an explicit-current material assertion beginning with it/this/
    # that. Ordinary new-sentence material prose still observes the hard reset.
    if (
        PORTAL_BOUNDED_SURFACE_ANAPHOR_PATTERN.match(current.text)
        and matches_any(PORTAL_EXPLICIT_CURRENT_TIME_PATTERNS, current.text)
        and classify_object_kind(current.text) is not ObjectKind.NONE
        and classify_predicate_kind(current.text) is not PredicateKind.NONE
    ):
        previous_sentence_id = current.sentence_id - 1
        for antecedent in reversed(spans[:current_index]):
            if antecedent.paragraph_id != current.paragraph_id:
                break
            if antecedent.sentence_id < previous_sentence_id:
                break
            if (
                antecedent.sentence_id == previous_sentence_id
                and portal_text_has_explicit_context(antecedent.text)
                and portal_context_is_within_source_distance(antecedent, current)
            ):
                return True

    # A consumed structural connector is retained as one direct graph edge.
    # Consult only that nearest structural antecedent; never relay context
    # across an unrelated span or inherit the antecedent's discourse mode.
    antecedent_structure = graph.continuation_antecedents.get(current.structure_id)
    if antecedent_structure is None:
        return False
    antecedents = spans_by_structure.get(antecedent_structure, [])
    if not antecedents:
        return False
    antecedent = antecedents[-1]
    return (
        portal_context_is_within_source_distance(antecedent, current)
        and portal_span_can_supply_context(antecedent, current)
    )


def portal_segment_asserts_external_state(segment: str) -> bool:
    """Compatibility wrapper evaluating every predicate span independently."""
    return any(
        portal_assertion_span_is_unsafe(span)
        for span in extract_assertion_spans(segment, "portal-state")
    )


def validate_portal_state_assertions(root: Path, errors: list[str]) -> None:
    """Reject assertions about external portal contents or submission state."""
    for relative in PORTAL_STATE_SCAN_FILES:
        path = root / relative
        if not path.is_file():
            continue
        visible = markdown_visible_text(path.read_text(encoding="utf-8"))
        graph = build_structured_span_graph(visible)
        assertion_spans = [
            assertion
            for structural_span in graph.spans
            for assertion in extract_assertion_spans(structural_span, "portal-state")
        ]
        spans_by_structure: dict[int, list[AssertionSpan]] = {}
        for span in assertion_spans:
            spans_by_structure.setdefault(span.structure_id, []).append(span)
        for index, span in enumerate(assertion_spans):
            inherited_context = inherited_portal_context(
                index, assertion_spans, graph, spans_by_structure
            )
            if portal_assertion_span_is_unsafe(span, inherited_context):
                errors.append(
                    f"{relative} must not assert unverified external portal state: "
                    f"{span.text!r}."
                )


def validate_human_prerequisites(root: Path, errors: list[str]) -> None:
    path = root / HUMAN_PREREQUISITES_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    # Parse the status table structurally. Substring presence is not enough:
    # "COMPLETE - previously PENDING HUMAN CHECK" contains the pending text
    # while asserting the opposite, so the status cell must equal it exactly.
    data_rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell) for cell in cells):
            continue
        if cells == ["#", "Item", "Status"]:
            continue
        data_rows.append(cells)

    for row in data_rows:
        if len(row) != 3:
            errors.append(
                "human-prerequisites.md status row must have exactly three cells "
                f"(number, item, status); found {len(row)}: {row!r}"
            )

    seen: dict[str, int] = {}
    for row in data_rows:
        if len(row) != 3:
            continue
        item = row[1]
        seen[item] = seen.get(item, 0) + 1
        if item not in HUMAN_PREREQUISITE_ITEMS:
            errors.append(
                f"human-prerequisites.md status table has an unexpected item: {item!r}"
            )
            continue
        status = row[2]
        if status != PENDING_HUMAN_CHECK:
            errors.append(
                f"human-prerequisites.md status cell for {item!r} must equal "
                f"{PENDING_HUMAN_CHECK!r} exactly; found {status!r}."
            )

    for item in HUMAN_PREREQUISITE_ITEMS:
        count = seen.get(item, 0)
        if count == 0:
            errors.append(
                f"human-prerequisites.md status table is missing the required item: {item}"
            )
        elif count > 1:
            errors.append(
                f"human-prerequisites.md status table has {count} rows for {item!r}; "
                "exactly one is required."
            )


def validate_visual_assets(root: Path, errors: list[str]) -> None:
    path = root / VISUAL_ASSETS_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if EXPECTED_LOGO_STATUS not in text:
        errors.append(f"visual-assets.md must record the logo status {EXPECTED_LOGO_STATUS!r}.")


def validate_release_notes(root: Path, errors: list[str]) -> None:
    path = root / RELEASE_NOTES_RELATIVE
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")

    if EXPECTED_SUBMISSION_RELEASE_NOTES_VERSION not in text:
        errors.append(
            f"release-notes.md must record the synchronized Plugin version "
            f"{EXPECTED_SUBMISSION_RELEASE_NOTES_VERSION!r}."
        )


def validate_status_claims(root: Path, errors: list[str]) -> None:
    """Reject any product or submission status claim whose own span is not
    explicitly negated.

    Negation binds to the specific claim: explicitly negated status spans are
    masked out first, and every positive claim left anywhere in the remaining
    text fails. A negation earlier in the sentence therefore never licenses a
    later claim — "No submission has occurred — this Plugin is published."
    fails on its second canonical English span across em dashes, commas, and
    contrastive connectors. This bounded policy does not interpret localized
    prose or prove arbitrary natural-language equivalence.
    """
    for relative in CLAIM_SCAN_FILES:
        path = root / relative
        if not path.is_file():
            continue
        visible = markdown_visible_text(path.read_text(encoding="utf-8"))
        masked = mask_negated_status_spans(visible)
        for segment in structural_atomic_segments(masked):
            for span in extract_assertion_spans(segment, "product-status"):
                if span.discourse_scope is DiscourseMode.QUESTION_OR_VERIFICATION:
                    continue
                if (
                    span.discourse_scope is DiscourseMode.FUTURE_OR_HYPOTHETICAL
                    and not matches_any(PORTAL_CURRENT_STATE_CUE_PATTERNS, span.text)
                ):
                    continue
                scan_span = mask_documentation_example_terms(span)
                normalized = " ".join(scan_span.split())
                if not normalized:
                    continue
                for pattern in POSITIVE_STATUS_PATTERNS:
                    match = pattern.search(scan_span)
                    if match:
                        errors.append(
                            f"{relative} must not claim public Directory availability, "
                            f"or submitted, published, approved, released, or stable "
                            f"status: {normalized!r} asserts "
                            f"{' '.join(match.group(0).split())!r}."
                        )


CANONICAL_STATUS_MARKERS = {
    PLUGIN_README_RELATIVE: (
        "Development preview",
        "Agentic Change Audit marketplace",
        "0.1.0-dev.3",
        "Phase C desktop evidence is pending",
        "historical, superseded, and non-transferable",
        "English is the sole canonical language for machine semantics and exact tokens",
    ),
    SUBMISSION_README_RELATIVE: (
        "Plugin version: `0.1.0-dev.3`",
        "Marketplace identity: neutral `Agentic Change Audit marketplace`",
        "Phase C desktop evidence remains pending",
        "Earlier desktop evidence is historical, superseded, and non-transferable",
        "Translation parity is not a machine validation gate",
    ),
    RELEASE_NOTES_RELATIVE: (
        "Version: `0.1.0-dev.3`",
        "Phase C desktop evidence remains pending",
        "historical, superseded, and non-transferable",
        "Every human-prerequisite row remains `PENDING HUMAN CHECK`",
    ),
}
FORBIDDEN_CURRENT_STATUS_PATTERNS = (
    (
        re.compile(
            r"Phase\s+C.{0,120}\b(?:passed|complete(?:d)?|verified|succeeded)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "must keep Phase C pending",
    ),
    (
        re.compile(
            r"\b(?:Plugin|marketplace)\s+(?:is|was|has been)\s+"
            r"(?:submitted|approved|published|listed|publicly available)\b",
            re.IGNORECASE,
        ),
        "must not claim an external submission, approval, publication, or listing",
    ),
    (
        re.compile(
            r"after this branch is merged|once this Plugin foundation is merged|"
            r"resolve only after this branch is merged",
            re.IGNORECASE,
        ),
        "must not retain stale pre-merge wording",
    ),
)


def validate_canonical_status_contract(root: Path, errors: list[str]) -> None:
    """Check bounded English status facts without interpreting arbitrary prose."""
    for relative, markers in CANONICAL_STATUS_MARKERS.items():
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{relative} is missing canonical English marker: {marker!r}.")
        visible_text = markdown_visible_text(text)
        for pattern, diagnostic in FORBIDDEN_CURRENT_STATUS_PATTERNS:
            if pattern.search(visible_text):
                errors.append(f"{relative} {diagnostic}.")


def validate_no_local_paths(root: Path, errors: list[str]) -> None:
    for relative in SCANNED_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in LOCAL_PATH_PATTERNS:
            for match in pattern.finditer(text):
                errors.append(
                    f"{relative} contains a private local path: {match.group(0)!r}"
                )


def validate_no_addresses(root: Path, errors: list[str]) -> None:
    for relative in SCANNED_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for match in EMAIL_PATTERN.finditer(text):
            address = match.group(0)
            if address.lower().endswith(f"@{ALLOWED_EMAIL_DOMAIN}"):
                continue
            errors.append(
                f"{relative} contains an email address; only {ALLOWED_EMAIL_DOMAIN} "
                f"placeholders are allowed: {address!r}"
            )


def validate_no_secrets(root: Path, errors: list[str]) -> None:
    for relative in SCANNED_FILES:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"{relative} contains a secret-like value matching {pattern.pattern!r}."
                )


def contains_key(value: Any, forbidden: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if key in forbidden:
                found.append(key)
            found.extend(contains_key(sub_value, forbidden))
    elif isinstance(value, list):
        for item in value:
            found.extend(contains_key(item, forbidden))
    return found


def validate_manifest_boundary(root: Path, errors: list[str]) -> None:
    """The submission package must not move the Plugin runtime boundary."""
    try:
        manifest = load_json(root / MANIFEST_RELATIVE)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(manifest, dict):
        errors.append("plugin.json must be a JSON object.")
        return

    check_exact(
        errors, "plugin.json version", manifest.get("version"), EXPECTED_MANIFEST_VERSION
    )

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json 'interface' must be an object.")
    else:
        check_exact(
            errors, "plugin.json interface.capabilities", interface.get("capabilities"),
            EXPECTED_MANIFEST_CAPABILITIES,
        )

    for key in contains_key(manifest, FORBIDDEN_MANIFEST_KEYS):
        errors.append(f"plugin.json must not contain a forbidden runtime key: {key}")


def run_plugin_validator(root: Path, errors: list[str]) -> None:
    validator = root / PLUGIN_VALIDATOR_RELATIVE
    if not validator.is_file():
        errors.append(f"Plugin validator script is missing: {PLUGIN_VALIDATOR_RELATIVE}")
        return

    result = subprocess.run(
        [sys.executable, str(validator), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("Existing Codex Plugin validator failed:")
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            errors.append(f"  {line}")


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    errors: list[str] = []

    validate_required_files(root, errors)
    validate_listing(root, errors)
    validate_starter_prompts(root, errors)
    validate_test_cases(root, errors)
    validate_availability(root, errors)
    validate_privacy(root, errors)
    validate_support(root, errors)
    validate_plugin_readmes(root, errors)
    validate_portal_state_assertions(root, errors)
    validate_human_prerequisites(root, errors)
    validate_visual_assets(root, errors)
    validate_release_notes(root, errors)
    validate_status_claims(root, errors)
    validate_canonical_status_contract(root, errors)
    validate_no_local_paths(root, errors)
    validate_no_addresses(root, errors)
    validate_no_secrets(root, errors)
    validate_manifest_boundary(root, errors)
    run_plugin_validator(root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            f"Plugin submission validation: FAIL ({len(errors)} issue(s))", file=sys.stderr
        )
        return 1

    print("Plugin submission validation: PASS")
    print(f"- listing: {root / LISTING_RELATIVE}")
    print(f"- starter prompts: {EXPECTED_STARTER_PROMPT_COUNT}")
    print(
        f"- test cases: {EXPECTED_TEST_CASE_COUNT} "
        f"({EXPECTED_POSITIVE_COUNT} positive, {EXPECTED_NEGATIVE_COUNT} negative)"
    )
    print(f"- developer identity: {EXPECTED_VERIFICATION_STATUS}")
    print(f"- logo: {EXPECTED_LOGO_STATUS}")
    print(f"- public content scanned: {len(SCANNED_FILES)} files")
    print(f"- status claims: none unnegated in {len(CLAIM_SCAN_FILES)} files")
    print(f"- human gates: {len(HUMAN_PREREQUISITE_ITEMS)} × {PENDING_HUMAN_CHECK}")
    print(f"- availability: {EXPECTED_AVAILABILITY_STATUS}")
    print(f"- public directory status: {EXPECTED_PUBLIC_DIRECTORY_STATUS}")
    print(f"- Plugin version: {EXPECTED_MANIFEST_VERSION} (development)")
    print("- capabilities: Read only")
    print("- submission to OpenAI: none")
    return 0


def cli() -> int:
    """Fail closed on unexpected defects without exposing a raw traceback."""
    try:
        return main()
    except Exception:
        print("ERROR: Unexpected Plugin submission validator failure.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
