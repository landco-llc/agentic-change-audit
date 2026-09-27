# ACA-W018 portal evidence reconciliation history

## Objective and fixed implementation identity

Reconcile the durable ACA-W017 read-only portal observation with the ACA-W016
repository-side prerequisite inventory and prepare bounded evidence for the
next campaign Work. This record does not perform or claim a portal mutation,
verification, draft creation, submission, listing, publication, release, or
deployment.

- Work item: `ACA-W018`, under `ACA-RS-CAMPAIGN-01` / Issue #36.
- Repository: `landco-llc/agentic-change-audit`.
- Fixed base/main: `57a1d52b82d130d25309657f76e126540df5a068`.
- Fixed base tree: `5050853b14882b8ac253327837b47e51ff2dd532`.
- Implementation branch: `codex/aca-w018-portal-reconciliation`.
- Authorized writable paths: this file and
  `docs/ai-dev-ops/orchestration/current-control-state.md` only.

The base is the post-merge ACA-GOV-001 main identity. ACA-GOV-001 PR #38
merged the exact delegated head `a2c6f3d8a40550f31d9b3996eb4364bc82f398f2`
onto base `c59bd59a7e7f37d26fa58702fc8489cfd446a98d`. Its independent AR01
re-audit was `PASS / VALID`, blocking 0, F01 resolved, and F02 resolved with no
regression. Five exact-main hosted checks succeeded. Those facts are recorded
as predecessor evidence; they do not grant W018 lifecycle authority.

## W017 durable evidence

- Durable source: Issue #35 comment `5855872049`.
- Observation time: `2026-09-27 12:24 UTC`.
- Method: authenticated Brave Browser session, read-only OpenAI Platform UI
  observation.
- Observation source packet SHA-256:
  `1f8fb85b04e71a127db99b84cdc71145dad599288baebbc60b18bc58c30e5530`.
- Repository identity at observation: main
  `57a1d52b82d130d25309657f76e126540df5a068`, tree
  `5050853b14882b8ac253327837b47e51ff2dd532`.
- `PORTAL MUTATION: NONE`.

The packet observed that L&Co. LLC was selectable and selected; the acting
account displayed Owner and the Owner preset permissions view displayed Apps
Management Write; organization settings displayed Start for Business
verification; and the selected Default project's Plugins page displayed an
empty list with a create-plugin prompt and no draft visible in that view.

These are time-, account-, organization-, and project-bound UI observations.
They do not authenticate effective permission across all contexts, establish
business verification, rule out drafts in another project or organization, or
establish submission readiness. Required logo, availability, URL, artifact,
policy, and attestation fields were not displayed and remain `UNVERIFIED`.
No verification flow or draft creation was initiated.

## Reconciled ACA-W016 prerequisite inventory

The W016 five-value classification vocabulary is retained. Composite rows keep
their blocked state whenever any protected subcondition remains unsatisfied.

