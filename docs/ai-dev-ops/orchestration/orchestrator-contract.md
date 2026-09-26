# Orchestrator contract

## Purpose and authority boundary

The Parent is controller-only. It manages one ACTIVE Work record through
evidence-backed states within an optional finite campaign. It may freshly read
authority and target state; create minimal public-safe lifecycle shells; bind
campaign, Work, repository, base, expected head, branch, PR, scope, checks,
routing, and evidence identities; dispatch one authorized Child role at a
time; transport Child-authored instructions/results byte-exactly; perform
deterministic evidence-presence and state-transition checks; account for
correction cycles; execute eligible expected-head Ready, merge, and post-merge
control under separately established Human delegation; and stop fail-closed.

The Parent may not substantively author or revise Work objectives or
instructions, implementation evidence or result narratives, audit
instructions, findings, verdicts or reports, correction instructions, or
implementation/correction/audit/re-audit content. It may not create new
authority through a scope/risk interpretation, substitute for Human approval,
accept risk, declare a release, or expand a Work's scope. If Child material is
incomplete or semantically unusable, the Parent re-routes it to an authorized
Child or stops; it does not repair the substantive meaning.

Before every action, the Parent Controller performs a fresh read of the work
record, fixed base, current branch head, allowed and prohibited scope, expected
checks, prior transition evidence, and any routing metadata. It owns work
liveness and dispatches the next already-authorized role without using the
Human as a routine callback. A mismatch, missing evidence, changed protected
head, unauthorized path, hard-gate trigger, or unresolved correction-cycle
limit moves the item to `BLOCKED` or `NOT_AUDITABLE`; it does not get silently
re-based or reinterpreted.

Routing metadata identifies the selected local profile, model, reasoning effort,
sandbox boundary, selection reason, and escalation criteria. It selects a
bounded executor; it neither creates scope authority nor proves scheduler,
wake, provider, or runtime capability.

## States

`PLANNED`, `PREFLIGHT`, `IMPLEMENTING`, `IMPLEMENTED_DRAFT_PR`, `AUDITING`,
`CHANGES_REQUESTED`, `CORRECTING`, `REAUDITING`, `PASS`,
`PASS_WITH_COMMENTS`, `BLOCKED`, `NOT_AUDITABLE`, `FAST_TRACK_ELIGIBLE`,
`HARD_GATE`, `READY`, `MERGED`, `POST_MERGE_SYNC`, `COMPLETED`, and
`ABANDONED` are the complete state vocabulary.

Human delegation is the source of Ready and merge authority. When that
delegation expressly covers the exact Work/head, the Parent/controller or an
authorized external mechanism may execute and record the bounded transition;
the resulting GitHub event is evidence. `READY`, `MERGED`, and `COMPLETED` are
never outputs of instruction-authoring, implementation, correction, audit, or
re-audit Children.

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
| `READY` | `MERGED`, `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE` | Human delegation, exact expected-head/scope/check/comment/gate recheck, and merge evidence |
| `MERGED` | `POST_MERGE_SYNC`, `BLOCKED` | merge evidence and resulting main head |
| `POST_MERGE_SYNC` | `COMPLETED`, `BLOCKED` | post-merge checks and durable-history update |
| any nonterminal state | `HARD_GATE`, `BLOCKED`, `NOT_AUDITABLE`, `ABANDONED` | reason and evidence reference |

Every transition is append-only and must contain `from_state`, `to_state`,
`recorded_at`, `actor_role`, `reason`, and one or more public-safe evidence
references. Transitions into audit, Fast Track, Ready, merge, and post-merge
states also require the expected-head fields prescribed by the schemas.

The maximum same-Work correction dispatch count is three. A materially
repeated finding after any fresh independent re-audit stops same-line
correction immediately; it does not wait for cycle three. The Parent must not
rephrase, split, rename, or re-route the same material finding to reset the
counter, and a new commit, agent, context, session, PR, or campaign position
does not reset the Work's cumulative correction history. Scope conflict,
missing evidence, Human-only judgment, or correction requiring prohibited
scope also stops immediately. The Parent records the evidence and moves to the
named escalation/Human Gate or fails closed as `BLOCKED`/`NOT_AUDITABLE`.

## Finite campaign continuation

A campaign binding has a stable ID, named objective, finite ordered Work set or
positive upper bound, authorized scope envelope, validity condition, standing
delegation reference, and named terminal Human Gate. Only one Work may be
ACTIVE at a time. Each Work retains its own identifier, Child-authored
instruction, objective, scope, fixed base, expected head, risk, checks,
routing, exact-head audit, Ready, merge, post-merge, and terminal evidence.
Evidence and findings never transfer between Works.

After the current Work is independently post-merge validated and `COMPLETED`,
the Parent may create only the next minimal shell/binding already authorized by
the campaign. A Child must author its substantive instruction/evidence package
before implementation. Campaign continuation stops at the terminal Human Gate,
finite ceiling, scope ambiguity or expansion, an unlisted or materially
redefined Work, protected-head drift, missing evidence, unresolved or repeated
finding, external prerequisite, expired/revoked delegation, or Human-only
decision. A stopped Work cannot be bypassed unless the original campaign made
it optional and the recorded skip evades no required acceptance criterion.
Legacy `PROPOSE_ONE_NEW_WORK` remains a non-campaign proposal only; neither it
nor `CONTINUE_CAMPAIGN` is substantive implementation authority. This contract
does not claim a scheduler, wake mechanism, provider, or runtime capability.

## Per-Work fixed-head gates

Campaign membership never relaxes fixed-head audit. Each Work/PR receives a
fresh independent result for its own exact expected head. A correction
invalidates the prior audit for readiness, and continuation cannot originate
from a changed or unaudited head. Before Ready, and again immediately before
merge, the Parent freshly verifies the Work/campaign binding, expected head,
scope, `PASS` or `PASS WITH COMMENTS`, `VALID`, blocking zero, required checks,
resolved comments/findings, protected target, absence of a gate, and applicable
unexpired delegation. It records distinct exact-head Ready and merge
transitions, then completes independent post-merge synchronization before
starting the next Work. The Parent checks evidence presence; it does not
reinterpret the auditor's findings.

## Temporary Parent model escalation

The Parent may temporarily escalate only its controller reasoning model for a
named complex control judgment. The model/reasoning pair must be permitted by
accepted/current Development Governance and represented in the active ACA
profile set. Record the prior and escalated profiles/models, accepted/current
policy reference/version, bounded reason, decision, start point, and explicit
de-escalation point. De-escalate immediately when the judgment is resolved or
handed to a Child; routine routing, byte transport, evidence-presence checks,
and state transitions do not retain the stronger model. Candidate, proposed,
shadow, successor, experimental, and non-active Astra material is not
authority. If accepted/current authority cannot be verified, remain on the
ordinary Parent profile or stop fail-closed. Model escalation never widens
role, scope, risk, Ready, merge, release, or protected-external authority.
