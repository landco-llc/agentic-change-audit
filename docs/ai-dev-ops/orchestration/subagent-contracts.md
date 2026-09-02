# Separated subagent contracts

## Controller

The Parent Controller performs fresh reads, creates public-safe work records,
selects bounded routing metadata, assigns one role at a time, checks
state-transition evidence, and continues already-authorized in-session work.
It does not implement, audit its own implementation, correct its own findings,
or grant human-only authority. Routing configuration is not evidence that a
scheduler, wake service, provider, or runtime is available.

## Implementation agent

The implementation agent changes only the approved allowed scope, records the
resulting head and checks, and returns a bounded result to the Parent. It must
not audit its own work, mark it Ready, merge it, publish it, or generate broader
work.

## Independent audit agent

The audit agent reads the exact expected head and approved evidence without
mutation. It reports one of the permitted audit outcomes with evidence. If the
head differs, it reports `NOT_AUDITABLE`; it does not inspect a substitute head.

## Correction agent

The correction agent addresses only recorded findings within the existing
allowed scope. A correction creates a new head and requires `REAUDITING` by a
fresh independent audit agent. The Parent records the cycle count. At three
correction cycles, or on a repeated material finding, scope conflict, missing
evidence, or human-only decision, the Parent stops same-line correction and
moves the item to the named escalation or `HARD_GATE`.

## Fresh re-audit agent

The fresh re-audit agent is independent from the correction agent. It fixes its
review target to the new expected head and follows the independent-audit
boundary. A prior PASS does not carry forward to a changed head.

## Human gate

Human gates are explicit stop conditions. They can authorize or decline the
next named transition, but must not be represented as an AI decision. The
record stores only public-safe decision evidence and never private deliberation
or credentials.
