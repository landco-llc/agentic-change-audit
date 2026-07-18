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
PLUGIN_README_JA_RELATIVE = f"{PLUGIN_RELATIVE}/README.ja.md"
PLUGIN_README_ZH_HANT_RELATIVE = f"{PLUGIN_RELATIVE}/README.zh-Hant.md"

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
    PLUGIN_README_JA_RELATIVE,
    PLUGIN_README_ZH_HANT_RELATIVE,
)

# Files scanned for local paths, addresses, and secret-like values.
SCANNED_FILES = REQUIRED_FILES + PLUGIN_README_FILES

# Files scanned for product and submission status claims.
CLAIM_SCAN_FILES = (
    RELEASE_NOTES_RELATIVE,
    SUBMISSION_README_RELATIVE,
) + PLUGIN_README_FILES

# Files whose portal wording must stay inside the repository-evidence lane.
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

EXPECTED_MANIFEST_VERSION = "0.1.0-dev.1"
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

# Phrases that materially assert a support/contact channel role, in English,
# Japanese, and Traditional Chinese, including mixed-language forms such as
# "公式help desk". Generic support vocabulary ("support terminology",
# "customer-support vocabulary", "サポート用語", "支援術語") does not match,
# and a URL path such as /help or /support is never proof by itself — the
# assertion must appear in the text around the URL.
SUPPORT_ASSERTION_PATTERNS = (
    # English.
    re.compile(r"\bofficial\s+(?:customer\s+)?support\b", re.IGNORECASE),
    re.compile(r"\bsupport\s+is\s+(?:also\s+)?available\s+(?:at|via|through|from)\b", re.IGNORECASE),
    re.compile(r"\bsupport\s+(?:channel|portal|contact)\b", re.IGNORECASE),
    re.compile(r"\bcontact\s+support\b", re.IGNORECASE),
    re.compile(r"\bhelp\s*desk\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+support\s+(?:hotline|line|desk|team|portal)\b", re.IGNORECASE),
    # Japanese.
    re.compile(r"公式\s*(?:サポート|ヘルプデスク|help\s*desk)", re.IGNORECASE),
    re.compile(r"サポート(?:窓口|チャネル|チャンネル|ポータル)"),
    re.compile(r"問い?合わせ(?:窓口|先)"),
    re.compile(r"ヘルプデスク"),
    re.compile(r"支援窓口"),
    # Traditional Chinese.
    re.compile(r"官方(?:支援|客服)"),
    re.compile(r"(?:支援|客服)(?:管道|入口)"),
    re.compile(r"聯絡支援"),
    re.compile(r"服務台"),
    re.compile(r"協助中心"),
)
URL_PATTERN = re.compile(r"https?://[^\s<>()\[\]\"'`。、，]+")

# Explanatory wording: a line qualified as documentation, reference, or
# terminology material is describing support concepts, not assigning the URL
# a channel role.
SUPPORT_DOC_QUALIFIER_PATTERN = re.compile(
    r"\b(?:documentation|reference|background|terminology|vocabulary|glossary"
    r"|implementation\s+notes|explains|discusses|compares)\b"
    r"|説明|用語|背景資料|参照|参考資料|ドキュメント|実装ノート|解説"
    r"|說明|術語|背景資料|參閱|參考資料|文件|詞彙|解說",
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
            "not submitted to, listed in, or available from the public Plugins Directory",
            ("not submitted to, listed in, or available from",),
        ),
        (
            "official OpenAI submission is not complete",
            ("Official OpenAI submission is not complete",),
        ),
        (
            "repository lane neither performs nor evidences portal action",
            ("No portal action is performed or evidenced by this repository lane",),
        ),
        (
            "portal state remains a human verification gate",
            ("Portal state remains a human verification gate",),
        ),
        (
            "no public Directory availability is claimed",
            ("No public Directory availability is claimed",),
        ),
        (
            "identity verification, logo approval, and submission remain pending",
            ("remain pending human decisions",),
        ),
    ),
    PLUGIN_README_JA_RELATIVE: (
        ("development preview", ("development preview",)),
        (
            "公開Plugins Directoryへ申請・登録・公開されていない",
            ("公開Plugins Directoryへ申請・登録・公開されていません",),
        ),
        ("正式申請は完了していない", ("正式申請は完了していません",)),
        (
            "リポジトリ側で申請ポータルを操作せず証跡もない",
            (
                "このリポジトリ側の作業では申請ポータルを操作しておらず、その操作を示す証跡もありません",
            ),
        ),
        (
            "申請ポータルの状態は人間が確認する",
            ("申請ポータルの状態は人間が確認する必要があります",),
        ),
        ("公開Directoryでの提供を主張しない", ("公開Directoryでの提供は一切主張しません",)),
        (
            "identity verification、logo承認、申請が人間判断待ち",
            ("人間の判断待ちです",),
        ),
    ),
    PLUGIN_README_ZH_HANT_RELATIVE: (
        ("development preview", ("development preview",)),
        (
            "尚未提交、列入或公開於公開Plugins Directory",
            ("尚未提交、列入或公開於",),
        ),
        ("尚未完成正式申請", ("尚未完成向 OpenAI 的正式申請",)),
        (
            "儲存庫端未操作申請入口且沒有操作證據",
            ("本次儲存庫端作業未操作申請入口，也沒有相關操作證據",),
        ),
        (
            "申請入口狀態仍須人工確認",
            ("申請入口的實際狀態仍須由人工確認",),
        ),
        ("不主張任何公開Directory上架", ("不主張任何公開 Directory 上架",)),
        (
            "identity verification、logo核准與申請仍待人工決定",
            ("均仍待人工決定",),
        ),
    ),
}

