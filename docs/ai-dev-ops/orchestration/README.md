# Finite campaign orchestration

This directory defines a public-safe, evidence-driven control model for a
finite campaign of separately bounded Works, with only one Work ACTIVE at a
time. It coordinates work; it does not replace the repository's audit
standard, runtime controls, or Human release authority, and it does not claim
scheduler, wake, provider, or runtime capability.

## Documents

- [Orchestrator contract](orchestrator-contract.md): state model and Controller duties.
- [Subagent contracts](subagent-contracts.md): separated-role boundaries.
- [Fast Track policy](fast-track-policy.md): standing human delegation limits.
- [History and evidence policy](history-evidence-policy.md): public/private separation.
- [Work-record schema](work-record.schema.json): planning and execution input.
- [Work-result schema](work-result.schema.json): bounded result output.
- [Current control state](current-control-state.md): initial non-mutating control snapshot.
- [Local model-selection addendum](../model_selection_policy.md): accepted
  local profile reference; it is not a scheduler, wake, or provider-capability
  claim.

Use the two JSON schemas as the canonical field contract. Historical one-Work
records remain valid. A Work record may additionally bind a finite campaign by
campaign ID, objective, ordered Work IDs or finite limit, current Work and
position, terminal Human Gate, scope envelope, validity condition, standing
delegation reference, and one-ACTIVE-Work evidence. A Controller result may use
`CONTINUE_CAMPAIGN` only after the current Work's completed post-merge
transition and must bind the finite order, next position, terminal gate,
campaign authority, and cumulative correction history. Such a result is only
a lifecycle continuation binding; it is never the substantive instruction for
the next Work.

The schemas and validator fail closed. A record or result is not authority to
merge, release, submit, publish, deploy, broaden scope, accept risk, or perform
another protected external effect.

## Offline validation

Validate work records with the immutable work-record schema and orchestration
semantic rules:

```sh
python3 scripts/validate-orchestration.py --kind record path/to/work-record.json
```

Validate work results with the immutable work-result schema and result
semantic rules:

```sh
python3 scripts/validate-orchestration.py --kind result path/to/work-result.json
```

The validator is deterministic, network-free, and read-only. It checks Draft
2020-12 schema conformance with date-time formats, rejects duplicate JSON keys,
and reports stable diagnostics for work-record continuity, final state,
identity, transition vocabulary, required target identity, correction cycles,
campaign binding, one-ACTIVE-Work exclusivity, Parent/Child role separation,
and actor-role alignment. For work results it also checks applicable target and
pull-request identity, permitted role outputs, allowed scope, blocking check
statuses, finite continuation order and bounds, terminal-gate presence, and
persistent-finding bypass. Optional `policy_version`, `routing`, and `campaign`
metadata are backward-compatible; records that predate them remain valid.