| Prerequisite | Classification | Observed evidence | Repository-side gap | Human/external-only gap | Next owner |
| --- | --- | --- | --- | --- | --- |
| Logo / approved asset status | `DECISION_REQUIRED` | `visual-assets.md` and `listing.json` state no approved asset exists; W017 did not display a logo field. | No repository asset or approved asset record exists. | Human must select and approve a compliant asset; only an authorized external process may accept it. | Authorized Human |
| Availability / public-directory decision | `DECISION_REQUIRED` | `availability.json` remains `PENDING HUMAN DECISION`; W017 did not expose a field. | Recommendation exists, but no final choice is recorded. | Maintainer must decide final availability in the external portal. | Authorized Human |
| Developer/business identity verification | `HUMAN_OR_EXTERNAL_VERIFICATION_REQUIRED` | W017 organization settings displayed Start; completion was not displayed. | Repository records pending status only. | OpenAI verification must establish the external state. | Human / OpenAI process |
| Apps Management / OpenAI portal state | `HUMAN_OR_EXTERNAL_VERIFICATION_REQUIRED` | W017 displayed selected L&Co. LLC, Owner, and Owner preset Apps Management Write in the observed context. | Repository cannot prove effective permission across contexts or portal state outside the observed view. | External account, organization, project, and portal state require Human/external confirmation. | Human / OpenAI process |
| Stable/final version decision | `DECISION_REQUIRED` | Submission materials remain development version `0.1.0-dev.3`. | No final SemVer or release status is chosen. | Maintainer must choose the final version and pre-release/stable status. | Authorized Human |
| Tag / GitHub Release prerequisites | `BLOCKED_BY_PREREQUISITE` | No tag or GitHub Release is established by W017 or this Work. | Final version, fixed audited source, verified artifacts, and release materials remain incomplete. | Release approval, tag, and GitHub Release decisions remain external Human actions. | Repository Child then Human |
| Final ZIP identity, provenance, digest, and upload boundary | `BLOCKED_BY_PREREQUISITE` | W016 tooling documents deterministic rules; W017 observed no draft fields and created no artifact. | No final version-bound ZIP, digest, or upload record exists. | Human must choose, review, and upload the final artifact through the authorized process. | Repository Child then Human |
| Policy / attestation prerequisites | `HUMAN_OR_EXTERNAL_VERIFICATION_REQUIRED` | Repository policy, privacy, support, and listing materials exist; W017 did not display attestation fields. | No repository evidence can attest on behalf of a Human. | Public URL review and legal attestations remain Human checks. | Authorized Human |
| Submission readiness | `BLOCKED_BY_PREREQUISITE` | W017 found no draft in the observed Default project view and no required form fields were displayed. | Draft materials exist, but no final artifact, approved asset, final choices, or external readiness record exists. | Portal draft, URL review, attestations, and final submit decision remain pending. | Human / OpenAI process |
| Public listing / directory publication | `BLOCKED_BY_PREREQUISITE` | `listing.json` remains `not-submitted`; W017 performed no publication. | No repository action establishes a listing. | Submission, external review, approval, and publication decision remain pending. | Authorized Human / OpenAI process |
| Public release / deployment | `BLOCKED_BY_PREREQUISITE` | W017 states `PORTAL MUTATION: NONE`; no release or deployment occurred. | Final artifact, tag, release, and publication evidence remain absent. | Human release approval and external publication/deployment remain pending. | Authorized Human / external process |

No W016 row is `REPOSITORY_EVIDENCE_COMPLETE` for a protected external
completion claim merely because the W017 UI displayed a related value. No row
is `NOT_APPLICABLE`. Every row in
`submission/codex-plugin/human-prerequisites.md` remains `PENDING HUMAN CHECK`.

## W019 preparation boundary

W018 organizes existing public-safe evidence for a later W019 packet. The
repository-side owner may prepare references, fixed identities, and explicit
evidence gaps under a separate W019 instruction. W018 does not choose a logo,
availability, version, URL, artifact, policy attestation, submission,
publication, release, or deployment. The campaign's final boundary remains
the named `HUMAN_GATE / RELEASE_SUBMISSION_DECISION_BUNDLE`.

No routine Human callback is requested by this repository reconciliation. The
bounded repository work may continue only under a separately authored W019
instruction and its own exact-head lifecycle evidence.

## Validation and candidate disposition

Validation for this implementation candidate:

- `git diff --check`: to be run before commit.
- Exact changed-path equality: exactly the two authorized documentation paths;
  no other path may change.
- Public-safe-content review: no credentials, account identifiers,
  organization IDs, personal data, private links, or raw external payloads.
- Hosted CI: `CI EVIDENCE NOT PRESENT` until exact-head hosted checks are read
  from the candidate PR.

State in this candidate: `IMPLEMENTED / AWAITING INDEPENDENT AUDIT`.

This record grants no audit result, Ready status, merge authority, release
authority, submission authority, publication authority, deployment authority,
portal mutation, credential/permission/organization mutation, Astra
activation, or risk acceptance. A later correction changes the target head and
requires a fresh independent fixed-head re-audit.
