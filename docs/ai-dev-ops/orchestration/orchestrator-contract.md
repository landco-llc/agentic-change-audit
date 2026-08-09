# Orchestrator contract

## Purpose and authority boundary

The Controller manages one work record through evidence-backed states. It may
route work, inspect public-safe evidence, and stop work. It may not substitute
for human approval, accept risk, declare a release, or expand a work item's
scope.

Before every action, the Controller performs a fresh read of the work record,
fixed base, current branch head, allowed and prohibited scope, expected checks,
and prior transition evidence. A mismatch, missing evidence, changed protected
head, unauthorized path, hard-gate trigger, or unresolved correction-cycle
limit moves the item to `BLOCKED` or `NOT_AUDITABLE`; it does not get silently
re-based or reinterpreted.

## States

`PLANNED`, `PREFLIGHT`, `IMPLEMENTING`, `IMPLEMENTED_DRAFT_PR`, `AUDITING`,
`CHANGES_REQUESTED`, `CORRECTING`, `REAUDITING`, `PASS`,
`PASS_WITH_COMMENTS`, `BLOCKED`, `NOT_AUDITABLE`, `FAST_TRACK_ELIGIBLE`,
`HARD_GATE`, `READY`, `MERGED`, `POST_MERGE_SYNC`, `COMPLETED`, and
`ABANDONED` are the complete state vocabulary.

`READY`, `MERGED`, and `COMPLETED` are recorded only after the responsible
human or external system provides the corresponding evidence. They are never
outputs of implementation or audit agents.

## Allowed transitions and evidence

| From | To | Mandatory evidence and control fields |
| --- | --- | --- |
| `PLANNED` | `PREFLIGHT`, `HARD_GATE`, `ABANDONED` | work record, scope and risk review |
| `PREFLIGHT` | `IMPLEMENTING`, `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE` | fixed base, branch, scope, checks |
| `IMPLEMENTING` | `IMPLEMENTED_DRAFT_PR`, `HARD_GATE`, `BLOCKED` | implementation head, changed-file evidence, checks |
| `IMPLEMENTED_DRAFT_PR` | `AUDITING`, `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE` | draft review reference and fixed expected head |
| `AUDITING` | `PASS`, `PASS_WITH_COMMENTS`, `CHANGES_REQUESTED`, `BLOCKED`, `NOT_AUDITABLE` | independent fixed-head result |
| `CHANGES_REQUESTED` | `CORRECTING`, `HARD_GATE`, `ABANDONED` | findings and correction-cycle count |
| `CORRECTING` | `REAUDITING`, `HARD_GATE`, `BLOCKED` | new implementation head and correction evidence |
| `REAUDITING` | `PASS`, `PASS_WITH_COMMENTS`, `CHANGES_REQUESTED`, `BLOCKED`, `NOT_AUDITABLE` | new independent fixed-head result |
| `PASS`, `PASS_WITH_COMMENTS` | `FAST_TRACK_ELIGIBLE`, `HARD_GATE`, `READY`, `ABANDONED` | audit result; human decision where required |
| `FAST_TRACK_ELIGIBLE` | `READY`, `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE` | standing delegation, exact expected head, required checks |
| `HARD_GATE` | `PREFLIGHT`, `IMPLEMENTING`, `AUDITING`, `CORRECTING`, `READY`, `BLOCKED`, `ABANDONED` | named prerequisite satisfaction |
| `READY` | `MERGED`, `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE` | human merge authority and protected-head recheck |
| `MERGED` | `POST_MERGE_SYNC`, `BLOCKED` | merge evidence and resulting main head |
| `POST_MERGE_SYNC` | `COMPLETED`, `BLOCKED` | post-merge checks and durable-history update |
| any nonterminal state | `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE`, `ABANDONED` | reason and evidence reference |

Every transition is append-only and must contain `from_state`, `to_state`,
`recorded_at`, `actor_role`, `reason`, and one or more public-safe evidence
references. Transitions into audit, Fast Track, Ready, merge, and post-merge
states also require the expected-head fields prescribed by the schemas.

## Bounded next work

The Controller may produce at most one next-work proposal, only after a
terminal result or a named hard gate. It must have a new identifier, a stated
objective, its own scope and risk classification, and must not mutate or
reinterpret the completed work record. A proposal is `PLANNED`, not an approved
implementation instruction.
