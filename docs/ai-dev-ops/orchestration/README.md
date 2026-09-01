# Single-launch orchestration bootstrap

This directory defines a public-safe, evidence-driven control model for one
bounded work item at a time. It coordinates work; it does not replace the
repository's audit standard, runtime controls, or human release authority.

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

Use the two JSON schemas as the canonical field contract. A record or result is
not authority to merge, release, deploy, broaden scope, or accept risk.

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
and role separation. For work results it checks transition identity and state,
applicable target and pull-request identity, permitted role outputs, allowed
scope, blocking check statuses, bounded next-work fields, and actor-role
alignment. Optional `policy_version` and `routing` metadata bind a work to a
local profile when supplied; records that predate this metadata remain valid.
