# Agentic Change Audit Model Selection and Independent Audit Policy

- Version: `2026-07-30-candidate.2`
- Repository: `landco-llc/agentic-change-audit`
- Internal central policy ID: `LCO-DEV-GOV-AI-MODEL-001`
- Public-repository rule: do not expose private Drive links, private repository URLs, private project names, or confidential evidence
- Status: `PENDING ACTIVATION`

## Implementation routing

Default: `GPT-5.6 Terra / high`.

### Luna

Use for deterministic fixtures, corpus formatting, generated cases, schemas, indexes, result maintenance, inventory, and structured summaries.

Do not use Luna for semantic-rule design, clause boundaries, visible-text projection, Markdown/entity/multilingual meaning, false-PASS/false-reject root cause, security verdicts, parser architecture, untrusted-input boundaries, conflicting evidence, or substantive final audit.

### Terra

Use for ordinary parser/test implementation, bounded semantic fixes, repository investigation, canonical-case reconciliation, and normal audit.

### Sol

Use for semantic architecture, visible-text projection design, normalization boundaries, false-PASS/false-reject integrity, security-sensitive parsing, unclear failures, conflicting evidence, and critical audit.

### GPT-5.5

Use only for frozen-workflow reproduction, confirmed GPT-5.6 incompatibility, an explicitly useful second opinion, or explicit approval. It is not a mandatory Sol auditor.

## Independent audit

Same-model audit is allowed when separate session/role, fixed PR/SHA, audit-only write boundary, separate result, and independent primary evidence are preserved.

| Audit class | ACA target | Default model |
|---|---|---|
| Simplified | docs, indexes, deterministic fixtures and schemas | Luna or Terra |
| Normal | bounded parser/test behavior and canonical cases | Terra |
| Focused | semantic boundaries, visible text, false PASS/reject, untrusted input | Sol |
| Critical | security, verdict integrity, disputed evidence | Sol / xhigh plus another verification path when useful |

Terra-on-Terra and Sol-on-Sol are allowed. Luna must not perform substantive or security-critical ACA audit.

## ACA self-use guidance

ACA must not be made recursively mandatory for every ACA audit. Use additional ACA execution only when it provides a distinct, defined verification path. Prefer canonical cases, raw evidence, independent probes, schema validation, and executable regression tests. A second model is optional when a disputed or critical judgment benefits from it.

## Required launch metadata

Instructions must record target risk, selected model and reason, escalation conditions, fixed HEAD, independence controls, evidence methods, and whether an additional ACA run is unnecessary, optional, recommended, or task-required.

## Stop conditions

Stop and return to the ACA control chat when semantic authority, canonical cases, fixed HEAD, evidence provenance, public/private boundary, or verification method is ambiguous, or when a bounded task reveals verdict-integrity or security impact.

Ready, merge, release, and publication remain separate approvals. Public outputs must remain sanitized.
