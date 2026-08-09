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

Use the two JSON schemas as the canonical field contract. A record or result is
not authority to merge, release, deploy, broaden scope, or accept risk.