# External portal state is not observable from this repository lane. Classify
# normalized visible prose by semantic components instead of accumulating
# whole-sentence deny-list phrases. A segment is rejected only when it has a
# portal context, a material draft/submission/review object or action, and a
# current-state predicate. Positive and negative polarity are equally
# unverifiable here.
PORTAL_CONTEXT_PATTERNS = {
    "en": (
        re.compile(
            r"(?<![A-Za-z0-9_])(?:portal|(?:submission|application|review|developer|application[-\s]+review)\s+portal|(?:submission|application)\s+system)(?![A-Za-z0-9_])",
            re.IGNORECASE,
        ),
    ),
    "ja": (
        re.compile(
            r"(?:申請ポータル|提出ポータル|審査ポータル|申請入口|申請画面|申請ページ|申請サイト|申請システム|ポータル)"
        ),
    ),
    "zh_hant": (
        re.compile(
            r"(?:申請入口|提交入口|送審入口|審核入口|申請平台|提交平台|送審平台|申請頁面|入口|平台)"
        ),
    ),
}

PORTAL_STATE_OBJECT_PATTERNS = {
    "en": (
        re.compile(
            r"\b(?:drafts?|(?:saved|pending|existing|application|submission|review)\s+drafts?|pending\s+application|saved\s+application|(?:application|submission|submitted|uploaded)\s+content|materials?|applications?|submissions?|content|nothing)\b",
            re.IGNORECASE,
        ),
    ),
    "ja": (
        re.compile(
            r"(?:下書き|草稿|ドラフト|保存済み|未保存|提出(?:済み)?|未提出|送信(?:済み)?|未送信|申請(?:済み)?|未申請|送審(?:済み|待ち)?|未送審|審査待ち|審査中|申請内容|提出内容|内容|資料|何も)"
        ),
    ),
    "zh_hant": (
        re.compile(
            r"(?:草稿|已儲存草稿|待提交草稿|待送審草稿|待送審|已送審|未送審|提交|已提交|未提交|送出|已送出|未送出|送審|審核中|待審核|申請內容|提交內容|資料|內容|申請|任何)"
        ),
    ),
}

# In the submission-status files, these objects carry their own application
# context even when a sentence omits the noun "portal". This is intentionally
# limited to draft-specific Japanese/Traditional Chinese vocabulary so a
# generic statement such as "This Plugin is not submitted" stays outside the
# external-portal classifier.
PORTAL_IMPLICIT_CONTEXT_PATTERNS = (
    re.compile(r"(?:下書き|草稿|ドラフト)"),
    re.compile(r"(?:申請草稿|待提交草稿|待送審草稿)"),
)

# The portal/system itself is the state object for empty/present/absent
# assertions, so these do not require a separate draft/content noun.
PORTAL_SELF_STATE_PATTERNS = (
    re.compile(
        r"\b(?:portal|system)\s+(?:is|are)\s+(?:not\s+)?(?:present|absent|empty)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:ポータル|入口|画面|ページ|サイト|システム)(?:は|が)?空(?:です|ではありません)"),
    re.compile(r"(?:入口|平台|頁面)(?:是|不是)空的"),
)

