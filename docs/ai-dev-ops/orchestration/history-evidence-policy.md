# History and evidence policy

## Two ledgers

The active private ledger may contain operational assignment detail and other
sensitive context needed by authorized people. It is outside this repository.
The public durable history in this repository contains only the minimum
public-safe evidence needed to understand a work item's state, immutable
identity, scope, checks, decision type, and result.

Never copy secrets, credentials, access instructions, private filesystem paths,
private links, personal data, customer data, private deliberation, or raw
external-system payloads into durable history.

## Evidence rules

Evidence references must be stable, public-safe identifiers or repository-
relative references. Each reference states what it proves and when it was
observed. Missing evidence is recorded as missing; it is not inferred as a
pass. Records are append-only: correct an error by adding a later transition or
result, not by erasing history.

## Legacy pull requests

Legacy pull requests #16 and #17 are recorded only as non-mutated conditions.
This bootstrap does not alter their branches, commits, bodies, checks, or
evidence, and does not reproduce private credential material associated with
them.
