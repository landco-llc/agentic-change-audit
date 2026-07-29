#!/usr/bin/env python3
"""Validate the skills-only Codex Plugin foundation without modifying it."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, NamedTuple

PLUGIN_RELATIVE = "plugins/agentic-change-audit"
MANIFEST_RELATIVE = f"{PLUGIN_RELATIVE}/.codex-plugin/plugin.json"
MARKETPLACE_RELATIVE = ".agents/plugins/marketplace.json"
SKILL_RELATIVE = f"{PLUGIN_RELATIVE}/skills/agentic-change-audit"
SYNC_SCRIPT_RELATIVE = "scripts/sync-codex-plugin.py"
SKILL_VALIDATOR_RELATIVE = "scripts/validate-skill.py"
README_NAMES = ("README.md", "README.ja.md", "README.zh-Hant.md")

FORBIDDEN_MANIFEST_KEYS = ("mcpServers", "apps", "hooks")
FORBIDDEN_VISUAL_KEYS = (
    "icon",
    "icons",
    "logo",
    "logoUrl",
    "assets",
    "screenshots",
    "banner",
)
FORBIDDEN_COMPONENT_BASENAMES = frozenset(
    {
        ".app.json",
        ".mcp.json",
        "mcp.json",
        "hooks",
        "hooks.json",
        "connector",
        "connectors",
        "server",
        "servers",
    }
)

EXPECTED_MANIFEST_KEYS = {
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "skills",
    "interface",
}
EXPECTED_AUTHOR_KEYS = {"name", "url"}
EXPECTED_INTERFACE_KEYS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "capabilities",
    "websiteURL",
    "defaultPrompt",
}
EXPECTED_PLUGIN_TOP_LEVEL = {
    ".codex-plugin",
    "NOTICE",
    "README.md",
    "README.ja.md",
    "README.zh-Hant.md",
    "skills",
}

EXPECTED_NAME = "agentic-change-audit"
EXPECTED_VERSION = "0.1.0-dev.3"
EXPECTED_DESCRIPTION = (
    "Evidence-first audits for AI-generated and human software changes "
    "before merge, release, or deployment."
)
EXPECTED_AUTHOR_NAME = "L&Co.LLC"
EXPECTED_AUTHOR_URL = "https://github.com/landco-llc"
EXPECTED_HOMEPAGE = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_REPOSITORY = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_KEYWORDS = [
    "ai-agents",
    "agent-skills",
    "software-audit",
    "change-audit",
    "code-review",
    "release-readiness",
]
EXPECTED_SKILLS_PATH = "./skills/"

EXPECTED_DISPLAY_NAME = "Agentic Change Audit"
EXPECTED_SHORT_DESCRIPTION = "Audit software changes with evidence before merge or release."
EXPECTED_LONG_DESCRIPTION = (
    "Review fixed software changes, verification evidence, remaining risks, "
    "and required human checks before merge, release, or deployment."
)
EXPECTED_DEVELOPER_NAME = "L&Co.LLC"
EXPECTED_CATEGORY = "Productivity"
EXPECTED_CAPABILITIES = ["Read"]
EXPECTED_WEBSITE_URL = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_DEFAULT_PROMPT = [
    "Audit the current repository change without modifying files. Fix the "
    "result to the current base and target HEAD.",
    "Audit this AI-built application as a release candidate and identify "
    "missing evidence and required human checks.",
    "Re-audit the approved remediation against the previous findings and "
    "authorized scope.",
]

EXPECTED_MARKETPLACE_NAME = "agentic-change-audit"
EXPECTED_MARKETPLACE_DISPLAY_NAME = "Agentic Change Audit"
EXPECTED_MARKETPLACE_ENTRY_NAME = "agentic-change-audit"
EXPECTED_MARKETPLACE_SOURCE_TYPE = "local"
EXPECTED_MARKETPLACE_SOURCE_PATH = "./plugins/agentic-change-audit"
EXPECTED_MARKETPLACE_INSTALLATION_POLICY = "AVAILABLE"
EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY = "ON_INSTALL"
EXPECTED_MARKETPLACE_CATEGORY = "Productivity"
EXPECTED_MARKETPLACE_KEYS = {"name", "interface", "plugins"}
EXPECTED_MARKETPLACE_INTERFACE_KEYS = {"displayName"}
EXPECTED_MARKETPLACE_ENTRY_KEYS = {"name", "source", "policy", "category"}
EXPECTED_MARKETPLACE_SOURCE_KEYS = {"source", "path"}
EXPECTED_MARKETPLACE_POLICY_KEYS = {"installation", "authentication"}

FORBIDDEN_HUMAN_IDENTITY_FRAGMENTS = ("landco-llc", "l&co")
STALE_README_MARKERS = (
    "landco-llc-open-source",
    "L&Co.LLC Open Source",
    "L&Co. Open Source",
    "0.1.0-dev.2",
)
REQUIRED_README_MARKERS = (
    "Agentic Change Audit marketplace",
    EXPECTED_VERSION,
)

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
PLUGIN_DEVELOPMENT_VERSION_PATTERN = re.compile(
    r"(?<![0-9A-Za-z])"
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"-dev\.(?:0|[1-9][0-9]*)(?:[.-][0-9A-Za-z-]+)*"
    r"(?![0-9A-Za-z-])",
    re.IGNORECASE,
)
README_CLAUSE_SPLIT_PATTERN = re.compile(
    r"(?:[!?。！？;；]+|\.(?=\s|$))",
    re.IGNORECASE,
)
README_MARKDOWN_FENCE_OPEN_PATTERN = re.compile(
    r"^\s{0,3}(?P<fence>`{3,}|~{3,})(?P<info>.*)$"
)
README_MARKDOWN_FENCE_CLOSE_PATTERN = re.compile(
    r"^\s{0,3}(?P<fence>`{3,}|~{3,})\s*$"
)
README_MARKDOWN_HEADING_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(?P<text>.*)$")
README_MARKDOWN_SETEXT_PATTERN = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")
README_MARKDOWN_LIST_ITEM_PATTERN = re.compile(
    r"^\s*(?:[-+*]|\d+[.)])\s+(?P<text>.*)$"
)
README_MARKDOWN_BLOCKQUOTE_PATTERN = re.compile(
    r"^\s{0,3}(?P<prefix>(?:>\s*)+)(?P<text>.*)$"
)
README_MARKDOWN_THEMATIC_BREAK_PATTERN = re.compile(
    r"^\s{0,3}(?:(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,})$"
)
README_MARKDOWN_REFERENCE_DEFINITION_PATTERN = re.compile(
    r"^\s{0,3}\[(?P<label>[^\]\n]+)\]:\s*"
    r"(?P<destination><[^>\n]*>|\S+)"
    r"(?:\s+(?P<title>\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*$"
)
README_DIAGNOSTIC_EXCERPT_LENGTH = 720
README_GATE_CONTEXT_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])phase\s*c(?![A-Za-z0-9])|desktop\s+gate|"
    r"neutral[- ]marketplace identity|"
    r"neutral identity|中立(?:な)?\s*marketplace\s*identity|"
    r"中性\s*marketplace\s*identity|桌面\s*gate|"
    r"(?:renamed|current)\s+(?:agentic change audit\s+)?marketplace|"
    r"名称変更後の?\s*agentic change audit\s*marketplace|"
    r"(?:更名後|目前|現行|現在)\s*(?:的)?\s*marketplace",
    re.IGNORECASE,
)
README_VERIFIED_ACTION_PATTERN = re.compile(
    r"marketplace(?:\s+(?:registration|discovery|install(?:ation)?))?|"
    r"\b(?:desktop|registration|discovery|install(?:ation)?|invocation|"
    r"explicit invocation|working[- ]tree(?: non-mutation)?)\b|"
    r"marketplace登録|marketplaceの?登録|登録|発見|install|インストール|"
    r"明示呼び出し|明示的?呼び出し|working\s*tree[^。.!?\n]{0,24}非変更|"
    r"marketplace\s*註冊|註冊|探索|安裝|明確呼叫|明確叫用|"
    r"工作樹[^。.!?\n]{0,24}未變更",
    re.IGNORECASE,
)
README_CURRENT_IDENTITY_CUE_PATTERN = re.compile(
    rf"{re.escape(EXPECTED_VERSION)}|neutral[- ]marketplace identity|"
    r"neutral identity|renamed|current|present(?:-day)?|now|"
    r"agentic change audit marketplace|"
    r"現行|現在|名称変更後|中立|中性\s*marketplace\s*identity|"
    r"更名後|目前|現已",
    re.IGNORECASE,
)
README_POSITIVE_GATE_STATUS_PATTERN = re.compile(
    r"\b(?:pass(?:ed|es|ing)?|complet(?:e|ed)|verif(?:y|ies|ied|ication complete)|"
    r"validat(?:ed|ion complete)|approv(?:ed|al complete)|"
    r"success(?:ful|fully)?|succeed(?:ed|s|ing)?|ready)\b|"
    r"合格(?:済み)?|完了(?:済み|しました)?|検証済み|確認済み|"
    r"承認済み|承認されました|成功(?:しました)?|"
    r"(?:已|現已)?(?:通過|完成|驗證|驗證完成|驗證完畢|核准|批准|成功)|"
    r"已獲核准",
    re.IGNORECASE,
)
README_NEGATIVE_STATE_STATUS_PATTERN = re.compile(
    r"\b(?:not|no longer)\s+(?:unverified|incomplete|pending|unsuccessful)\b|"
    r"(?:未検証|未完了|保留中|不成功)(?:ではない|ではありません)|"
    r"(?:並非|不是|不再)(?:未驗證|未完成|待處理|未成功)",
    re.IGNORECASE,
)
README_NEGATIVE_STATE_PREDICATE_PATTERN = re.compile(
    r"\b(?:unverified|incomplete|pending|unsuccessful)\b|"
    r"未検証|未完了|保留中|不成功|"
    r"未驗證|未完成|待處理|未成功",
    re.IGNORECASE,
)
README_STATUS_NEGATION_BEFORE_PATTERN = re.compile(
    r"(?:\b(?:not|never|no)\s+(?:been\s+)?|"
    r"\b(?:has|have|had|is|are|was|were|does|do|did|must|should|may)\s+"
    r"not\s+(?:have\s+|been\s+|be\s+)?|"
    r"\b(?:cannot|can't)\s+(?:be\s+)?|"
    r"(?:未|まだ|尚未|並未|不得|不可|不曾|不能|不)\s*)$",
    re.IGNORECASE,
)
README_STATUS_COMPOUND_NEGATION_BEFORE_PATTERN = re.compile(
    r"\bnot\s+yet\s+(?:been\s+|successfully\s+)?$|"
    r"(?:尚未|並未|未|まだ)\s*"
    r"(?:獲得|得到|驗證|驗證完畢|検証|確認|承認|成功|通過|合格)?\s*$",
    re.IGNORECASE,
)
README_STATUS_PENDING_AFTER_PATTERN = re.compile(
    r"^\s*(?:not\b|ではありません|ではない|ではなく|"
    r"していません|していない|しておらず|とはいえない|"
    r"並非|不代表|不表示|不保證)",
    re.IGNORECASE,
)
README_STATUS_NON_CURRENT_BEFORE_PATTERN = re.compile(
    r"\b(?:will|would|shall|must|should|may)\s+(?:later\s+)?"
    r"(?:be\s+)?(?:re[- ]?)?$|"
    r"\b(?:when|if|once|after)\b[^.!?。！？;；]*$|"
    r"(?:将来|今後|次回|予定|再(?:検証|確認|実施|試験)|待ち)[^。！？;；]*$|"
    r"(?:須於未來|未來|將|重新|仍待)[^。！？;；]*$",
    re.IGNORECASE,
)
README_STATUS_NON_CURRENT_AFTER_PATTERN = re.compile(
    r"^\s*(?:in the future\b|later\b|when\b|if\b|"
    r"(?:になる|となる)?予定|待ち|"
    r"未來|之後|稍後|仍待)",
    re.IGNORECASE,
)
README_NON_ASSERTION_CUE_PATTERN = re.compile(
    r"\b(?:does not|doesn't|do not|don't|did not|never)\s+"
    r"(?:assert|claim|state|represent|mean)\b|"
    r"\b(?:is|are|was|were)\s+not\s+"
    r"(?:asserting|claiming|stating|representing)\b|"
    r"\b(?:must|should|is expected to|is intended to)\s+"
    r"(?:be\s+)?(?:reject(?:ed)?|forbid(?:den)?|prohibit(?:ed)?)\b|"
    r"\b(?:rejects?|forbids?|prohibits?)\s+(?:the\s+)?claim\b|"
    r"\b(?:forbidden|prohibited|invalid)\s+(?:wording|claim|example)\b|"
    r"\b(?:forbidden|prohibited)\b|"
    r"\b(?:is|are|was|were)\s+(?:an?\s+)?"
    r"(?:forbidden|prohibited|invalid)"
    r"(?:\s+(?:wording|claim|example))?\b|"
    r"\b(?:does not|doesn't|do not|don't)\s+represent\s+"
    r"(?:the\s+)?current\s+state\b|"
    r"\bnot\s+(?:the\s+)?current\s+state\b|\bis not a claim\b|"
    r"\b(?:quoted|shown)\s+only\s+to\s+explain\s+"
    r"(?:the\s+)?rejection\s+rule\b|"
    r"主張(?:してい(?:ない|ません)|し(?:ない|ません))|"
    r"意味し(?:ない|ません)|認め(?:ない|ません)|"
    r"拒否(?:する|される|されます|されるべき|される予定)|"
    r"禁止(?:する|される|されます|用語|文言)?|"
    r"無効(?:な)?(?:例|主張|文言|表現)?|"
    r"現在(?:の)?(?:状態|state)(?:を示し(?:ない|ません)|"
    r"では(?:ない|ありません))|"
    r"拒否規則を説明するため(?:だけ|のみ)?の?(?:引用|例)|"
    r"並未主張|不主張|不代表|不表示目前狀態|並非目前狀態|"
    r"(?:必須|必需|預期(?:會)?|應)(?:被)?拒絕|"
    r"拒絕規則|拒絕|禁止用語|禁止(?:的)?(?:說法|文言|範例)|"
    r"不得(?:主張|作為目前結果)|"
    r"無效(?:範例|說法|主張|例)?|"
    r"僅用於說明拒絕規則",
    re.IGNORECASE,
)
README_REPORTING_MENTION_PATTERN = re.compile(
    r"\b(?:wording|phrase|input|example|claim|quote|quoted\s+text|"
    r"code\s+example)\b|"
    r"文言|表現|語句|入力|例|主張|引用|code例|"
    r"用語|說法|輸入|範例|主張|引用|程式碼範例",
    re.IGNORECASE,
)
README_REPORTING_SUBJECT_PATTERN = re.compile(
    r"\b(?:fixture|test(?:\s+case)?|example|documentation|document|guide|report|"
    r"wording|phrase|input|quote|quoted\s+text|code\s+example)\b|"
    r"fixture|テスト|例|文書|文言|入力|引用|code例|報告|"
    r"fixture|測試|範例|文件|用語|說法|輸入|引用|程式碼範例|報告",
    re.IGNORECASE,
)
README_REPORTING_VERB_PATTERN = re.compile(
    r"\b(?:records?|reports?|quotes?|contains?|describes?|names?|mentions?|"
    r"discusses?|shows?|uses?|appears?|says?|archives?|preserves?|stores?|saves?|"
    r"rejects?|forbids?|prohibits?)\b|"
    r"記録|記載|報告|説明|保存|言及|"
    r"引用(?:する|します|した|して)|扱|現れ|拒否|禁止|"
    r"記錄|描述|報告|說明|保存|引用(?:為|作為|於|在)|提及|出現|拒絕|禁止",
    re.IGNORECASE,
)
README_ASSERTIVE_REPORTING_ROLE_PATTERN = re.compile(
    r"\bas\s+(?:the\s+)?current\s+(?:result|state|status|outcome)\b|"
    r"\b(?:records?|reports?|shows?|uses?)\s+(?:the\s+)?current\s+"
    r"(?:result|state|status|outcome)\b|"
    r"\b(?:represents?|shows?|states?|confirms?)\s+(?:the\s+)?current\s+"
    r"(?:result|state|status|outcome)\b|"
    r"現在(?:の)?(?:結果|状態|state)(?:を)?(?:示します|表します|意味します)|"
    r"現在(?:の)?(?:結果|状態|state)(?:です|である)|"
    r"現在(?:の)?(?:結果|状態|state)として|"
    r"(?<!不)(?:表示|代表|確認)(?:目前|現在)(?:的)?(?:結果|狀態|status)|"
    r"(?:是|作為)(?:目前|現在)(?:的)?(?:結果|狀態|status)",
    re.IGNORECASE,
)
README_NON_ASSERTION_AFTER_PATTERN = re.compile(
    r"^\s*(?:without\s+(?:asserting|claiming)|"
    r"is\s+(?:forbidden|prohibited|invalid)|must\s+be\s+rejected|"
    r"(?:という)?主張をし(?:ない|ません)|禁止(?:される)?|拒否(?:される)?|"
    r"現在(?:の)?状態を示し(?:ない|ません)|"
    r"並未主張|不主張|禁止|拒絕|不表示目前狀態|不代表)",
    re.IGNORECASE,
)
README_CONTRAST_PATTERN = re.compile(
    r"\b(?:but|however|rather|instead|yet|while|whereas)\b|"
    r"(?:ですが|ますが|ましたが|でしたが|ていますが|だが|が[,、，]|"
    r"しかし|ではなく|一方|而是|但是|然而|但|卻)",
    re.IGNORECASE,
)
README_INDEPENDENT_CLAIM_BOUNDARY_PATTERN = re.compile(
    r"[,，、]\s*(?:(?:and|then|also|the\s+current|currently)\b|"
    r"現在|現行|目前|並且|而且)|"
    r"\band\s+(?:this|that|the\s+current|current|another|different|"
    r"unrelated|the\s+fixture|the\s+example)\b",
    re.IGNORECASE,
)
README_EXPLANATORY_SUBJECT_PATTERN = re.compile(
    r"\b(?:readme|document|wording|phrase|claim|fixture|example|"
    r"test case|code example|quoted text|quotation)\b|"
    r"文書|文言|表現|語句|主張|fixture|例|code例|引用|"
    r"文件|用語|說法|主張|範例|程式碼範例",
    re.IGNORECASE,
)
README_TRAILING_NON_ASSERTION_LINK_PATTERN = re.compile(
    r"^\s*[\"'”’」』）》）】]*\s*"
    r"(?:(?:だと|とは|という(?:文言|主張)?(?:は)?|を|が|は|と|"
    r"的說法|這項主張|this claim|that claim))?"
    r"\s*[,、，:]?\s*$",
    re.IGNORECASE,
)
README_HISTORICAL_CUE_PATTERN = re.compile(
    r"\b(?:earlier|previous|prior|old|historical)\b|以前|過去|旧|先前|舊",
    re.IGNORECASE,
)
README_INVALIDATION_CUE_PATTERN = re.compile(
    r"\b(?:superseded|invalid|expired|no longer valid|does not verify)\b|"
    r"失効|無効|検証するものではありません|已失效|失效|不能驗證",
    re.IGNORECASE,
)
README_POLARITY_REVERSAL_BEFORE_PATTERN = re.compile(
    r"\b(?:is|was)\s+not\s+(?:true|correct)\s+that\b|"
    r"\b(?:cannot|can't)\s+(?:say|claim|state)\b|"
    r"(?:とはいえません|とは言えません|とはいえない|とは言えない)|"
    r"(?:不能|不可)\s*(?:say|claim|state|說|声称|聲稱|主張)",
    re.IGNORECASE,
)
README_POLARITY_REVERSAL_AFTER_PATTERN = re.compile(
    r"\b(?:is|was)\s+(?:false|incorrect|wrong)\b|"
    r"(?:という)?(?:説明|記述|主張)(?:は|が)?"
    r"(?:誤り|間違い|正しくない|正しくありません|不正確)|"
    r"(?:とはいえません|とは言えません|とはいえない|とは言えない)|"
    r"(?:這|該)?(?:說法|描述|主張)(?:是|並不)?(?:錯誤|不正確)",
    re.IGNORECASE,
)
README_ANAPHORIC_STATUS_PREFIX_PATTERN = re.compile(
    r"\s*(?:(?:but|however|instead|yet|and|then|also|"
    r"it|this|that|they|both|which|is|are|was|were|"
    r"has|have|had|now|currently)\b[\s,，、:：]*|"
    r"(?:しかし|ではなく|一方|それ|これは|その結果|そして|また|も|"
    r"は|が|但是|然而|而是|但|卻|其|它|這|該|並且|而且|現已|已|也)"
    r"[\s,，、:：]*|"
    r"(?:English|日本語|中文)?\s*(?:status|result|outcome|状態|結果|狀態)"
    r"[\s,，、:：]*)*",
    re.IGNORECASE,
)


class ReadmeMarkdownSpan(NamedTuple):
    kind: str
    source_start: int
    source_end: int
    text: str
    children: tuple["ReadmeMarkdownSpan", ...]


class ReadmeMarkdownBlock(NamedTuple):
    block_id: int
    kind: str
    source_start: int
    source_end: int
    spans: tuple[ReadmeMarkdownSpan, ...]


class ReadmeSourceLine(NamedTuple):
    text: str
    source_start: int
    source_end: int


class ReadmeVisibleSpan(NamedTuple):
    kind: str
    start: int
    end: int
    source_start: int
    source_end: int


class ReadmeBlock(NamedTuple):
    block_id: int
    kind: str
    source_start: int
    source_end: int
    text: str
    spans: tuple[ReadmeVisibleSpan, ...]


class ReadmeClaimClause(NamedTuple):
    block_id: int
    block_kind: str
    block_text: str
    source_start: int
    source_end: int
    readiness_context: str
    clause_id: int
    text: str
    spans: tuple[ReadmeVisibleSpan, ...]


class ReadmeClaimOccurrence(NamedTuple):
    block_id: int
    block_kind: str
    block_text: str
    readiness_context: str
    clause_id: int
    clause: str
    status_start: int
    status_end: int
    claim_start: int
    claim_end: int
    quote_span: tuple[int, int] | None
    inline_code_span: tuple[int, int] | None
    link_label_span: tuple[int, int] | None
    emphasis_visible_span: tuple[int, int] | None

    @property
    def before(self) -> str:
        return self.clause[self.claim_start : self.status_start]

    @property
    def after(self) -> str:
        return self.clause[self.status_end : self.claim_end]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the skills-only Codex Plugin foundation."
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    return parser.parse_args()


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


def validate_semver(value: str) -> None:
    if not isinstance(value, str) or not SEMVER_PATTERN.fullmatch(value):
        raise ValueError(f"Version is not valid ASCII SemVer: {value!r}")


def contains_forbidden_keys(value: Any, forbidden: tuple[str, ...], path: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, sub_value in value.items():
            if key in forbidden:
                found.append(f"{path}.{key}" if path else key)
            found.extend(contains_forbidden_keys(sub_value, forbidden, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(contains_forbidden_keys(item, forbidden, f"{path}[{index}]"))
    return found


def check_exact(errors: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        errors.append(f"plugin.json {label} must equal {expected!r}; found {actual!r}.")


def check_key_set(errors: list[str], label: str, actual: set[str], expected: set[str]) -> None:
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        errors.append(f"{label} keys mismatch; missing={missing}, extra={extra}")


def iter_string_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_string_values(item)


def validate_company_neutral_value(errors: list[str], label: str, value: Any) -> None:
    """Reject company identity only in structurally human-facing fields.

    Legal identity and technical GitHub URL fields are validated separately and
    intentionally never passed to this function.
    """
    for text in iter_string_values(value):
        normalized = text.casefold()
        for fragment in FORBIDDEN_HUMAN_IDENTITY_FRAGMENTS:
            if fragment in normalized:
                errors.append(
                    f"{label} must remain company-neutral; found {fragment!r}."
                )


def validate_manifest(root: Path, errors: list[str]) -> None:
    manifest_path = root / MANIFEST_RELATIVE
    try:
        manifest = load_json(manifest_path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(manifest, dict):
        errors.append("plugin.json must be a JSON object.")
        return

    check_key_set(errors, "plugin.json top-level", set(manifest), EXPECTED_MANIFEST_KEYS)

    check_exact(errors, "name", manifest.get("name"), EXPECTED_NAME)
    actual_version = manifest.get("version")
    check_exact(errors, "version", actual_version, EXPECTED_VERSION)
    try:
        validate_semver(actual_version)
    except ValueError as exc:
        errors.append(str(exc))
    check_exact(errors, "description", manifest.get("description"), EXPECTED_DESCRIPTION)
    check_exact(errors, "homepage", manifest.get("homepage"), EXPECTED_HOMEPAGE)
    check_exact(errors, "repository", manifest.get("repository"), EXPECTED_REPOSITORY)
    check_exact(errors, "license", manifest.get("license"), EXPECTED_LICENSE)
    check_exact(errors, "skills", manifest.get("skills"), EXPECTED_SKILLS_PATH)
    check_exact(errors, "keywords", manifest.get("keywords"), EXPECTED_KEYWORDS)

    author = manifest.get("author")
    if not isinstance(author, dict):
        errors.append("plugin.json 'author' must be an object.")
    else:
        check_key_set(errors, "plugin.json author", set(author), EXPECTED_AUTHOR_KEYS)
        check_exact(errors, "author.name", author.get("name"), EXPECTED_AUTHOR_NAME)
        check_exact(errors, "author.url", author.get("url"), EXPECTED_AUTHOR_URL)

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        errors.append("plugin.json 'interface' must be an object.")
    else:
        check_key_set(errors, "plugin.json interface", set(interface), EXPECTED_INTERFACE_KEYS)
        check_exact(
            errors, "interface.displayName", interface.get("displayName"), EXPECTED_DISPLAY_NAME
        )
        check_exact(
            errors,
            "interface.shortDescription",
            interface.get("shortDescription"),
            EXPECTED_SHORT_DESCRIPTION,
        )
        check_exact(
            errors,
            "interface.longDescription",
            interface.get("longDescription"),
            EXPECTED_LONG_DESCRIPTION,
        )
        check_exact(
            errors, "interface.developerName", interface.get("developerName"), EXPECTED_DEVELOPER_NAME
        )
        check_exact(errors, "interface.category", interface.get("category"), EXPECTED_CATEGORY)
        check_exact(
            errors, "interface.capabilities", interface.get("capabilities"), EXPECTED_CAPABILITIES
        )
        check_exact(errors, "interface.websiteURL", interface.get("websiteURL"), EXPECTED_WEBSITE_URL)
        check_exact(
            errors, "interface.defaultPrompt", interface.get("defaultPrompt"), EXPECTED_DEFAULT_PROMPT
        )

        for label, value in (
            ("plugin.json name", manifest.get("name")),
            ("plugin.json description", manifest.get("description")),
            ("plugin.json keywords", manifest.get("keywords")),
            ("plugin.json interface.displayName", interface.get("displayName")),
            ("plugin.json interface.shortDescription", interface.get("shortDescription")),
            ("plugin.json interface.longDescription", interface.get("longDescription")),
            ("plugin.json interface.defaultPrompt", interface.get("defaultPrompt")),
        ):
            validate_company_neutral_value(errors, label, value)

    forbidden = contains_forbidden_keys(manifest, FORBIDDEN_MANIFEST_KEYS, "")
    for finding in forbidden:
        errors.append(f"plugin.json must not contain forbidden key: {finding}")

    visual = contains_forbidden_keys(manifest, FORBIDDEN_VISUAL_KEYS, "")
    for finding in visual:
        errors.append(f"plugin.json must not contain a visual asset field: {finding}")


def validate_plugin_tree_contract(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    if not plugin_root.is_dir():
        errors.append(f"Plugin root is missing: {plugin_root}")
        return

    top_level = {entry.name for entry in plugin_root.iterdir()}
    if top_level != EXPECTED_PLUGIN_TOP_LEVEL:
        missing = sorted(EXPECTED_PLUGIN_TOP_LEVEL - top_level)
        extra = sorted(top_level - EXPECTED_PLUGIN_TOP_LEVEL)
        errors.append(
            f"Plugin root top-level entries mismatch; missing={missing}, extra={extra}"
        )

    codex_plugin_dir = plugin_root / ".codex-plugin"
    if codex_plugin_dir.is_dir():
        entries = sorted(entry.name for entry in codex_plugin_dir.iterdir())
        if entries != ["plugin.json"]:
            errors.append(f".codex-plugin must contain only plugin.json; found: {entries}")
    else:
        errors.append(f".codex-plugin directory is missing: {codex_plugin_dir}")

    skills_dir = plugin_root / "skills"
    if skills_dir.is_dir():
        entries = sorted(entry.name for entry in skills_dir.iterdir())
        if entries != ["agentic-change-audit"]:
            errors.append(
                "skills/ must contain exactly one directory, agentic-change-audit; "
                f"found: {entries}"
            )
    else:
        errors.append(f"skills directory is missing: {skills_dir}")


def validate_marketplace(root: Path, errors: list[str]) -> None:
    marketplace_path = root / MARKETPLACE_RELATIVE
    try:
        marketplace = load_json(marketplace_path)
    except ValueError as exc:
        errors.append(str(exc))
        return

    if not isinstance(marketplace, dict):
        errors.append("marketplace.json must be a JSON object.")
        return

    check_key_set(
        errors,
        "marketplace.json top-level",
        set(marketplace),
        EXPECTED_MARKETPLACE_KEYS,
    )

    if marketplace.get("name") != EXPECTED_MARKETPLACE_NAME:
        errors.append(f"marketplace.json 'name' must be {EXPECTED_MARKETPLACE_NAME!r}.")
    validate_company_neutral_value(
        errors, "marketplace.json name", marketplace.get("name")
    )

    interface = marketplace.get("interface")
    if (
        not isinstance(interface, dict)
        or interface.get("displayName") != EXPECTED_MARKETPLACE_DISPLAY_NAME
    ):
        errors.append(
            "marketplace.json interface.displayName must be "
            f"{EXPECTED_MARKETPLACE_DISPLAY_NAME!r}."
        )
    if isinstance(interface, dict):
        check_key_set(
            errors,
            "marketplace.json interface",
            set(interface),
            EXPECTED_MARKETPLACE_INTERFACE_KEYS,
        )
        validate_company_neutral_value(
            errors,
            "marketplace.json interface.displayName",
            interface.get("displayName"),
        )

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        errors.append("marketplace.json 'plugins' must contain exactly one entry.")
        return

    entry = plugins[0]
    if not isinstance(entry, dict):
        errors.append("marketplace.json plugin entry must be an object.")
        return

    check_key_set(
        errors,
        "marketplace.json plugin entry",
        set(entry),
        EXPECTED_MARKETPLACE_ENTRY_KEYS,
    )

    if entry.get("name") != EXPECTED_MARKETPLACE_ENTRY_NAME:
        errors.append(
            f"marketplace.json entry 'name' must be {EXPECTED_MARKETPLACE_ENTRY_NAME!r}."
        )
    validate_company_neutral_value(
        errors, "marketplace.json entry name", entry.get("name")
    )

    source = entry.get("source")
    if not isinstance(source, dict):
        errors.append("marketplace.json entry 'source' must be an object.")
    else:
        check_key_set(
            errors,
            "marketplace.json plugin entry source",
            set(source),
            EXPECTED_MARKETPLACE_SOURCE_KEYS,
        )
        if source.get("source") != EXPECTED_MARKETPLACE_SOURCE_TYPE:
            errors.append(
                "marketplace.json entry source.source must be "
                f"{EXPECTED_MARKETPLACE_SOURCE_TYPE!r}."
            )
        path_value = source.get("path")
        if path_value != EXPECTED_MARKETPLACE_SOURCE_PATH:
            errors.append(
                "marketplace.json entry source.path must be "
                f"{EXPECTED_MARKETPLACE_SOURCE_PATH!r}."
            )
        elif not path_value.startswith("./"):
            errors.append("marketplace.json entry source.path must begin with './'.")
        else:
            candidate = (root / path_value.removeprefix("./")).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                errors.append(
                    "marketplace.json entry source.path escapes the repository root."
                )

    policy = entry.get("policy")
    if not isinstance(policy, dict):
        errors.append("marketplace.json entry 'policy' must be an object.")
    else:
        check_key_set(
            errors,
            "marketplace.json plugin entry policy",
            set(policy),
            EXPECTED_MARKETPLACE_POLICY_KEYS,
        )
        if policy.get("installation") != EXPECTED_MARKETPLACE_INSTALLATION_POLICY:
            errors.append(
                "marketplace.json entry policy.installation must be "
                f"{EXPECTED_MARKETPLACE_INSTALLATION_POLICY!r}."
            )
        if policy.get("authentication") != EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY:
            errors.append(
                "marketplace.json entry policy.authentication must be "
                f"{EXPECTED_MARKETPLACE_AUTHENTICATION_POLICY!r}."
            )

    if entry.get("category") != EXPECTED_MARKETPLACE_CATEGORY:
        errors.append(
            f"marketplace.json entry 'category' must be {EXPECTED_MARKETPLACE_CATEGORY!r}."
        )


def run_skill_validator(root: Path, errors: list[str]) -> None:
    skill_root = root / SKILL_RELATIVE
    validator = root / SKILL_VALIDATOR_RELATIVE
    if not validator.is_file():
        errors.append(f"Skill validator script is missing: {validator}")
        return

    result = subprocess.run(
        [
            sys.executable,
            str(validator),
            str(skill_root),
            "--expected-name",
            EXPECTED_NAME,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("Bundled Plugin Skill failed validate-skill.py:")
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            errors.append(f"  {line}")


def run_mirror_check(root: Path, errors: list[str]) -> None:
    sync_script = root / SYNC_SCRIPT_RELATIVE
    if not sync_script.is_file():
        errors.append(f"Sync script is missing: {sync_script}")
        return

    result = subprocess.run(
        [sys.executable, str(sync_script), "--check", "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        errors.append("Plugin Skill mirror check failed:")
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            errors.append(f"  {line}")


def validate_no_symlinks(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    if not plugin_root.is_dir():
        errors.append(f"Plugin root is missing: {plugin_root}")
        return

    for current_dir, dir_names, file_names in os.walk(plugin_root, followlinks=False):
        current = Path(current_dir)
        for name in dir_names + file_names:
            candidate = current / name
            if candidate.is_symlink():
                errors.append(
                    f"Symlink is not allowed in the Plugin directory: {candidate}"
                )


def validate_forbidden_components(root: Path, errors: list[str]) -> None:
    """Recursively reject forbidden basenames anywhere under the Plugin root.

    Uses os.walk with followlinks=False so a symlinked directory is never
    descended into; that condition is separately rejected by
    validate_no_symlinks.
    """
    plugin_root = root / PLUGIN_RELATIVE
    if not plugin_root.is_dir():
        errors.append(f"Plugin root is missing: {plugin_root}")
        return

    for current_dir, dir_names, file_names in os.walk(plugin_root, followlinks=False):
        current = Path(current_dir)
        for name in dir_names:
            if name in FORBIDDEN_COMPONENT_BASENAMES:
                errors.append(f"Forbidden component present: {current / name}")
        for name in file_names:
            if name in FORBIDDEN_COMPONENT_BASENAMES:
                errors.append(f"Forbidden component present: {current / name}")


def normalize_reference_label(label: str) -> str:
    return " ".join(html.unescape(label).split()).casefold()


def _find_unescaped(text: str, needle: str, start: int) -> int:
    cursor = start
    while True:
        found = text.find(needle, cursor)
        if found < 0:
            return -1
        backslashes = 0
        check = found - 1
        while check >= 0 and text[check] == "\\":
            backslashes += 1
            check -= 1
        if backslashes % 2 == 0:
            return found
        cursor = found + len(needle)


def _find_closing_parenthesis(text: str, start: int) -> int:
    depth = 0
    cursor = start
    while cursor < len(text):
        character = text[cursor]
        if character == "\\":
            cursor += 2
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                return cursor
            depth -= 1
        cursor += 1
    return -1


def _append_markdown_span(
    spans: list[ReadmeMarkdownSpan],
    kind: str,
    source_start: int,
    source_end: int,
    value: str,
    children: tuple[ReadmeMarkdownSpan, ...] = (),
) -> None:
    if not value and not children:
        return
    if (
        kind == "text"
        and spans
        and spans[-1].kind == "text"
        and spans[-1].source_end == source_start
        and not spans[-1].children
    ):
        previous = spans[-1]
        spans[-1] = ReadmeMarkdownSpan(
            "text",
            previous.source_start,
            source_end,
            previous.text + value,
            (),
        )
        return
    spans.append(
        ReadmeMarkdownSpan(
            kind,
            source_start,
            source_end,
            value,
            children,
        )
    )


def parse_markdown_inline_spans(
    text: str,
    source_start: int,
    reference_labels: frozenset[str],
    *,
    parse_quotes: bool = True,
) -> tuple[ReadmeMarkdownSpan, ...]:
    spans: list[ReadmeMarkdownSpan] = []
    cursor = 0
    quote_pairs = (
        ("\"", "\""),
        ("“", "”"),
        ("‘", "’"),
        ("「", "」"),
        ("『", "』"),
    )

    while cursor < len(text):
        absolute = source_start + cursor

        if text[cursor] == "\\" and cursor + 1 < len(text):
            _append_markdown_span(
                spans,
                "text",
                absolute,
                absolute + 2,
                text[cursor + 1],
            )
            cursor += 2
            continue

        if text[cursor] == "<":
            tag_end = _find_unescaped(text, ">", cursor + 1)
            if tag_end >= 0:
                _append_markdown_span(
                    spans,
                    "html_tag",
                    absolute,
                    source_start + tag_end + 1,
                    text[cursor : tag_end + 1],
                )
                cursor = tag_end + 1
                continue

        if text[cursor] == "`":
            marker_end = cursor
            while marker_end < len(text) and text[marker_end] == "`":
                marker_end += 1
            marker = text[cursor:marker_end]
            closing = _find_unescaped(text, marker, marker_end)
            if closing >= 0:
                content_start = marker_end
                content_end = closing
                _append_markdown_span(
                    spans,
                    "inline_code",
                    source_start + cursor,
                    source_start + closing + len(marker),
                    text[content_start:content_end],
                )
                cursor = closing + len(marker)
                continue

        link_start = cursor + 1 if text.startswith("![", cursor) else cursor
        if link_start < len(text) and text[link_start] == "[":
            label_end = _find_unescaped(text, "]", link_start + 1)
            if label_end >= 0:
                label = text[link_start + 1 : label_end]
                label_source_start = source_start + link_start + 1
                label_children = parse_markdown_inline_spans(
                    label,
                    label_source_start,
                    reference_labels,
                )
                suffix = label_end + 1
                is_image = link_start != cursor
                if suffix < len(text) and text[suffix] == "(":
                    destination_end = _find_closing_parenthesis(
                        text,
                        suffix + 1,
                    )
                    if destination_end >= 0:
                        _append_markdown_span(
                            spans,
                            "inline_link_label",
                            source_start + cursor,
                            source_start + label_end + 1,
                            label,
                            label_children,
                        )
                        _append_markdown_span(
                            spans,
                            "inline_link_destination",
                            source_start + suffix,
                            source_start + destination_end + 1,
                            text[suffix + 1 : destination_end],
                        )
                        cursor = destination_end + 1
                        continue
                if suffix < len(text) and text[suffix] == "[":
                    reference_end = _find_unescaped(text, "]", suffix + 1)
                    if reference_end >= 0:
                        reference = text[suffix + 1 : reference_end] or label
                        if normalize_reference_label(reference) in reference_labels:
                            _append_markdown_span(
                                spans,
                                "reference_link_label",
                                source_start + cursor,
                                source_start + label_end + 1,
                                label,
                                label_children,
                            )
                            _append_markdown_span(
                                spans,
                                "reference_link_destination",
                                source_start + suffix,
                                source_start + reference_end + 1,
                                reference,
                            )
                            cursor = reference_end + 1
                            continue
                if (
                    not is_image
                    and normalize_reference_label(label) in reference_labels
                ):
                    _append_markdown_span(
                        spans,
                        "reference_link_label",
                        source_start + cursor,
                        source_start + label_end + 1,
                        label,
                        label_children,
                    )
                    cursor = label_end + 1
                    continue

        emphasis_marker = next(
            (
                marker
                for marker in ("**", "__", "~~", "*", "_")
                if text.startswith(marker, cursor)
            ),
            None,
        )
        if emphasis_marker is not None:
            content_start = cursor + len(emphasis_marker)
            closing = _find_unescaped(text, emphasis_marker, content_start)
            if closing >= 0:
                content = text[content_start:closing]
                children = parse_markdown_inline_spans(
                    content,
                    source_start + content_start,
                    reference_labels,
                )
                _append_markdown_span(
                    spans,
                    "emphasis",
                    absolute,
                    source_start + closing + len(emphasis_marker),
                    content,
                    children,
                )
                cursor = closing + len(emphasis_marker)
                continue

        if parse_quotes:
            quote_pair = next(
                (
                    (opening, closing)
                    for opening, closing in quote_pairs
                    if text.startswith(opening, cursor)
                ),
                None,
            )
            if quote_pair is not None:
                opening, closing_marker = quote_pair
                content_start = cursor + len(opening)
                closing = _find_unescaped(text, closing_marker, content_start)
                if closing >= 0:
                    content = text[content_start:closing]
                    children = (
                        ReadmeMarkdownSpan(
                            "text",
                            absolute,
                            absolute + len(opening),
                            opening,
                            (),
                        ),
                        *parse_markdown_inline_spans(
                            content,
                            source_start + content_start,
                            reference_labels,
                            parse_quotes=False,
                        ),
                        ReadmeMarkdownSpan(
                            "text",
                            source_start + closing,
                            source_start + closing + len(closing_marker),
                            closing_marker,
                            (),
                        ),
                    )
                    _append_markdown_span(
                        spans,
                        "quoted_text",
                        absolute,
                        source_start + closing + len(closing_marker),
                        text[cursor : closing + len(closing_marker)],
                        tuple(children),
                    )
                    cursor = closing + len(closing_marker)
                    continue

        _append_markdown_span(
            spans,
            "text",
            absolute,
            absolute + 1,
            text[cursor],
        )
        cursor += 1

    return tuple(spans)


def _source_lines(text: str) -> list[ReadmeSourceLine]:
    lines: list[ReadmeSourceLine] = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        content = raw_line.rstrip("\r\n")
        lines.append(ReadmeSourceLine(content, offset, offset + len(content)))
        offset += len(raw_line)
    if not lines and text:
        lines.append(ReadmeSourceLine(text, 0, len(text)))
    return lines


def _reference_labels(lines: list[ReadmeSourceLine]) -> frozenset[str]:
    labels: set[str] = set()
    for line in lines:
        quote = README_MARKDOWN_BLOCKQUOTE_PATTERN.match(line.text)
        content = quote.group("text") if quote else line.text
        definition = README_MARKDOWN_REFERENCE_DEFINITION_PATTERN.match(content)
        if definition is not None:
            labels.add(normalize_reference_label(definition.group("label")))
    return frozenset(labels)


def _indented_code_content(content: str) -> tuple[str, int] | None:
    if content.startswith("\t"):
        return content[1:], 1
    if content.startswith("    "):
        return content[4:], 4
    return None


def parse_readme_markdown(text: str) -> list[ReadmeMarkdownBlock]:
    source_lines = _source_lines(text)
    reference_labels = _reference_labels(source_lines)
    blocks: list[ReadmeMarkdownBlock] = []
    current_kind: str | None = None
    current_quote_depth = 0
    current_lines: list[ReadmeSourceLine] = []
    current_source_start = 0
    current_source_end = 0
    fence_character: str | None = None
    fence_length = 0

    def block_spans(
        kind: str,
        lines: list[ReadmeSourceLine],
    ) -> tuple[ReadmeMarkdownSpan, ...]:
        spans: list[ReadmeMarkdownSpan] = []
        for index, line in enumerate(lines):
            if index:
                previous = lines[index - 1]
                _append_markdown_span(
                    spans,
                    "soft_break",
                    previous.source_end,
                    line.source_start,
                    "\n",
                )
            if kind in {"fenced_code", "indented_code"}:
                _append_markdown_span(
                    spans,
                    "code_content",
                    line.source_start,
                    line.source_end,
                    line.text,
                )
            else:
                spans.extend(
                    parse_markdown_inline_spans(
                        line.text,
                        line.source_start,
                        reference_labels,
                    )
                )
        return tuple(spans)

    def append_block(
        kind: str,
        lines: list[ReadmeSourceLine],
        source_start: int,
        source_end: int,
        *,
        spans: tuple[ReadmeMarkdownSpan, ...] | None = None,
    ) -> None:
        blocks.append(
            ReadmeMarkdownBlock(
                len(blocks),
                kind,
                source_start,
                source_end,
                block_spans(kind, lines) if spans is None else spans,
            )
        )

    def flush() -> None:
        nonlocal current_kind, current_quote_depth, current_lines
        nonlocal current_source_start, current_source_end
        if current_kind is not None:
            append_block(
                current_kind,
                current_lines,
                current_source_start,
                current_source_end,
            )
        current_kind = None
        current_quote_depth = 0
        current_lines = []
        current_source_start = 0
        current_source_end = 0

    line_index = 0
    while line_index < len(source_lines):
        source_line = source_lines[line_index]
        quote = README_MARKDOWN_BLOCKQUOTE_PATTERN.match(source_line.text)
        quote_depth = quote.group("prefix").count(">") if quote else 0
        content = quote.group("text") if quote else source_line.text
        content_start = (
            source_line.source_start + quote.start("text")
            if quote
            else source_line.source_start
        )
        content_line = ReadmeSourceLine(
            content,
            content_start,
            content_start + len(content),
        )

        if fence_character is not None:
            closing = README_MARKDOWN_FENCE_CLOSE_PATTERN.match(content)
            if (
                closing is not None
                and closing.group("fence")[0] == fence_character
                and len(closing.group("fence")) >= fence_length
            ):
                current_source_end = source_line.source_end
                flush()
                fence_character = None
                fence_length = 0
            else:
                current_lines.append(content_line)
                current_source_end = source_line.source_end
            line_index += 1
            continue

        if current_kind == "indented_code":
            indented = _indented_code_content(content)
            if indented is not None:
                value, prefix_length = indented
                current_lines.append(
                    ReadmeSourceLine(
                        value,
                        content_start + prefix_length,
                        content_start + len(content),
                    )
                )
                current_source_end = source_line.source_end
                line_index += 1
                continue
            if not content.strip():
                current_lines.append(
                    ReadmeSourceLine("", content_start, content_start)
                )
                current_source_end = source_line.source_end
                line_index += 1
                continue
            flush()
            continue

        if not content.strip():
            flush()
            line_index += 1
            continue

        fence = README_MARKDOWN_FENCE_OPEN_PATTERN.match(content)
        if fence is not None:
            flush()
            current_kind = "fenced_code"
            current_quote_depth = quote_depth
            current_source_start = source_line.source_start
            current_source_end = source_line.source_end
            fence_character = fence.group("fence")[0]
            fence_length = len(fence.group("fence"))
            line_index += 1
            continue

        if (
            current_kind in {"paragraph", "blockquote_paragraph"}
            and current_quote_depth == quote_depth
            and README_MARKDOWN_SETEXT_PATTERN.match(content)
        ):
            current_kind = "heading"
            current_source_end = source_line.source_end
            flush()
            line_index += 1
            continue

        if README_MARKDOWN_THEMATIC_BREAK_PATTERN.match(content):
            flush()
            append_block(
                "thematic_break",
                [],
                source_line.source_start,
                source_line.source_end,
                spans=(),
            )
            line_index += 1
            continue

        heading = README_MARKDOWN_HEADING_PATTERN.match(content)
        if heading is not None:
            flush()
            heading_start = content_start + heading.start("text")
            heading_line = ReadmeSourceLine(
                heading.group("text"),
                heading_start,
                heading_start + len(heading.group("text")),
            )
            append_block(
                "heading",
                [heading_line],
                source_line.source_start,
                source_line.source_end,
            )
            line_index += 1
            continue

        definition = README_MARKDOWN_REFERENCE_DEFINITION_PATTERN.match(content)
        if definition is not None:
            flush()
            definition_spans: list[ReadmeMarkdownSpan] = []
            for kind, group_name in (
                ("reference_definition_label", "label"),
                ("reference_definition_destination", "destination"),
                ("reference_definition_title", "title"),
            ):
                value = definition.group(group_name)
                if value is None:
                    continue
                _append_markdown_span(
                    definition_spans,
                    kind,
                    content_start + definition.start(group_name),
                    content_start + definition.end(group_name),
                    value,
                )
            append_block(
                "reference_definition",
                [],
                source_line.source_start,
                source_line.source_end,
                spans=tuple(definition_spans),
            )
            line_index += 1
            continue

        list_item = README_MARKDOWN_LIST_ITEM_PATTERN.match(content)
        if list_item is not None:
            flush()
            item_start = content_start + list_item.start("text")
            current_kind = "list_item"
            current_quote_depth = quote_depth
            current_source_start = source_line.source_start
            current_source_end = source_line.source_end
            current_lines = [
                ReadmeSourceLine(
                    list_item.group("text"),
                    item_start,
                    item_start + len(list_item.group("text")),
                )
            ]
            line_index += 1
            continue

        indented = _indented_code_content(content)
        if indented is not None:
            value, prefix_length = indented
            flush()
            current_kind = "indented_code"
            current_quote_depth = quote_depth
            current_source_start = source_line.source_start
            current_source_end = source_line.source_end
            current_lines = [
                ReadmeSourceLine(
                    value,
                    content_start + prefix_length,
                    content_start + len(content),
                )
            ]
            line_index += 1
            continue

        next_kind = "blockquote_paragraph" if quote_depth else "paragraph"
        if current_kind == "list_item" and current_quote_depth == quote_depth:
            stripped = content.strip()
            stripped_start = content_start + content.find(stripped)
            current_lines.append(
                ReadmeSourceLine(
                    stripped,
                    stripped_start,
                    stripped_start + len(stripped),
                )
            )
            current_source_end = source_line.source_end
            line_index += 1
            continue
        if current_kind != next_kind or current_quote_depth != quote_depth:
            flush()
            current_kind = next_kind
            current_quote_depth = quote_depth
            current_source_start = source_line.source_start
        current_lines.append(content_line)
        current_source_end = source_line.source_end
        line_index += 1

    flush()
    return blocks


def project_readme_visible_text(
    blocks: list[ReadmeMarkdownBlock],
) -> list[ReadmeBlock]:
    projected: list[ReadmeBlock] = []
    invisible_blocks = {
        "fenced_code",
        "indented_code",
        "thematic_break",
        "reference_definition",
    }
    invisible_spans = {
        "html_tag",
        "inline_link_destination",
        "reference_link_destination",
        "reference_definition_label",
        "reference_definition_destination",
        "reference_definition_title",
        "code_content",
    }
    semantic_kinds = {
        "inline_code": "inline_code",
        "quoted_text": "quoted_text",
        "emphasis": "emphasis_visible",
        "inline_link_label": "link_label",
        "reference_link_label": "link_label",
    }

    for block in blocks:
        output: list[str] = []
        visible_spans: list[ReadmeVisibleSpan] = []

        def append_visible(value: str) -> None:
            for character in html.unescape(value):
                if character.isspace():
                    if output and output[-1] != " ":
                        output.append(" ")
                else:
                    output.append(character)

        def project_span(span: ReadmeMarkdownSpan) -> None:
            if span.kind in invisible_spans:
                return
            start = len(output)
            if span.children:
                for child in span.children:
                    project_span(child)
            else:
                append_visible(span.text)
            end = len(output)
            visible_kind = semantic_kinds.get(span.kind)
            if visible_kind is not None and start < end:
                visible_spans.append(
                    ReadmeVisibleSpan(
                        visible_kind,
                        start,
                        end,
                        span.source_start,
                        span.source_end,
                    )
                )

        if block.kind not in invisible_blocks:
            for span in block.spans:
                project_span(span)
        while output and output[-1] == " ":
            output.pop()
        visible_length = len(output)
        projected.append(
            ReadmeBlock(
                block.block_id,
                block.kind,
                block.source_start,
                block.source_end,
                "".join(output),
                tuple(
                    ReadmeVisibleSpan(
                        span.kind,
                        span.start,
                        min(span.end, visible_length),
                        span.source_start,
                        span.source_end,
                    )
                    for span in visible_spans
                    if span.start < min(span.end, visible_length)
                ),
            )
        )

    return projected


def readme_visible_blocks(text: str) -> list[ReadmeBlock]:
    return project_readme_visible_text(parse_readme_markdown(text))


def readme_claim_clauses(text: str) -> list[ReadmeClaimClause]:
    clauses: list[ReadmeClaimClause] = []
    blocks = readme_visible_blocks(text)
    for block_index, block in enumerate(blocks):
        if not block.text:
            continue
        readiness_context = " ".join(
            candidate.text
            for candidate in blocks[max(0, block_index - 2) : block_index + 1]
            if candidate.text
        )
        segment_start = 0
        clause_id = 0
        boundaries = list(README_CLAUSE_SPLIT_PATTERN.finditer(block.text))
        for boundary in (*boundaries, None):
            segment_end = boundary.start() if boundary is not None else len(block.text)
            raw_segment = block.text[segment_start:segment_end]
            stripped = raw_segment.strip()
            if stripped:
                left_trim = len(raw_segment) - len(raw_segment.lstrip())
                visible_start = segment_start + left_trim
                visible_end = visible_start + len(stripped)
                spans = tuple(
                    ReadmeVisibleSpan(
                        span.kind,
                        max(span.start, visible_start) - visible_start,
                        min(span.end, visible_end) - visible_start,
                        span.source_start,
                        span.source_end,
                    )
                    for span in block.spans
                    if span.start < visible_end and span.end > visible_start
                )
                clauses.append(
                    ReadmeClaimClause(
                        block_id=block.block_id,
                        block_kind=block.kind,
                        block_text=block.text,
                        source_start=block.source_start,
                        source_end=block.source_end,
                        readiness_context=readiness_context,
                        clause_id=clause_id,
                        text=stripped,
                        spans=spans,
                    )
                )
                clause_id += 1
            segment_start = boundary.end() if boundary is not None else segment_end
    return clauses


def status_match_quote_span(
    clause: str,
    match: re.Match[str],
) -> tuple[int, int] | None:
    for opening, closing in (
        ("\"", "\""),
        ("'", "'"),
        ("“", "”"),
        ("‘", "’"),
        ("「", "」"),
        ("『", "』"),
        ("`", "`"),
    ):
        cursor = 0
        while True:
            start = clause.find(opening, cursor)
            if start < 0:
                break
            end = clause.find(closing, start + len(opening))
            if end < 0:
                break
            if start < match.start() and match.end() <= end:
                return start, end + len(closing)
            cursor = end + len(closing)
    return None


def claim_scope_bounds(
    clause: str,
    match: re.Match[str],
) -> tuple[int, int]:
    start = 0
    end = len(clause)
    boundaries = sorted(
        (
            *README_CONTRAST_PATTERN.finditer(clause),
            *README_INDEPENDENT_CLAIM_BOUNDARY_PATTERN.finditer(clause),
        ),
        key=lambda boundary: boundary.start(),
    )
    for boundary in boundaries:
        if (
            boundary.group(0).casefold() == "yet"
            and clause[max(0, boundary.start() - 4) : boundary.start()]
            .casefold()
            .endswith("not ")
        ):
            continue
        if boundary.end() <= match.start():
            start = boundary.start()
        elif boundary.start() >= match.end():
            end = boundary.start()
            break
    return start, end


def build_claim_occurrence(
    clause: ReadmeClaimClause,
    match: re.Match[str],
) -> ReadmeClaimOccurrence:
    claim_start, claim_end = claim_scope_bounds(clause.text, match)

    def containing_span(kind: str) -> tuple[int, int] | None:
        for span in clause.spans:
            if (
                span.kind == kind
                and span.start <= match.start()
                and match.end() <= span.end
            ):
                return span.start, span.end
        return None

    return ReadmeClaimOccurrence(
        block_id=clause.block_id,
        block_kind=clause.block_kind,
        block_text=clause.block_text,
        readiness_context=clause.readiness_context,
        clause_id=clause.clause_id,
        clause=clause.text,
        status_start=match.start(),
        status_end=match.end(),
        claim_start=claim_start,
        claim_end=claim_end,
        quote_span=(
            containing_span("quoted_text")
            or status_match_quote_span(clause.text, match)
        ),
        inline_code_span=containing_span("inline_code"),
        link_label_span=containing_span("link_label"),
        emphasis_visible_span=containing_span("emphasis_visible"),
    )


def status_match_has_polarity_reversal(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    return bool(
        README_POLARITY_REVERSAL_BEFORE_PATTERN.search(occurrence.before)
        or README_POLARITY_REVERSAL_AFTER_PATTERN.search(occurrence.after)
    )


def status_match_is_negated(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    direct_negation = bool(
        README_STATUS_NEGATION_BEFORE_PATTERN.search(occurrence.before)
        or README_STATUS_COMPOUND_NEGATION_BEFORE_PATTERN.search(
            occurrence.before
        )
        or README_STATUS_PENDING_AFTER_PATTERN.search(occurrence.after)
    )
    return direct_negation and not status_match_has_polarity_reversal(occurrence)


def status_match_is_non_current(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    return bool(
        README_STATUS_NON_CURRENT_BEFORE_PATTERN.search(occurrence.before)
        or README_STATUS_NON_CURRENT_AFTER_PATTERN.search(occurrence.after)
    )


def status_match_structural_span(
    occurrence: ReadmeClaimOccurrence,
) -> tuple[int, int] | None:
    spans = tuple(
        span
        for span in (
            occurrence.quote_span,
            occurrence.inline_code_span,
            occurrence.link_label_span,
        )
        if span is not None
    )
    return min(spans, key=lambda span: span[1] - span[0]) if spans else None


def structural_status_is_reporting(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    structural_span = status_match_structural_span(occurrence)
    if structural_span is None:
        return False
    span_start, span_end = structural_span
    outer_before = occurrence.clause[occurrence.claim_start:span_start]
    outer_after = occurrence.clause[span_end:occurrence.claim_end]
    span_before_status = occurrence.clause[span_start:occurrence.status_start]
    span_after_status = occurrence.clause[occurrence.status_end:span_end]
    relation_context = (
        f"{outer_before} {span_before_status} "
        f"{span_after_status} {outer_after}"
    )
    has_reporting_relation = bool(
        README_REPORTING_SUBJECT_PATTERN.search(relation_context)
        and README_REPORTING_VERB_PATTERN.search(relation_context)
    )
    has_explicit_non_assertion = bool(
        README_NON_ASSERTION_CUE_PATTERN.search(relation_context)
        or README_NON_ASSERTION_AFTER_PATTERN.search(outer_after)
    )
    if not (has_reporting_relation or has_explicit_non_assertion):
        return False
    if README_ASSERTIVE_REPORTING_ROLE_PATTERN.search(relation_context):
        return False
    return True


def unquoted_status_is_reporting(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    context = occurrence.clause[occurrence.claim_start : occurrence.claim_end]
    has_reporting_relation = bool(
        README_REPORTING_SUBJECT_PATTERN.search(context)
        and README_REPORTING_VERB_PATTERN.search(context)
    )
    if not has_reporting_relation:
        return False
    if README_ASSERTIVE_REPORTING_ROLE_PATTERN.search(context):
        return False
    return bool(
        README_REPORTING_MENTION_PATTERN.search(context)
        or README_NON_ASSERTION_CUE_PATTERN.search(context)
        or README_NON_ASSERTION_AFTER_PATTERN.search(occurrence.after)
    )


def status_match_is_non_assertive(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    before = occurrence.before
    after = occurrence.after
    structural_span = status_match_structural_span(occurrence)

    if structural_status_is_reporting(occurrence):
        return True
    if structural_span is None and unquoted_status_is_reporting(occurrence):
        return True

    for cue in README_NON_ASSERTION_CUE_PATTERN.finditer(before):
        governed_text = before[cue.end() :]
        if not README_CONTRAST_PATTERN.search(
            governed_text
        ) and not README_INDEPENDENT_CLAIM_BOUNDARY_PATTERN.search(governed_text):
            return True

    for cue in README_NON_ASSERTION_CUE_PATTERN.finditer(after):
        governed_text = after[: cue.start()]
        if README_CONTRAST_PATTERN.search(
            governed_text
        ) or README_INDEPENDENT_CLAIM_BOUNDARY_PATTERN.search(governed_text):
            continue
        explanatory_subject = README_EXPLANATORY_SUBJECT_PATTERN.search(before)
        if (
            structural_span is not None
            or explanatory_subject
            or README_TRAILING_NON_ASSERTION_LINK_PATTERN.fullmatch(governed_text)
        ):
            return True

    return bool(
        README_REPORTING_SUBJECT_PATTERN.search(before)
        and README_REPORTING_VERB_PATTERN.search(before)
        and README_NON_ASSERTION_AFTER_PATTERN.search(
            after.lstrip("\"'”’」』）》）】` ,、，:")
        )
    )


def status_match_is_allowed_historical(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    return bool(
        README_HISTORICAL_CUE_PATTERN.search(occurrence.before)
        and README_INVALIDATION_CUE_PATTERN.search(
            occurrence.clause[occurrence.status_end :]
        )
    )


def readme_claim_excerpt(
    clause: ReadmeClaimClause,
    match: re.Match[str],
) -> str:
    if len(clause.text) <= README_DIAGNOSTIC_EXCERPT_LENGTH:
        return clause.text
    center = (match.start() + match.end()) // 2
    start = max(0, center - README_DIAGNOSTIC_EXCERPT_LENGTH // 2)
    end = start + README_DIAGNOSTIC_EXCERPT_LENGTH
    return clause.text[start:end]


def occurrence_has_readiness_context(
    occurrence: ReadmeClaimOccurrence,
) -> bool:
    scoped_claim = occurrence.clause[
        occurrence.claim_start : occurrence.claim_end
    ]
    has_local_gate_context = bool(
        README_GATE_CONTEXT_PATTERN.search(scoped_claim)
    )
    has_local_current_action_context = bool(
        README_VERIFIED_ACTION_PATTERN.search(scoped_claim)
        and README_CURRENT_IDENTITY_CUE_PATTERN.search(scoped_claim)
    )
    if has_local_gate_context or has_local_current_action_context:
        return True
    if (
        README_VERIFIED_ACTION_PATTERN.search(scoped_claim)
        and README_CURRENT_IDENTITY_CUE_PATTERN.search(
            occurrence.readiness_context
        )
    ):
        return True
    if (
        README_VERIFIED_ACTION_PATTERN.search(scoped_claim)
        and README_GATE_CONTEXT_PATTERN.search(occurrence.readiness_context)
    ):
        return True

    prefix = occurrence.before.strip()
    if not README_ANAPHORIC_STATUS_PREFIX_PATTERN.fullmatch(prefix):
        return False
    return bool(
        README_GATE_CONTEXT_PATTERN.search(occurrence.readiness_context)
        or (
            README_VERIFIED_ACTION_PATTERN.search(occurrence.readiness_context)
            and README_CURRENT_IDENTITY_CUE_PATTERN.search(
                occurrence.readiness_context
            )
        )
    )


def validate_readmes(root: Path, errors: list[str]) -> None:
    plugin_root = root / PLUGIN_RELATIVE
    for name in README_NAMES:
        candidate = plugin_root / name
        if not candidate.is_file() or candidate.stat().st_size == 0:
            errors.append(f"Plugin README is missing or empty: {candidate}")
            continue
        text = candidate.read_text(encoding="utf-8")
        for marker in STALE_README_MARKERS:
            if marker in text:
                errors.append(
                    f"Plugin README contains stale marketplace/version identity: "
                    f"{name}: {marker!r}"
                )
        for marker in REQUIRED_README_MARKERS:
            if marker not in text:
                errors.append(
                    f"Plugin README must record the current marketplace/version "
                    f"identity: {name}: {marker!r}"
                )

        for match in PLUGIN_DEVELOPMENT_VERSION_PATTERN.finditer(text):
            if match.group(0) != EXPECTED_VERSION:
                errors.append(
                    "Plugin README development-version mismatch: "
                    f"{name}: found {match.group(0)!r}; expected only "
                    f"{EXPECTED_VERSION!r}."
                )

        clauses = readme_claim_clauses(text)
        for clause in clauses:
            status_matches = [
                (match, False)
                for match in README_POSITIVE_GATE_STATUS_PATTERN.finditer(
                    clause.text
                )
            ]
            status_matches.extend(
                (match, True)
                for match in README_NEGATIVE_STATE_STATUS_PATTERN.finditer(
                    clause.text
                )
            )
            for match in README_NEGATIVE_STATE_PREDICATE_PATTERN.finditer(
                clause.text
            ):
                occurrence = build_claim_occurrence(clause, match)
                if status_match_has_polarity_reversal(occurrence):
                    status_matches.append((match, True))
            status_matches.sort(key=lambda item: item[0].start())
            for match, negative_state_reversal in status_matches:
                occurrence = build_claim_occurrence(clause, match)
                if not occurrence_has_readiness_context(occurrence):
                    continue
                if (
                    (
                        not negative_state_reversal
                        and status_match_is_negated(occurrence)
                    )
                    or status_match_is_non_current(occurrence)
                    or status_match_is_non_assertive(occurrence)
                    or status_match_is_allowed_historical(occurrence)
                ):
                    continue
                excerpt = readme_claim_excerpt(clause, match)
                errors.append(
                    "Plugin README Phase C identity contradiction: "
                    f"{name}: block={clause.block_id}/"
                    f"{clause.block_kind}, clause={clause.clause_id}: "
                    f"{excerpt!r}."
                )
                break


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    errors: list[str] = []

    validate_manifest(root, errors)
    validate_plugin_tree_contract(root, errors)
    validate_marketplace(root, errors)
    run_skill_validator(root, errors)
    run_mirror_check(root, errors)
    validate_no_symlinks(root, errors)
    validate_forbidden_components(root, errors)
    validate_readmes(root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Codex Plugin validation: FAIL ({len(errors)} issue(s))", file=sys.stderr)
        return 1

    print("Codex Plugin validation: PASS")
    print(f"- manifest: {root / MANIFEST_RELATIVE}")
    print(f"- marketplace: {root / MARKETPLACE_RELATIVE}")
    print(f"- bundled Skill: {root / SKILL_RELATIVE}")
    print(f"- Plugin NOTICE: {root / PLUGIN_RELATIVE / 'NOTICE'}")
    print("- MCP servers: none (recursive scan)")
    print("- Apps/connectors: none (recursive scan)")
    print("- Hooks: none (recursive scan)")
    print("- capabilities: Read only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