PORTAL_STATE_PREDICATE_PATTERNS = {
    "en": (
        re.compile(r"\bthere\s+(?:is|are)\s+(?:no\s+)?", re.IGNORECASE),
        re.compile(r"\b(?:exists?|does\s+not\s+exist)\b", re.IGNORECASE),
        re.compile(
            r"\b(?:is|are)\s+(?:not\s+)?(?:present|absent|empty|pending|approved|rejected)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:has|have|contains?|does\s+not\s+contain|do\s+not\s+contain)\s+(?:no\s+|an?\s+|the\s+|any\s+)?",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:has|have)\s+(?:not\s+|already\s+)?been\s+(?:saved|created|submitted|sent|uploaded|filed|approved|rejected)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:is|are|was|were)\s+(?:not\s+|already\s+)?(?:saved|created|submitted|sent|uploaded|filed|approved|rejected)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:not\s+|already\s+)?(?:saved|created|submitted|sent|uploaded|filed|approved|rejected)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:is|are|was|were)\s+(?:already\s+|not\s+)?under\s+review\b|\b(?:awaiting|queued\s+for)\s+review\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:not\s+)?pending\b", re.IGNORECASE),
    ),
    "ja": (
        re.compile(r"(?:ある|ない|あります|ありません)"),
        re.compile(r"存在(?:する|します|しない|しません|せず)"),
        re.compile(
            r"(?:作成|保存|提出|送信|申請|送審)(?:済み|されています|されていません|された|されていない|していません|していない)"
        ),
        re.compile(r"未(?:保存|提出|送信|申請|送審)"),
        re.compile(r"(?:審査中|審査待ち|送審待ち)"),
        re.compile(r"空(?:です|ではありません)"),
        re.compile(r"含まれて(?:います|いません|いる|いない)"),
        re.compile(r"何も[^。！？；\n]{0,24}(?:提出|送信|申請|送審)[^。！？；\n]{0,12}(?:ていません|していない)"),
    ),
    "zh_hant": (
        re.compile(r"(?:已有|有|沒有|尚未)"),
        re.compile(r"(?:存在|不存在)"),
        re.compile(r"(?:是空的|不是空的)"),
        re.compile(r"(?:已|未)(?:建立|儲存|提交|送出|送審)"),
        re.compile(r"沒有(?:建立|儲存|提交|送出|送審)"),
        re.compile(r"已(?:透過|經由)[^。！？；\n]{0,24}(?:提交|送出|送審)"),
        re.compile(r"(?:審核中|待審核|待送審|待提交)"),
        re.compile(r"(?:包含|不包含)"),
    ),
}

