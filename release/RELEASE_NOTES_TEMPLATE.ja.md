# Agentic Change Audit v<version>

[English](RELEASE_NOTES_TEMPLATE.md)

## Status

**Pre-release** | **Stable**

## 概要

このreleaseの目的と固定source commitを記載します。

## 内容

- Agent-neutralな監査Skill
- 英語正本standard
- 公式日本語訳
- JSON Schemaおよび結果template
- local installation guide

## Source identity

```text
Repository: landco-llc/agentic-change-audit
Tag: v<version>
Source commit: <full-source-sha>
```

## Asset

```text
agentic-change-audit-<version>.zip
agentic-change-audit-<version>.manifest.json
agentic-change-audit-<version>.SHA256SUMS
```

ZIPはversionを含まないSkill directoryへ展開されます。

```text
agentic-change-audit/
```

## 検証

導入前にSHA-256を確認してください。可能な場合、source repositoryの`scripts/verify-distribution.py`も実行します。

## 互換性

確認済みのClaude Code／Codex導入動作と最低versionを記載します。

## 既知制限

- automated validationは独立監査判断を代替しない
- 監査結果はsecurity certification、法律意見、規制適合認証、本番安全性保証ではない
- 明記がない限りCodex Plugin packageを含まない
- release固有の制限を記載する

## Support

本projectは現状有姿で提供します。無償導入支援、troubleshooting、継続保守、回答期限保証は含みません。専門的な実装・統合支援を別途有償提供する場合があります。
