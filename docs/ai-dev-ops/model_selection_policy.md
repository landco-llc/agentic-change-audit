# Agentic Change Audit Model Selection and Independent Audit Policy

- Version: `2026-07-30-candidate`
- Repository: `landco-llc/agentic-change-audit`
- Internal central policy ID: `LCO-DEV-GOV-AI-MODEL-001`
- Public-repository rule: internal Drive links, private repository URLs, private project names, and confidential operational evidence must not be copied into this public repository
- Status: `PENDING ACTIVATION` until internal central-policy activation and this adoption change are independently audited, accepted, and merged

## Default

When an instruction does not explicitly select a model, use:

```text
推奨モデル：GPT-5.6 Terra
reasoning：high
```

## Credit-aware routing

| Model | Role in ACA |
|---|---|
| GPT-5.6 Luna | Deterministic fixtures, generated cases, formatting, result/index maintenance, and low-risk classification support |
| GPT-5.6 Terra | Default implementation, parser/test work, repository investigation, and audit of Luna work |
| GPT-5.6 Sol | Semantic architecture, false-PASS/false-reject boundaries, security-sensitive parsing, difficult root-cause analysis, and critical audit |
| GPT-5.5 | Frozen-workflow reproduction, confirmed GPT-5.6 incompatibility, or model-diversity audit of Sol implementation |

As of 2026-07-30, Codex credit ratios are approximately Luna 1.0x, Terra 2.5x, and Sol/GPT-5.5 5.0x. The latest official rate card overrides this planning ratio.

## Luna eligibility

Use Luna only for bounded work with explicit expected output and deterministic validation, including:

- fixture and corpus formatting
- expected-result, schema, index, handoff, or docs-only updates
- generation of already-specified test variants
- grep, inventory, classification, and structured summary work

Luna is prohibited for:

- semantic-rule design or clause-boundary decisions
- visible-text projection, Markdown normalization, entity decoding, multilingual meaning classification
- false-PASS or false-reject root-cause determination
- security finding discovery, exploitability, severity, or audit-verdict decisions
- parser architecture, untrusted-input boundaries, or conflicting evidence
- final independent audit of substantive ACA behavior

Do not use Luna with `xhigh`, `max`, or `ultra`; escalate to Terra.

## Terra lane

Use `GPT-5.6 Terra / high` for normal parser/test implementation, bounded semantic fixes, repository investigation, canonical-case reconciliation, and independent audit of Luna implementation.

Escalate to Sol for architecture, ambiguous semantics, security, critical verdict logic, or repeated false-PASS/false-reject behavior.

## Sol lane

Use `GPT-5.6 Sol / high` or `xhigh` for:

- semantic architecture and visible-text projection design
- Markdown/multilingual/entity normalization boundaries
- false-PASS/false-reject root causes and verdict integrity
- security-sensitive parsing and untrusted-input behavior
- unclear failures, conflicting evidence, or critical audit

## Implementation/audit separation

| Implementation model | Independent audit model |
|---|---|
| GPT-5.6 Luna | GPT-5.6 Terra; Sol for semantic or security impact |
| GPT-5.6 Terra | GPT-5.6 Sol |
| GPT-5.6 Sol | GPT-5.5 or another approved independent model family |
| GPT-5.5 | GPT-5.6 Sol |

If model-family separation is unavailable after Sol implementation, use a separate Sol audit session plus a second independent verifier, record the limitation, and require explicit approval.

Substantive ACA audits must never use Luna. Different reasoning alone is not model separation. The auditor must not modify the target implementation or silently repair findings.

## Implementation launch template

```text
次の作業を実行

作業種別：実装
作業ランク：A / B / C
推奨実装エージェント：Codex / other approved agent
推奨モデル：GPT-5.6 Luna / GPT-5.6 Terra / GPT-5.6 Sol / GPT-5.5
reasoning：medium / high / xhigh
モデル選定理由：<semantic risk, verification method, context size, credit balance>
対象レポ：landco-llc/agentic-change-audit
指示書配置場所：<repository path>
branch：<base or working branch>
固定開始HEAD：<full SHA or N/A>
完了条件：<canonical cases, regression tests, schema or exact verdict criteria>
上位モデルへ上げる条件：<semantic boundary/false PASS/false reject/security/conflicting evidence>
禁止事項：<scope expansion, target audit modification, merge or release without approval>
監査方針：不要 / 簡易 / 通常 / 重点
予定監査モデル：<implementation modelとは分離>
```

## Independent audit launch template

```text
次の独立監査を実行

作業種別：監査
監査ランク：簡易 / 通常 / 重点
推奨監査エージェント：Codex / Codex Security / other approved auditor
推奨監査モデル：GPT-5.6 Terra / GPT-5.6 Sol / GPT-5.5
reasoning：high / xhigh
実装モデル：<known model or UNKNOWN>
モデル分離判定：PASS / EXCEPTION REQUIRES APPROVAL
対象レポ：landco-llc/agentic-change-audit
対象PR：<#number>
固定監査HEAD：<full SHA>
監査結果配置場所：<separate audit/reporting path or PR>
禁止事項：対象実装変更、silent repair、Ready、merge、release
```

A stronger model does not authorize broader scope. Public outputs must remain sanitized and must not expose internal canonical links or confidential evidence.