# Safe contexts are applied to one atomic segment only. Explanatory prose is
# skipped only when it has no explicit current-state cue. Future/hypothetical
# prose is skipped only when it has no current-state marker such as already,
# 現在, or 已. This prevents a safe sentence from licensing a later assertion.
PORTAL_REPOSITORY_EVIDENCE_SAFE_PATTERNS = (
    re.compile(
        r"\bno\s+portal\s+action\s+is\s+performed\s+or\s+evidenced\s+by\s+this\s+repository\s+lane\b",
        re.IGNORECASE,
    ),
    re.compile(r"このリポジトリ側の作業では申請ポータルを操作して(?:いません|おらず)"),
    re.compile(r"本次儲存庫端作業未操作申請入口"),
)
PORTAL_HUMAN_GATE_SAFE_PATTERNS = (
    re.compile(r"\bportal\s+state\s+remains\s+a\s+human\s+verification\s+gate\b", re.IGNORECASE),
    re.compile(r"\b(?:final\s+)?portal\s+state\s+must\s+be\s+checked\s+by\s+a\s+human\b", re.IGNORECASE),
    re.compile(r"申請ポータルの状態は人間が確認"),
    re.compile(r"申請入口の実際の状態は人間が確認"),
    re.compile(r"申請入口的實際狀態仍須由人工確認"),
)
PORTAL_EXPLANATORY_SEGMENT_PATTERNS = (
    re.compile(r"\b(?:documentation|schema|field|fixture|example|terminology|phrase|defines?|explains?)\b", re.IGNORECASE),
    re.compile(r"(?:説明|項目|用語|例|テスト|フィクスチャ|文書)"),
    re.compile(r"(?:文件|說明|欄位|詞彙|範例|測試|解釋)"),
)
PORTAL_FUTURE_SEGMENT_PATTERNS = (
    re.compile(r"\b(?:future|may|might|could|after\s+human\s+approval|following\s+human\s+approval)\b", re.IGNORECASE),
    re.compile(r"(?:将来|今後|可能性|承認後|場合)"),
    re.compile(r"(?:未來|可能|核准後|若|如果|之後)"),
)
PORTAL_CURRENT_STATE_CUE_PATTERNS = (
    re.compile(
        r"\b(?:already|currently|now|exists?|present|absent|empty|has\s+no|contains?\s+no|does\s+not\s+contain|has\s+been|was|were|under\s+review|awaiting\s+review|queued\s+for\s+review)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:現在|すでに|既に|済み|存在|(?<!可能性が)あります|ありません|されています|されていません|審査中|審査待ち|空です)"),
    re.compile(r"(?:目前|已有|已(?:建立|儲存|提交|送出|送審)|未(?:建立|儲存|提交|送出|送審)|沒有|存在|審核中|待審核|是空的|不是空的)"),
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
    # Japanese: "申請・登録・公開されていません", "完了していません",
    # "提出していません", "未申請", "一切主張しません". The bounded eater
    # covers a coordinated ・-list but cannot reach back across a positive
    # claim, sentence punctuation, or a connector.
    re.compile(r"[\w・]{0,12}(?:されて|して)?い?ません"),
    re.compile(r"[\w・]{0,12}(?:されて|して)いない"),
    re.compile(r"未(?:申請|承認|提出|公開|完了|提供|掲載|登録)"),
    re.compile(r"[\w・]{0,16}(?:を|は)?(?:一切)?主張(?:しません|しない)"),
    # Traditional Chinese: "尚未提交、列入或公開於", "未在…上架", "不主張…".
    re.compile(r"尚未[\w、]{0,12}"),
    re.compile(r"未(?:在|於)[^\n。，]{0,30}(?:上架|提供|核准|發布)"),
    re.compile(r"不主張[^\n。]{0,20}"),
    re.compile(r"(?:並未|並非|沒有|不會)[\w、]{0,12}"),
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
    # Japanese.
    re.compile(
        r"公開\s*(?:Plugins\s*)?Directory\s*(?:で|から|に|上で)?[^\n。、]{0,12}?"
        r"(?:利用可能|利用でき|提供されてい|入手でき|取得でき|インストールでき|installでき)"
    ),
    re.compile(r"正式公開済み"),
    re.compile(r"申請完了"),
    re.compile(r"承認済み"),
    re.compile(r"上架済み"),
    re.compile(r"(?:掲載|公開|承認|提供)されています"),
    re.compile(r"(?:正式)?申請(?:は|が)?完了しています"),
    # Traditional Chinese.
    re.compile(
        r"可(?:從|在|由|自)[^\n。，]{0,20}公開\s*(?:Plugins\s*)?Directory"
        r"[^\n。，]{0,10}(?:使用|取得|安裝|下載)"
    ),
    re.compile(r"已(?:於|在)[^\n。，]{0,25}Directory[^\n。，]{0,10}(?:提供|上架)"),
    re.compile(r"目前已提供"),
    re.compile(r"已上架"),
    re.compile(r"已提交"),
    re.compile(r"已核准"),
    re.compile(r"正式發布"),
)

# Structural separators used after masking: sentence punctuation, em/en
# dashes, and contrastive connectors in all three languages. Splitting keeps
# gap-based positive patterns from reaching across independent clauses;
# ordinary commas are not split so coordinated negations stay intact.
SEGMENT_SPLIT_PATTERN = re.compile(
    r"[.!?;:\n。！？；：]"
    r"|[—–]"
    r"|(?<![A-Za-z])(?:but|however|yet|although|though|whereas|nevertheless)(?![A-Za-z])"
    r"|ですが|だが|しかし|ただし|一方で|一方|とはいえ|ものの|けれども|けれど|にもかかわらず"
    r"|但是|但|然而|不過|可是|卻|雖然|儘管",
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

CJK_CHARACTER_PATTERN = re.compile(
    r"[぀-ヿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ]"
)


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

    Lines are joined with a space, except between two CJK characters where a
    rendered soft break introduces no visible gap. Blank lines, headings,
    list items, blockquotes, and thematic breaks all start a new block and
    are never joined across.
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
            if CJK_CHARACTER_PATTERN.match(left[-1]) and CJK_CHARACTER_PATTERN.match(
                right[0]
            ):
                joined = left + right
            else:
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
    visible = MD_SHORTCUT_LINK_PATTERN.sub(lambda m: m.group(1), visible)

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


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"File does not exist: {path}") from exc
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
        url_only = not re.search(r"[\w一-龠ぁ-んァ-ン]", residue)

        for raw_url in targets:
            url = raw_url.rstrip(".,;)。、，：:")
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
            and stripped_line.endswith((":", "："))
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


