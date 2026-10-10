# Codex Plugin submission preparation package

## Purpose

This directory contains repository-side preparation materials for the
skills-only Agentic Change Audit Codex Plugin. It does not change the Plugin
runtime, perform an external submission, or satisfy a protected human
prerequisite.

## Current state

- Plugin version: `0.1.0-dev.3` (development).
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
  the ACA-W013 display-name candidate.
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

## Preparation-only two-package design (NONACTIVE)

`ACA-C02-AUDIT-HOLD-PREP-001` records a documentation-only candidate. This
section is a proposed packaging design, not an implemented archive contract,
formal audit, accepted source, release, or submission artifact. No Family B
builder, verifier, or submission ZIP is produced by this candidate.

### Distinct output families

| Family | Proposed or existing output | Boundary |
|---|---|---|
| A — existing runtime Skill | `agentic-change-audit-<version>.zip`, external `.manifest.json`, and `.SHA256SUMS` | One `agentic-change-audit/` root; the existing 24-file runtime allowlist plus generated `PACKAGE-MANIFEST.json` |
| B — proposed Skills-only Plugin | `agentic-change-audit-plugin-<plugin-version>.zip` | One `agentic-change-audit/` Plugin root containing exactly the 28 existing source files specified below |

Family A retains its existing commands and deterministic contract in the
[release guide](../../release/README.md). Its external manifest and checksums
remain separate from the runtime ZIP. The GitHub Actions outer transport ZIP
is neither Family A nor Family B.

### Family B source boundary

Proposed source binding:
`d1bfda4e703c5bc1639c55e4b7dd17c9c064f264`, tree
`4291ab6eb0636233eeb352638f62ac044e0ca91c`. Packaging would remove only the
source prefix `plugins/` and retain this single root:

```text
agentic-change-audit/
  .codex-plugin/plugin.json
  NOTICE
  README.md
  skills/agentic-change-audit/  (exact 25-file inventory below)
```

The bundled Skill inventory, relative to `skills/agentic-change-audit/`, is:

```text
LICENSE
NOTICE
README.ja.md
README.md
SKILL.md
docs/legal-attribution.md
docs/product-definition.ja.md
docs/product-definition.md
guides/en/installation.md
guides/ja/installation.md
guides/zh-Hant/installation.md
standard/audit-invalidation.ja.md
standard/audit-invalidation.md
standard/change-audit-standard.ja.md
standard/change-audit-standard.md
standard/evidence-requirements.ja.md
standard/evidence-requirements.md
standard/human-check-boundary.ja.md
standard/human-check-boundary.md
standard/output-schema.json
standard/verdict-criteria.ja.md
standard/verdict-criteria.md
templates/audit-result.json
templates/audit-result.md
templates/focused-reaudit-result.md
```

The proposed boundary permits only these 28 existing regular files and their
necessary parent directories. No other root, sibling, generated package
manifest, extra script, test, submission-preparation file, private file, or
cache belongs in Family B. It retains a Skills-only Plugin: no MCP, apps,
hooks, authentication, telemetry, or network client. The manifest's
`skills: "./skills/"` resolves from the Plugin root, and the Skill directory
remains named `agentic-change-audit` with its existing `SKILL.md`.

### Public specification and unresolved metadata

Official public documentation checked on **2026-10-10**:

- [Package your plugin](https://developers.openai.com/plugins/build/plugins)
  continues to support `.codex-plugin/plugin.json` compatibility manifests.
  This design retains the existing layout; a portable-manifest migration is
  outside this candidate.
- [Build skills](https://developers.openai.com/plugins/build/skills) documents
  bundled Skill folders and `SKILL.md`.
- [Upload and submit your plugin](https://developers.openai.com/plugins/deploy/submission)
  documents ZIP upload and separate review/publication stages. Its listing
  limit is 30 characters each for display name and short description.
- [Plugin submission errors](https://developers.openai.com/plugins/deploy/submission-errors)
  documents archive/path checks and a compressed ZIP limit of 100 MB. It also
  distinguishes upload checks from final directory submission checks.

P01's dated metadata measurement is 26 characters for the current display name
and 61 for `interface.shortDescription`: the name fits the 30-character
submission limit; the short description exceeds it. No replacement wording is
selected here. The public package-summary table gives 4000 characters while
the package error reference gives 1024; the conservative future design ceiling
is 1024 pending fresh reconciliation. These public facts do not establish
compatibility with an authenticated or post-upload portal state, which remains
`UNKNOWN`; they are not a submission-readiness attestation.

Plugin version remains `0.1.0-dev.3`; bundled Skill metadata remains `0.1.0`.
A future Plugin `0.1.0-rc.1` is provisional intent only and requires its own
coherent version/metadata transition. Both rc support and short-description
validation require work in currently excluded paths:
`scripts/validate-codex-plugin-core.py`, `scripts/validate-codex-plugin.py`,
`tests/test_codex_plugin.py`, and `tests/codex_plugin_core_tests.py`. Existing
validation must not be weakened to hide those dependencies.

### Deferred implementation and evidence

A future archive builder/verifier and path parser are High Risk security work.
Their implementation is deferred pending the required security-specialist
assurance and formal Critical Audit admission, which are currently unavailable.
Future tests must cover exact root/allowlist and manifest/content hashes,
missing/extra/duplicate entries, malformed or corrupted ZIPs/manifests,
absolute/backslash/traversal paths, symlinks, privacy checks, exact committed
source provenance, version consistency, and two-build byte/hash equivalence.
These are design requirements, not executed Family B tests.

Any rehearsal using existing runtime tooling must bind a clean fixed source
and keep temporary outputs in private scratch. It supplies preparation evidence
only, not release/submission assets, formal audit, or acceptance. Historical
ACA-W010 identities and evidence above retain their original exact binding.
Developer identity, logo, availability, legal/policy choices, and every Human
prerequisite remain pending; this design makes no portal choice or attestation.
G1B remains `HOLD`; W021–W024 remain `NOT ACTIVATED`.

## Related documents

- [Plugin README](../../plugins/agentic-change-audit/README.md)
- [Support](../../SUPPORT.md)
- [Privacy](../../PRIVACY.md)
- [License](../../LICENSE)
