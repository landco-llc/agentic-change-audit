# Separated subagent contracts

## Controller

The Parent Controller performs fresh reads, creates only minimal public-safe
lifecycle shells/bindings, selects bounded routing metadata, assigns one role
at a time, transports Child-authored material byte-exactly, checks deterministic
state/evidence predicates, accounts for correction cycles, and continues only
already-authorized bounded Work. It does not substantively author or repair a
Work instruction, implementation evidence/result narrative, audit instruction
or report, finding, verdict, correction instruction, or
implementation/correction/audit/re-audit content. It does not implement, audit
its own implementation, correct its own findings, accept risk, or grant
Human-only authority. Routing configuration is not evidence that a scheduler,
wake service, provider, or runtime is available. Parent delegates tests and
substantive task-plane artifact materialization/publication. Current routes,
Parent-low semantics, generation exceptions and Work-scoped Cloud/Local
admission are referenced in the thin
[model-selection addendum](../model_selection_policy.md); no route widens
authority or establishes project activation.

## Instruction/evidence-authoring Child

This non-audit Child authors the complete executable Work instruction and
evidence package: exact paths, required semantics, preserved invariants,
checks, and acceptance criteria. It is distinct from the Parent and from the
independent audit context. It may not implement unless a separately
authoritative role contract explicitly combines non-audit authoring and
implementation for that Work, and it may not audit, correct, mark Ready,
merge, release, submit, publish, or deploy. Its continuation output is not
authority to begin the next Work until the Parent verifies the binding and
dispatches the appropriate Child.

## Implementation agent

The implementation agent changes only the approved allowed scope against the
Child-authored executable instruction, records the resulting head and checks,
and returns a bounded result to the Parent. It must not audit its own work,
mark it Ready, merge it, release, submit, publish, deploy, or generate broader
Work.

## Independent audit agent

The audit agent reads the exact expected head and approved evidence without
mutation as a dedicated fresh independent Child of a control-plane-only Audit
Parent in a NEW separate formal Audit Work/context. It owns a separate
Result/evidence/judgment and reports a permitted outcome with provenance and
independent reproduction or explicit limitations. Producer-parent review is
SELF_VALIDATION regardless of model or inherited history. A delegated
controller qualifies only with supported separate-context/control-surface
and independently admitted Parent/Child evidence; naming it Audit Parent is
insufficient. `SELF_VALIDATION_PASS != INDEPENDENT_AUDIT_PASS`. If the head
differs, it reports `NOT_AUDITABLE`; it
does not inspect a substitute head. Campaign membership and an earlier Work's
PASS do not relax or carry forward this fixed-head boundary. The Audit Child
never corrects, marks Ready or merges.

## Correction agent

The correction instruction is authored by a Child from immutable fixed-audit
findings. A separate correction agent addresses only those findings within the
existing allowed scope. A correction creates a new head and requires
`REAUDITING` by a fresh independent audit agent. The Parent records the
cumulative cycle count. At three correction dispatches, or immediately when a
fresh re-audit repeats a material finding, or on scope conflict, missing
evidence, prohibited-scope need, or Human-only decision, the Parent stops
same-line correction and moves the item to the named escalation or
`HARD_GATE`. A new SHA, branch, PR, agent, model, context, session, or campaign
position does not reset the count; neither does a host change. Three is a ceiling,
not permission to retry a surviving root: stricter current DG per-root limits
remain controlling. `MODEL_CHANGE != RETRY_RESET`.

## Fresh re-audit agent

The fresh re-audit agent is independent from the correction agent. A NEW
separate Audit Work/control-plane Parent dispatches its dedicated fresh
read-only Child against the new fixed expected HEAD/tree/base/scope, following
the independent-audit boundary. A prior PASS does not carry forward to a
changed head. No Child role
creates or executes Ready or merge authority.

## Validation and publication workers

An appropriately bound validation Child reproduces the exact-target checks,
keeps the target read-only and writes only assigned disposable scratch.
Producer validation is SELF_VALIDATION, with no formal independent-audit PASS.
A separately bound mechanical publication worker may materialize/publish only
exact authorized public-safe source bytes, verify immutable readback and
return evidence. It neither reconstructs substantive meaning/judgment nor
corrects the target, marks Ready, merges or acquires protected-effect authority.
`CHILD_COMPLETE != PARENT_COMPLETE`, `READY_AUTHORITY != MERGE_AUTHORITY`,
`HOST_CHANGE != AUTHORITY_EXPANSION`, `CANDIDATE != ACTIVE` and
`MAIN_RESIDENT != ACTIVE_AUTHORITY` remain controlling.

## Human gate

Human gates are explicit stop conditions. They can authorize or decline the
next named transition, but must not be represented as an AI decision. The
record stores only public-safe decision evidence and never private deliberation
or credentials.