def portal_atomic_segments(visible: str) -> list[str]:
    """Split visible prose without allowing one safe sentence to mask another."""
    return [
        " ".join(segment.split())
        for segment in SEGMENT_SPLIT_PATTERN.split(visible)
        if segment.strip()
    ]


def portal_patterns_match(
    patterns_by_language: dict[str, tuple[re.Pattern[str], ...]], segment: str
) -> bool:
    return any(
        pattern.search(segment)
        for patterns in patterns_by_language.values()
        for pattern in patterns
    )


def portal_segment_is_safe(segment: str) -> bool:
    if any(
        pattern.search(segment)
        for pattern in (
            *PORTAL_REPOSITORY_EVIDENCE_SAFE_PATTERNS,
            *PORTAL_HUMAN_GATE_SAFE_PATTERNS,
        )
    ):
        return True

    has_current_state_cue = any(
        pattern.search(segment) for pattern in PORTAL_CURRENT_STATE_CUE_PATTERNS
    )
    if not has_current_state_cue and any(
        pattern.search(segment) for pattern in PORTAL_EXPLANATORY_SEGMENT_PATTERNS
    ):
        return True
    if not has_current_state_cue and any(
        pattern.search(segment) for pattern in PORTAL_FUTURE_SEGMENT_PATTERNS
    ):
        return True
    return False


def portal_segment_asserts_external_state(segment: str) -> bool:
    if portal_segment_is_safe(segment):
        return False
    has_portal_context = portal_patterns_match(PORTAL_CONTEXT_PATTERNS, segment) or any(
        pattern.search(segment) for pattern in PORTAL_IMPLICIT_CONTEXT_PATTERNS
    )
    has_state_object = portal_patterns_match(PORTAL_STATE_OBJECT_PATTERNS, segment) or any(
        pattern.search(segment) for pattern in PORTAL_SELF_STATE_PATTERNS
    )
    return (
        has_portal_context
        and has_state_object
        and portal_patterns_match(PORTAL_STATE_PREDICATE_PATTERNS, segment)
    )


def validate_portal_state_assertions(root: Path, errors: list[str]) -> None:
    """Reject assertions about external portal contents or submission state."""
    for relative in PORTAL_STATE_SCAN_FILES:
        path = root / relative
        if not path.is_file():
            continue
        visible = markdown_visible_text(path.read_text(encoding="utf-8"))
        for segment in portal_atomic_segments(visible):
            if portal_segment_asserts_external_state(segment):
                errors.append(
                    f"{relative} must not assert unverified external portal state: "
                    f"{segment!r}."
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

    if EXPECTED_MANIFEST_VERSION not in text:
        errors.append(
            f"release-notes.md must record the current Plugin version "
            f"{EXPECTED_MANIFEST_VERSION!r}."
        )


def validate_status_claims(root: Path, errors: list[str]) -> None:
    """Reject any product or submission status claim whose own span is not
    explicitly negated.

    Negation binds to the specific claim: explicitly negated status spans are
    masked out first, and every positive claim left anywhere in the remaining
    text fails. A negation earlier in the sentence therefore never licenses a
    later claim — "No submission has occurred — this Plugin is published."
    fails on its second span, in any of English, Japanese, or Traditional
    Chinese, across em dashes, commas, and contrastive connectors.
    """
    for relative in CLAIM_SCAN_FILES:
        path = root / relative
        if not path.is_file():
            continue
        visible = markdown_visible_text(path.read_text(encoding="utf-8"))
        masked = mask_negated_status_spans(visible)
        for segment in SEGMENT_SPLIT_PATTERN.split(masked):
            normalized = " ".join(segment.split())
            if not normalized:
                continue
            for pattern in POSITIVE_STATUS_PATTERNS:
                match = pattern.search(segment)
                if match:
                    errors.append(
                        f"{relative} must not claim public Directory availability, "
                        f"or submitted, published, approved, released, or stable "
                        f"status: {normalized!r} asserts "
                        f"{' '.join(match.group(0).split())!r}."
                    )


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
    print(f"- Plugin version: {EXPECTED_MANIFEST_VERSION} (unchanged)")
    print("- capabilities: Read only")
    print("- submission to OpenAI: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
