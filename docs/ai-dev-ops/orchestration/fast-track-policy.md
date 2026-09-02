# Fast Track policy

Fast Track is a standing human delegation to merge one bounded, expected-head
change after the listed prerequisites are satisfied. It is not an AI authority,
automatic risk acceptance, blanket merge permission, or release permission.

## Eligibility

The Controller may enter `FAST_TRACK_ELIGIBLE` only when all of these are
evidenced in the work record:

1. An independent fixed-head result has the public ACA verdict `PASS` or
   `PASS WITH COMMENTS`. The corresponding control states are `PASS` and
   `PASS_WITH_COMMENTS` respectively; verdict strings are public audit
   outcomes, while control-state identifiers are internal orchestration values.
2. The delegation identifies the work item, exact expected head, allowed scope,
   expiration or validity condition, and responsible human authority.
3. Required checks are complete and non-blocking.
4. No hard-gate trigger, protected-head mismatch, unresolved comment, or
   prohibited-scope change exists.

Immediately before `READY` and again before merge, the Controller verifies the
expected head unchanged, the scope unchanged, and each required check still
applies. Any difference is `NOT_AUDITABLE` or `HARD_GATE`, as appropriate, and
requires a fresh human decision or re-audit.

## Merge and post-merge

Only the delegated human or authorized external mechanism can create merge
evidence. After merge, move to `POST_MERGE_SYNC` and record the resulting main
head, required post-merge checks, and public-safe durable-history update before
`COMPLETED`. Fast Track never grants release or deployment authority.
