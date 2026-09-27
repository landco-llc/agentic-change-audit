# Fast Track policy

Fast Track is accepted/current standing Human delegation for a finite campaign
envelope. The delegation identifies a finite ordered Work set or explicit
finite upper bound, scope envelope, validity condition, and terminal Human
Gate. It instantiates separately for each listed Work and exact head after the
prerequisites below are satisfied; it is not AI authority, automatic risk
acceptance, blanket merge permission, release/submission/publication/deployment
permission, or authority for another protected external effect.

## Eligibility

The Controller may enter `FAST_TRACK_ELIGIBLE` only when all of these are
evidenced in the work record:

1. Fresh Read binds the Work record, campaign position, current branch head,
   expected head, allowed/prohibited scope, open comments/findings, checks,
   delegation validity, and protected target state.
2. An independent fixed-head result has the public ACA verdict `PASS` or
   `PASS WITH COMMENTS`. The corresponding control states are `PASS` and
   `PASS_WITH_COMMENTS` respectively; verdict strings are public audit
   outcomes, while control-state identifiers are internal orchestration values.
3. Audit validity is `VALID` and blocking finding count is zero.
4. The accepted/current campaign delegation explicitly covers this Work or its
   finite authorized position, exact expected head, allowed scope,
   expiration/validity condition, and responsible Human authority.
5. Required checks are complete and non-blocking.
6. No hard-gate trigger, protected-head mismatch, unresolved audit/review
   comment or finding, prohibited-scope change, Human-only decision, or
   external prerequisite exists.
7. Eligibility is not Ready: the next authorized lifecycle action, if every
   predicate remains true, is a distinct `READY` transition for this exact
   expected head.

Immediately before `READY` and again before merge, the Controller freshly
verifies the expected head, scope, checks, comments/findings, protected target,
gate state, and delegation validity. Any difference is `NOT_AUDITABLE`,
`BLOCKED`, or `HARD_GATE`, as appropriate, and requires the corresponding fresh
decision or re-audit. A campaign PASS is never inferred: each Work and changed
head receives its own independent audit result and exact-head transitions.

## Merge and post-merge

The accepted/current Human delegation is the source of authority. This policy
itself grants no Ready or merge authority and names no executor by default. If
a separate exact-Work/head delegation already names the Parent/controller or
an authorized external mechanism as the bounded executor, that executor may
record the Ready transition and expected-head merge only after every predicate
above is satisfied and read back after each transition. The resulting GitHub
merge event is evidence. Neither instruction-authoring, implementation,
correction, audit, nor re-audit Children may execute or authorize Ready or
merge.

After merge, independently move to `POST_MERGE_SYNC` and record the resulting
main head, required post-merge checks, and public-safe durable-history update
before `COMPLETED` or starting the next campaign Work. Fast Track never grants
release, submission, publication, deployment, portal mutation,
provider/credential/organization/permission mutation, or other
protected-external-effect authority.
