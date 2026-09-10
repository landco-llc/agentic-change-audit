# Codex Plugin submission preparation package

## Purpose

This directory contains repository-side preparation materials for the
skills-only Agentic Change Audit Codex Plugin. It does not change the Plugin
runtime, perform an external submission, or satisfy a protected human
prerequisite.

## Current state

- Plugin version: `0.1.0-dev.3` (development).
- Marketplace identity: neutral `Agentic Change Audit marketplace`.
- Current reconciled source before ACA-W012 mutation:
  `26af2687d0bac87089abd975b571ace5398a1a0b`.
- Phase C desktop verification is complete and accepted. ACA-W010 verified that
  exact fixed candidate and package SHA-256
  `af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57`.
- Earlier desktop evidence is historical, superseded, and non-transferable. This
  refers to evidence for the previous marketplace identity/version.
- ACA-W010 evidence is also candidate-bound; it is not automatically transferable
  to a later repository/package identity.
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
Base SHA:   26af2687d0bac87089abd975b571ace5398a1a0b
```

Evidence for one fixed identity does not transfer to another commit. ACA-W012
changes repository documentation/validation state, so its merged candidate must
receive a new fixed identity before any later final-candidate evaluation.

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

The post-W010 validator boundary requires the repository to state that Phase C
desktop verification is complete and accepted while keeping release,
submission, availability, logo, developer/business verification, portal, and
attestation gates fail-closed.

## Human prerequisites

Repository validation cannot select the OpenAI Platform organization, grant
Apps Management Write permission, verify the publisher identity, approve a
logo, choose availability, build or upload a final submission artifact, create
an external portal draft, make policy attestations, or decide to submit.

See [human-prerequisites.md](human-prerequisites.md) for the exact pending list.

## Desktop evidence boundary

ACA-W010 collected fresh desktop evidence for the neutral marketplace identity
and `0.1.0-dev.3` at fixed main
`26af2687d0bac87089abd975b571ace5398a1a0b`: marketplace registration,
discovery, installation, explicit invocation, and Git working-tree
non-mutation. The result was `PHASE_C_DESKTOP_VERIFICATION = PASS` and was Human
accepted for that binding.

That result is immutable historical evidence for its exact candidate. It does
not authorize release/submission and must not be reused as final-candidate
evidence after a repository/package identity change.

## Related documents

- [Plugin README](../../plugins/agentic-change-audit/README.md)
- [Support](../../SUPPORT.md)
- [Privacy](../../PRIVACY.md)
- [License](../../LICENSE)
