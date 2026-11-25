# Codex Plugin submission preparation package

## Purpose

This directory contains repository-side preparation materials for the
skills-only Agentic Change Audit Codex Plugin. It does not change the Plugin
runtime, perform an external submission, or satisfy a protected human
prerequisite.

## Current state

- Plugin version: `0.1.0-rc.1` (provisional pre-release).
- Current user-facing Plugin/listing display name:
  `ACA - Agentic Change Audit`.
- Technical Plugin and marketplace identifier: `agentic-change-audit`.
- ACA-W013 fixed base before this display-name reconciliation:
  `5b96b64a7c7bb0d97c4a15ddab055c0c87018a8f`.
- Phase C desktop verification is complete and accepted. ACA-W010 verified its
  exact historical fixed candidate and package SHA-256
  `af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57`.
- The earlier marketplace wording `Agentic Change Audit marketplace` belongs to
  that historical ACA-W010 binding and is not the current display name.
- ACA-W010 evidence is candidate-bound; it is not automatically transferable to
  the ACA-W013 display-name candidate or the current pre-release.
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
content, not independent machine-semantic acceptance lanes. Translation parity
is not a machine validation gate.

## Source identity

```text
Repository: landco-llc/agentic-change-audit
W013 base:  5b96b64a7c7bb0d97c4a15ddab055c0c87018a8f
```

Evidence for one fixed identity does not transfer to another commit. ACA-W013
changes user-facing display metadata and associated repository validation state,
so its final candidate requires a new fixed identity and final-candidate
verification before release/submission evidence can be claimed.

## Package field map

| Field | File | Notes |
|---|---|---|
| Submission type, listing, identity | [listing.json](listing.json) | Exact repository contract |
| Portable Plugin manifest | [portable/plugin.json](portable/plugin.json) | Skills-only Plugin ZIP root manifest |
| Starter prompts | [starter-prompts.json](starter-prompts.json) | Exactly five |
| Test cases | [test-cases.json](test-cases.json) | Five positive and three negative |
| Availability | [availability.json](availability.json) | Recommendation only |
| Release notes | [release-notes.md](release-notes.md) | Provisional pre-release |
| Human prerequisites | [human-prerequisites.md](human-prerequisites.md) | Pending human checks |
| Visual assets | [visual-assets.md](visual-assets.md) | No approved asset |

## Portable package

The Skills-only Plugin ZIP has one root, `agentic-change-audit/`. It contains
`plugin.json`, the Plugin's root `NOTICE`, and the exact bundled Skill under
`skills/agentic-change-audit/`. The ZIP's manifest copies package identity
and three starter prompts from the local Codex manifest. The listing supplies
the long description and public URLs.

ACA-W021 verified the public [website](https://github.com/landco-llc/agentic-change-audit),
[support](https://github.com/landco-llc/agentic-change-audit/issues) and
[privacy](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md)
surfaces. The [license](https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE)
stays in the listing record as the terms pointer. Availability remains a
pending Human decision with Japan, Taiwan and the United States as the
proposed initial regions.

ACA-W022 prepares and validates packaging source. ACA-W023 independently
builds and verifies the [local package outputs](../../release/README.md#skills-only-plugin-zip)
from merged, post-merge-validated source. An external manifest and checksums
record package identity. OpenAI validation and upload are separate actions.

## Machine validation

Run:

```bash
python -m pip install -r requirements-validation.txt
python scripts/validate-plugin-submission.py
```

The validator checks exact JSON shapes, portable manifest source linkage,
canonical English values, HTTPS
URLs, required policy boundaries, pending human prerequisites, local-path and
secret leakage, Plugin version/capability boundaries, the English Plugin
README, and the existing Plugin validator. It intentionally does not attempt
to prove arbitrary natural-language meaning or establish translation parity.
This change adds no new third-party dependency; use the existing
`requirements-validation.txt` validation environment.

The post-W010/W013 adapter boundary preserves documented candidate-bound
historical verification while binding the current user-facing display name.

## Human prerequisites

Repository validation cannot select the OpenAI Platform organization, grant
Apps Management Write permission, verify the publisher identity, approve a
logo, choose availability, build or upload a final submission artifact, create
an external portal draft, make policy attestations, or decide to submit.

See [human-prerequisites.md](human-prerequisites.md) for the exact pending list.

## Desktop evidence boundary

ACA-W010 collected fresh desktop evidence for the pre-W013 neutral marketplace
identity and `0.1.0-dev.3` at fixed main
`26af2687d0bac87089abd975b571ace5398a1a0b`: marketplace registration,
discovery, installation, explicit invocation, and Git working-tree
non-mutation. The result was `PHASE_C_DESKTOP_VERIFICATION = PASS` and was Human
accepted for that binding.

That result is immutable historical evidence for its exact candidate. It does
not authorize release/submission and must not be reused as final-candidate
evidence after the ACA-W013 display-name change.

## Related documents

- [Plugin README](../../plugins/agentic-change-audit/README.md)
- [Support](../../SUPPORT.md)
- [Privacy](../../PRIVACY.md)
- [License](../../LICENSE)
