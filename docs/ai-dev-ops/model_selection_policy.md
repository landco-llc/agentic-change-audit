# Agentic Change Audit Model Selection and Independent Audit Policy

- Version: `2026-08-01-candidate`
- Repository: `landco-llc/agentic-change-audit`
- Central policy: `LCO-DEV-GOV-AI-MODEL-001`
- Public repository rule: internal Drive links, private repository URLs, confidential project facts, and private evidence must not be copied here
- Status: `PENDING ACTIVATION`

## Official Codex rate

Confirmed `2026-08-01`, credits per 1M tokens:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| GPT-5.6 Luna | 5 | 0.5 | 30 |
| GPT-5.6 Terra | 50 | 5 | 300 |
| GPT-5.6 Sol | 125 | 12.5 | 750 |
| GPT-5.5 | 125 | 12.5 | 750 |

Source: https://help.openai.com/en/articles/20001106-codex-rate-card

The latest official rate card overrides this table. API prices and Codex credits are separate.

## Phase routing

| Phase | Default |
|---|---|
| Fixtures, schemas, expected results, docs, result maintenance | Luna / medium |
| Well-specified test variants and bounded parser correction | Luna / high |
| Investigation, canonical-case reconciliation, normal audit | Terra / high |
| Semantic architecture, false-verdict integrity, untrusted input, security | Sol / high-xhigh |

Luna may implement semantic corrections only after the semantic rule, allowed paths, canonical cases, and expected verdicts are fixed by Terra or Sol.

## Luna eligibility

Eligible examples:

- fixture and corpus formatting
- schema and expected-result maintenance
- implementation of already-specified test variants
- bounded parser correction with exact canonical cases
- docs, results, handoffs, indexes, inventory, and deterministic classification support

Luna must stop when clause boundaries, visible-text meaning, multilingual semantics, false PASS/reject causes, or verdict policy require judgment.

## Terra work

Use Terra for:

- repository and test-corpus investigation
- bounded semantic analysis and canonical-case reconciliation
- Luna-ready test/correction instruction creation
- normal independent audit
- implementation where semantic judgment remains but risk is not critical

## Sol triggers

Use Sol for:

- semantic architecture and visible-text projection design
- Markdown, entity, clause, or multilingual boundary decisions
- false PASS or false reject root-cause determination
- verdict integrity and finding-validity rules
- untrusted-input and security-sensitive parsing
- critical audit, conflicting evidence, or release-blocking uncertainty

Luna is prohibited for these areas.

## Public safety

- use sanitized generic examples in public artifacts
- do not expose private repository names, private URLs, customer data, or internal Drive references
- stable prompt prefixes must not contain private project context that could leak into this public repository

## GPT-5.5

Use only for reproduction, confirmed GPT-5.6 incompatibility, an explicit second opinion, or explicit Mamoru instruction.

## Independent audit

- Simplified deterministic audit: Luna or Terra
- Normal parser/test audit: Terra
- Semantic architecture, false-verdict, untrusted-input, or security audit: Sol
- Same-model audit is allowed under separate session, role, fixed SHA, audit-only boundary, separate result, and independent evidence
- ACA is not recursively mandatory for ACA itself; use another ACA run only when it provides a genuinely distinct verification path

## Context and credit efficiency

- maintain a stable public-safe launch prefix
- place variable PR/HEAD and sanitized case data later
- load the current handoff, canonical cases, and required evidence only
- separate raw ACA JSON from concise result summaries
- use a clean Luna session after semantic rules and expected verdicts are fixed
- avoid repeatedly loading all prior remediation ledgers unless the Work requires them

## Fast mode

Sol Fast mode is reserved for urgent release-blocking false verdicts or urgent security response. It is not routine for fixture work or scheduled audit.

## Activation

This file remains `PENDING ACTIVATION` until the central policy and this adoption are independently audited, accepted, and merged. Ready, merge, release, and publication require separate approval.
