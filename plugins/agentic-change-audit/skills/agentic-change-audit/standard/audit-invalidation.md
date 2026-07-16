# Audit Invalidation

## Status

- Version: Draft 0.1
- Language: English
- Canonical: Yes
- Last updated: 2026-07-12

## 1. Purpose

This document defines when an audit result stops being valid and when a new audit or focused re-audit is required.

## 2. Binding Model

An audit result is bound to:

```text
Repository
+ Base
+ Target HEAD
+ Requirements
+ Required evidence
```

The result is valid only for the combination recorded in the audit.

## 3. Mandatory Invalidation Events

The result MUST be treated as invalid when any of the following occurs:

- target HEAD changes;
- commits are added, removed, amended, rebased, or force-pushed;
- the base changes and the effective diff materially changes;
- requirements or acceptance criteria materially change;
- requested scope expands or contracts;
- a reviewed file changes;
- required configuration, dependency resolution, or generated output changes;
- evidence is discovered to belong to another target;
- required evidence is corrected or withdrawn;
- a mandatory human check produces a materially different result;
- the audit procedure is found to have relied on corrupted or untrusted evidence; or
- the recorded repository or pull request identity is wrong.

The prior result MUST NOT be presented as current.

## 4. Events That Do Not Automatically Invalidate

The following do not automatically invalidate the result when they do not alter target identity, diff, requirements, or required evidence:

- adding labels;
- assigning reviewers;
- editing non-normative pull request wording;
- adding discussion comments;
- changing project board state; or
- updating unrelated repository content outside the audited target.

The auditor SHOULD verify that the event is truly non-material.

## 5. Base Changes

A base branch update requires at least a diff comparison.

If the effective diff, merge result, dependency resolution, generated output, or required checks change, the audit is invalid.

If the base changed but the effective audited change and required evidence remain identical, the auditor MAY record a base-refresh verification rather than a full audit.

## 6. Re-audit Types

### 6.1 Full Re-audit

Use a full re-audit when:

- identity was previously invalid;
- requirements changed;
- the change set materially expanded;
- architecture, security, data, dependencies, or operations changed;
- multiple findings were fixed across broad areas; or
- confidence in prior evidence was lost.

### 6.2 Focused Re-audit

A focused re-audit MAY be used when:

- the prior audit target and findings are known;
- the new target is fixed;
- changes are limited to clearly identified remediation;
- unrelated diff changes are absent;
- relevant checks are re-run; and
- regression risk outside the focus area is evaluated.

A focused re-audit MUST still:

- verify the new target identity;
- compare old and new diffs;
- confirm no unrelated change;
- re-check each blocking finding;
- run materially affected tests or checks; and
- issue a new verdict bound to the new HEAD.

## 7. Status Terms

Recommended status terms:

- `VALID`: result still applies to the recorded target.
- `INVALIDATED`: a binding input changed.
- `SUPERSEDED`: a later audit replaced the result.
- `EXPIRED`: an organization-defined time policy ended validity.
- `UNKNOWN`: validity cannot be established.

Time-based expiration is optional and organization-specific.

## 8. Required Result Statement

Every audit result MUST include a statement similar to:

> This result is valid only for target HEAD `<sha>` against base `<base>`. Any material change to the target, effective diff, requirements, or required evidence invalidates this result.

## 9. Merge and Release Use

A merge or release decision MUST verify that the current target still matches the audited target.

"Previously audited" is not sufficient when the HEAD or effective diff has changed.
