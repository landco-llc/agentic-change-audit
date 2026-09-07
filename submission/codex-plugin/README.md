# Codex Plugin submission preparation package

## Purpose

This directory contains repository-side preparation materials for the
skills-only Agentic Change Audit Codex Plugin. It does not change the Plugin
runtime, perform an external submission, or satisfy a human prerequisite.

## Current state

- Plugin version: `0.1.0-dev.3` (development).
- Marketplace identity: neutral `Agentic Change Audit marketplace`.
- Phase A pull request #16 accepted implementation head
  `581beae7e1c0dc0157ef32959e5d83925aa2ee27` and merged as
  `20f53ecfcd5ebc13b6a4b2ddea41f292f54778e0`.
- Phase C desktop evidence remains pending for this identity and version.
- Earlier desktop evidence is historical, superseded, and non-transferable.
- Every row in [human-prerequisites.md](human-prerequisites.md) remains
  `PENDING HUMAN CHECK`.

This state records repository evidence only. It does not establish an OpenAI
submission, approval, public listing, release, or deployment.
No portal action is performed or evidenced by this repository lane.
Portal state remains a human verification gate.

## Language contract

English is the sole canonical language for specifications, machine fields, and
exact tokens. Runtime narrative follows the user's conversation language unless
the user requests otherwise. Verdicts, severities, schema keys and values,
human-check statuses, audit statuses, and other exact machine tokens are never
translated or aliased. Localized ACA documents are explanatory distribution
content, not independent machine-semantic acceptance lanes. Translation parity is not a machine validation gate.

## Source identity

```text
Repository: landco-llc/agentic-change-audit
Base SHA:   20f53ecfcd5ebc13b6a4b2ddea41f292f54778e0
```

Evidence for one fixed identity does not transfer to another commit.

## Package field map

| Field | File | Notes |
|---|---|---|
| Submission type, listing, identity | [listing.json](listing.json) | Exact repository contract |
| Starter prompts | [starter-prompts.json](starter-prompts.json) | Exactly five |
| Test cases | [test-cases.json](test-cases.json) | Five positive and three negative |
| Availability | [availability.json](availability.json) | Recommendation only |
| Release notes | [release-notes.md](release-notes.md) | Development materials |
| Human prerequisites | [human-prerequisites.md](human-prerequisites.md) | Pending human checks |
| Visual assets | [visual-assets.md](visual-assets.md) | No approved asset |

## Machine validation

Run:

```bash
python -m pip install -r requirements-validation.txt
python scripts/validate-plugin-submission.py
```

The validator checks exact JSON shapes and canonical English values, HTTPS
URLs, required policy boundaries, pending human prerequisites, local-path and
secret leakage, Plugin version/capability boundaries, the English Plugin
README, and the existing Plugin validator. It intentionally does not attempt
to prove arbitrary natural-language meaning or establish translation parity.
This change adds no new third-party dependency; use the existing
`requirements-validation.txt` validation environment.

## Human prerequisites

Repository validation cannot select the OpenAI Platform organization, grant
Apps Management Write permission, verify the publisher identity, approve a
logo, choose availability, build or upload a final submission artifact, create
an external portal draft, make policy attestations, or decide to submit.

See [human-prerequisites.md](human-prerequisites.md) for the exact pending list.

## Phase C boundary

Phase C must collect fresh desktop evidence for the neutral marketplace
identity and `0.1.0-dev.3`: marketplace registration, discovery, installation,
explicit invocation, and Git working-tree non-mutation. The earlier desktop
record cannot satisfy these checks.

## Related documents

- [Plugin README](../../plugins/agentic-change-audit/README.md)
- [Support](../../SUPPORT.md)
- [Privacy](../../PRIVACY.md)
- [License](../../LICENSE)
