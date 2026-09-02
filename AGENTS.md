# Agent Guidance

This is a public repository. Do not place secrets, personal data, private paths,
private links, credentials, customer information, or private ledger content in
repository files, commits, issues, or pull requests.

The Parent Controller starts each work item with a fresh read of its record,
fixed base, expected head, allowed scope, routing metadata, and required
evidence. It owns liveness: do not use routine Human callbacks between
authorized implementation, validation, audit, correction, and re-audit steps.
Route implementation, independent audit, correction, and fresh re-audit to
separate agents. An audit is fixed-head and read-only: a correction changes the
head and therefore requires a new independent re-audit.

Treat durable repository history as public-safe evidence only. Keep active
private operating detail in a separate private ledger; never copy it here.
Fast Track is standing human delegation for a bounded, expected-head merge. It
is not AI risk acceptance. Hard gates stop work until their named human or
external prerequisite is satisfied. Do not infer Ready, merge, release, or
deployment authority from an audit result.

See `docs/ai-dev-ops/orchestration/` for the machine-readable work-record and
work-result contracts, local routing reference, and control-state model.
