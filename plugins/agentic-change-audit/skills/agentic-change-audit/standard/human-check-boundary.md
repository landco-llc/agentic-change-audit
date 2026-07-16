# Human Check Boundary

## Status

- Version: Draft 0.1
- Language: English
- Canonical: Yes
- Last updated: 2026-07-12

## 1. Purpose

This document defines decisions and observations that require human responsibility or human verification.

The standard does not declare humans unnecessary.

## 2. Final Responsibility

A human authorized by the relevant project or organization remains responsible for final decisions concerning:

- merge;
- production deployment;
- release;
- destructive data operations;
- security acceptance;
- legal or regulatory compliance;
- contractual obligations;
- privacy and personal data;
- financial transactions and billing;
- operational risk; and
- business acceptance.

An AI agent MAY recommend a decision but MUST NOT claim to hold organizational authority.

## 3. Mandatory Human Check Areas

Human verification is normally mandatory for materially affected areas including:

- production deployment;
- data deletion or irreversible migration;
- authentication or authorization behavior;
- payment, billing, or financial calculation;
- personal or confidential information;
- legal, regulatory, or contractual interpretation;
- major security risk acceptance;
- destructive infrastructure actions;
- externally visible brand, copy, visual, or accessibility quality;
- safety-critical behavior; and
- final merge or release approval.

Organizations MAY add mandatory areas.

## 4. When Automation Is Insufficient

A human check is required when the result depends on:

- subjective visual judgment;
- business intent not fully encoded in requirements;
- legal authority;
- production credentials or restricted access;
- customer-specific context;
- ethical or reputational judgment;
- physical-world observation;
- acceptance of residual risk; or
- an irreversible action.

## 5. Human Check Record

Each required human check SHOULD record:

```text
Check:
Reason automation is insufficient:
Required role:
Status:
Evidence or observation:
Acceptance gate:
Owner:
```

Allowed status values:

- `COMPLETE`
- `PENDING`
- `NOT REQUIRED`
- `DEFERRED TO APPROVED GATE`

## 6. Verdict Effect

- A mandatory check that is `PENDING` before acceptance requires `BLOCKED`.
- A check `DEFERRED TO APPROVED GATE` MAY allow `PASS WITH COMMENTS` only when acceptance at the current gate does not require it.
- An optional check MAY be recorded without blocking.
- A failed human check that requires implementation change normally results in `CHANGES REQUESTED`.

## 7. Prohibited Claims

The audit MUST NOT claim:

- that human review is unnecessary;
- that legal compliance is certified;
- that security is guaranteed;
- that production deployment is safe without required authorization;
- that a subjective visual result is correct without observation; or
- that an AI agent accepted organizational risk.

## 8. Separation of Roles

Where practical, the person implementing a material change SHOULD NOT be the sole final approver.

For high-risk changes, organizations SHOULD separate:

- implementation;
- audit;
- business approval; and
- deployment authorization.

This separation is recommended but not required by the open-source core.

## 9. Professional Services Boundary

Paid implementation or consulting support does not transfer the client's final authority or responsibility unless a separate written agreement explicitly defines it.
