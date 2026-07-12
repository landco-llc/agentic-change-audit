# Agentic Change Audit Standard

## Status

- Version: Draft 0.1
- Language: English
- Canonical: Yes
- Last updated: 2026-07-12

## 1. Purpose

Agentic Change Audit defines a vendor-neutral and evidence-first method for determining whether a software change is sufficiently understood and verified to proceed toward acceptance, merge, deployment, or release.

The standard evaluates the complete change, not only the quality of individual code lines.

## 2. Normative Language

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

- **MUST / MUST NOT**: required for conformance.
- **SHOULD / SHOULD NOT**: recommended unless a documented reason justifies deviation.
- **MAY**: optional.

## 3. Applicability

The standard applies to:

- pull requests;
- local working-tree changes;
- release candidates;
- documentation-only changes;
- application code;
- configuration;
- infrastructure;
- database and migration changes;
- human-written changes;
- AI-generated changes; and
- mixed human and AI changes.

## 4. Audit Contract

An audit is valid only when all of the following are identified:

1. repository identity;
2. base reference;
3. target branch or change set;
4. target commit SHA or equivalent immutable identity;
5. change request, requirements, or approved intent;
6. expected scope;
7. actual diff;
8. required verification;
9. available evidence; and
10. human verification requirements.

The auditor MUST NOT infer missing identity or scope information when doing so could alter the result.

## 5. Core Principles

### 5.1 Evidence First

Claims MUST be supported by inspectable evidence. Confidence, familiarity, or an agent's assertion is not a substitute for evidence.

### 5.2 Agent Neutral

The standard MUST remain usable by different AI agents and by human reviewers. Agent-specific instructions belong in integration layers, not in the normative core.

### 5.3 Fixed Target Identity

Every result MUST bind to a specific target identity. A pull request number alone is insufficient.

### 5.4 Explicit Scope Control

The auditor MUST compare the requested change with the actual diff and identify omitted work, unrelated work, unnecessary files, and excessive implementation.

### 5.5 Audit Invalidation

A result MUST be treated as invalid when its bound target, base-dependent diff, requirements, or required evidence materially changes.

### 5.6 Explicit Stop Conditions

The auditor MUST stop rather than manufacture a verdict when the audit target or evidence cannot be established reliably.

### 5.7 Human Responsibility

The standard supports decisions. It does not transfer final responsibility for merge, deployment, release, security, legal, or operational approval.

## 6. Required Audit Phases

### Phase 1: Establish Identity

Confirm:

- repository;
- base;
- target branch;
- target HEAD;
- pull request identity, when applicable;
- clean or dirty working-tree state; and
- whether the retrieved diff matches the intended target.

Failure to establish identity results in `NOT AUDITABLE`.

### Phase 2: Establish Requested Scope

Identify:

- the source of requirements;
- requested files, behavior, and constraints;
- prohibited changes;
- required checks;
- required human review; and
- explicit stop conditions.

If no reliable requirements or approved intent exists, the audit is `NOT AUDITABLE`.

### Phase 3: Inspect the Actual Change

Review the complete diff and classify affected areas, including:

- application behavior;
- public interfaces;
- authentication and authorization;
- data and migrations;
- dependencies;
- configuration;
- infrastructure and deployment;
- tests;
- documentation; and
- generated or sensitive files.

### Phase 4: Execute or Verify Checks

Run or verify the checks required by the change type, such as:

- formatting and diff checks;
- linting;
- type checking;
- compilation or build;
- unit, integration, and regression tests;
- schema validation;
- migration safety checks;
- security-relevant checks; and
- documentation link or structure checks.

A check MUST NOT be reported as passed unless its result is available and attributable to the audited target.

### Phase 5: Evaluate Findings

Each finding SHOULD record:

- identifier;
- title;
- severity;
- affected location;
- observed evidence;
- expected behavior;
- impact;
- required action; and
- whether it blocks acceptance.

### Phase 6: Issue a Verdict

The auditor MUST use one of these verdicts:

- `PASS`
- `PASS WITH COMMENTS`
- `CHANGES REQUESTED`
- `BLOCKED`
- `NOT AUDITABLE`

The verdict MUST follow `verdict-criteria.md`.

### Phase 7: Record Validity

The result MUST record:

- audited target HEAD;
- base;
- audit timestamp;
- evidence limitations;
- incomplete human checks;
- invalidation conditions; and
- next permitted action.

## 7. Audit Domains

The auditor SHOULD consider all domains materially affected by the change:

| Domain | Minimum concern |
|---|---|
| Identity | Correct repository, base, branch, HEAD, and pull request |
| Scope | Requested versus actual changes |
| Correctness | Requirements and behavior |
| Regression | Existing behavior and contracts |
| Security | Authentication, authorization, secrets, inputs, trust boundaries |
| Data | Integrity, migration, rollback, destructive effects |
| Dependencies | Added or updated packages, lockfiles, supply-chain impact |
| Architecture | Responsibilities, dependency direction, existing design |
| Quality | Readability, duplication, errors, maintainability |
| Tests | Required and relevant coverage |
| Build | Lint, typecheck, compile, package, build |
| Git hygiene | Untracked, generated, temporary, binary, or sensitive files |
| Operations | Deployment, configuration, cache, downtime, rollback |
| Documentation | User, developer, operational, and change documentation |
| Evidence | Commands, outputs, exit status, limitations |
| Merge readiness | Remaining blockers and human approval |

Not every domain requires the same depth. The auditor MUST explain material exclusions.

## 8. Mandatory Stop Conditions

The audit MUST stop when any of the following applies:

- the repository cannot be identified;
- the base or target cannot be established;
- the target HEAD is missing or changes during the audit;
- the actual diff cannot be obtained;
- the change request or approved intent is absent;
- the pull request and branch do not match;
- required source material is unavailable;
- required evidence belongs to a different target;
- evidence integrity cannot be trusted; or
- continuing would require unsafe or unauthorized access.

Use `NOT AUDITABLE` when the target or audit contract cannot be established.

Use `BLOCKED` when the target is established but required verification cannot be completed.

## 9. Prohibited Behavior

The auditor MUST NOT:

- claim a check was executed when it was not;
- treat a pull request number as an immutable target;
- silently ignore unrelated changes;
- expose secrets or include secret values in evidence;
- perform destructive production actions merely to obtain evidence;
- auto-merge or auto-deploy under this standard;
- present the result as a legal, regulatory, or security certification; or
- state that human review is unnecessary.

## 10. Minimum Result Structure

Every audit result MUST include:

```text
Repository:
Base:
Target branch or change set:
Target HEAD:
Requirements source:
Reviewed files:
Commands executed:
Command results:
Exit codes:
Checks not executed:
Evidence limitations:
Findings:
Human verification required:
Audit validity:
Verdict:
Next permitted action:
```

## 11. Non-Guarantees

Conformance with this standard does not guarantee:

- absence of defects;
- absence of vulnerabilities;
- regulatory or contractual compliance;
- production safety;
- fitness for a particular purpose; or
- correctness of external systems or evidence.

## 12. Support Boundary

The open-source project is provided as-is. Free installation support, implementation assistance, troubleshooting, and response-time guarantees are not included.

Professional implementation support, custom audit policies, workflow integration, and organizational adoption may be offered separately as paid services.
