# Verdict Criteria

## Status

- Version: Draft 0.1
- Language: English
- Canonical: Yes
- Last updated: 2026-07-12

## 1. Purpose

This document defines the five allowed audit verdicts and the conditions for issuing each verdict.

Verdict and finding severity are separate concepts.

## 2. Allowed Verdicts

### 2.1 PASS

Use `PASS` only when all of the following are true:

- the audit target is valid and fixed;
- no blocking finding exists;
- all required non-human checks are complete and attributable to the target;
- all mandatory human checks required before acceptance are complete;
- no material evidence limitation affects the decision;
- the change is within approved scope; and
- the change may proceed to the next approved step.

Minor observations that do not require tracking SHOULD NOT be added merely to avoid issuing a clean `PASS`.

### 2.2 PASS WITH COMMENTS

Use `PASS WITH COMMENTS` when:

- the target is valid;
- no blocking finding exists;
- all checks required for acceptance are complete;
- remaining items are non-blocking;
- remaining items do not materially change safety or scope; and
- the change may proceed, with comments recorded.

Typical examples:

- low-severity maintainability improvements;
- optional documentation improvements;
- minor naming or consistency observations; or
- a non-mandatory human follow-up.

Do not use this verdict to hide incomplete mandatory verification.

### 2.3 CHANGES REQUESTED

Use `CHANGES REQUESTED` when:

- the target is valid and auditable; and
- one or more findings require modification before acceptance.

Typical causes:

- incorrect behavior;
- missing required work;
- unauthorized or excessive scope;
- regression;
- security weakness;
- unsafe migration;
- failing required test or build;
- material documentation error; or
- a High or Critical finding.

The current target MUST NOT be accepted. A new or focused re-audit is required after changes.

### 2.4 BLOCKED

Use `BLOCKED` when:

- the target identity and requested scope are established;
- the audit can be partially performed; but
- a required verification or decision dependency cannot be completed.

Typical causes:

- required CI cannot be executed;
- a required external system is unavailable;
- the reviewer lacks necessary access;
- a mandatory production-safe check cannot be performed;
- mandatory human verification is pending; or
- required source material exists but is inaccessible.

`BLOCKED` does not imply that the implementation is defective.

No merge or release readiness claim may be made while the blocking dependency remains unresolved.

### 2.5 NOT AUDITABLE

Use `NOT AUDITABLE` when a reliable audit target or audit contract cannot be established.

Typical causes:

- repository, base, branch, or HEAD is unknown;
- the diff cannot be retrieved;
- the requirements or approved intent do not exist;
- the pull request does not match the branch;
- evidence belongs to a different target;
- the target changed during the audit;
- source material is internally contradictory; or
- evidence integrity cannot be trusted.

The auditor MUST NOT issue implementation-quality conclusions beyond clearly labeled preliminary observations.

## 3. Decision Order

Apply the following order:

1. If target identity or the audit contract is invalid: `NOT AUDITABLE`.
2. If the target is valid but required verification cannot be completed: `BLOCKED`.
3. If the target is valid and modification is required: `CHANGES REQUESTED`.
4. If the target is acceptable with non-blocking recorded items: `PASS WITH COMMENTS`.
5. Otherwise: `PASS`.

When multiple conditions apply, use the earliest applicable verdict in this order.

## 4. Severity Relationship

Recommended finding severity:

| Severity | Meaning | Default verdict effect |
|---|---|---|
| Critical | Data loss, major compromise, severe outage, privilege bypass | `CHANGES REQUESTED` |
| High | Material defect, regression, contract breach, unsafe change | `CHANGES REQUESTED` |
| Medium | Meaningful but contained problem requiring correction | Usually `CHANGES REQUESTED` |
| Low | Non-blocking improvement | Usually `PASS WITH COMMENTS` |
| Comment | Information, optional improvement, human note | `PASS` or `PASS WITH COMMENTS` |

Exceptions MUST be explained.

A verdict may be `BLOCKED` or `NOT AUDITABLE` even when no finding exists.

## 5. Human Verification

If a mandatory human check required before acceptance is incomplete, the result MUST be `BLOCKED`.

If the human check is explicitly optional or deferred to a later approved gate, it MAY be recorded under `PASS WITH COMMENTS`.

## 6. Next Permitted Action

Every result MUST state one next permitted action.

Examples:

- `PASS`: eligible for human merge approval.
- `PASS WITH COMMENTS`: eligible for human merge approval with comments retained.
- `CHANGES REQUESTED`: modify the target, then re-audit.
- `BLOCKED`: resolve the named dependency, then resume or re-run the audit.
- `NOT AUDITABLE`: establish a valid target and requirements, then start a new audit.

## 7. Prohibited Substitutions

Do not substitute:

- confidence percentages for verdicts;
- informal phrases such as "looks good";
- GitHub review states for this standard's verdicts; or
- a severity label for the overall verdict.
