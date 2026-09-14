# ACA-W016 protected release/submission prerequisite inventory

## Objective

Inventory the protected release and Codex Plugin submission prerequisites after
ACA-W015, reconcile the public-safe current control snapshot, and stop at one
recommended Human/external gate without performing that gate or any protected
external effect.

## Fixed implementation identity and scope

- Work item: `ACA-W016`.
- Repository: `landco-llc/agentic-change-audit`.
- Fixed base/main: `efd4f002df77e99edfdfd00449e3f7bf322ed2a3`.
- Fixed base tree: `09ddbaf82cf4029b8cc2c9fda361eec24f54d57f`.
- Human authorization: Issue #12 comment `5658504685`, based on proposal
  comment `5656947812` and tracked by Issue #32.
- Prior candidates `58106c35bb6fea6ecb4fac8b3268d4dcb583486e` and
  `24b8572d34290d9f971f5f4f172186ab034b5708` are non-canonical,
  irrecoverable historical attempts. This implementation makes no byte-identity
  claim about either attempt.

The writable scope was fixed before mutation to exactly:

- `docs/ai-dev-ops/orchestration/current-control-state.md`;
- `docs/ai-dev-ops/orchestration/history/ACA-W016.md`.

No prior append-only history is changed. No Plugin, runtime, marketplace,
submission-package, distribution, or version behavior is changed.

## Fresh-read evidence

### Completed predecessor

- ACA-W015 pull request #30 accepted candidate
  `0d3cd2b0f0fd7962149e1972cb86eb8d4b808436`, tree
  `09ddbaf82cf4029b8cc2c9fda361eec24f54d57f`, after an independent
  `PASS / VALID` result with zero blocking findings and exact-head Validate #93
  / Package #90 success.
- It merged as `main@efd4f002df77e99edfdfd00449e3f7bf322ed2a3`
  with the same tree. Exact-main Validate #94 / run `34788442789` and Package
  #91 / run `34788442783` succeeded.
- Package #91 produced development preview
  `agentic-change-audit-0.0.0-dev.efd4f002df77`, SHA-256
  `4c9cd5adfe06bdf802d8bd5e9ba931dfb549dac86a09c69ee71fb46608a05d33`.
  It is exact-main reproducibility evidence only, not a final ZIP, release
  artifact, submission artifact, or publication authority.

### Repository preparation and remaining boundaries

- The Plugin manifest and marketplace metadata consistently identify display
  name `ACA - Agentic Change Audit`, technical slug `agentic-change-audit`,
  developer `L&Co.LLC`, capability `Read`, and development version
  `0.1.0-dev.3`.
- The submission package contains listing metadata, five starter prompts, eight
  test cases, development release notes, an availability recommendation,
  privacy/support references, and validators. The listing remains
  `draft-materials-only` and `not-submitted`.
- Every row in `submission/codex-plugin/human-prerequisites.md` remains
  `PENDING HUMAN CHECK`; repository evidence cannot convert those rows into
  completed external facts.
- No approved logo exists. Availability is only a recommendation. Developer
  identity is pending verification, and no portal draft or policy attestation
  is established by repository evidence.
- The deterministic distribution workflow defines a three-file version set,
  clean fixed-source provenance, repeat-build identity, checksums, independent
  verification, and the boundary between the outer Actions transport ZIP and
  the inner runtime ZIP. Ordinary CI development previews do not satisfy the
  final-version, final-artifact, tag, or GitHub Release gates.
- The release checklist requires an explicit version and fixed source, clean
  successful validation, verified deterministic artifacts, independent audit,
  Human release approval, an audited tag, a draft release, uploaded-asset
  verification, and explicit publication approval.

## Prerequisite inventory

The classifications below are the only classifications authorized by Issue
#32. `REPOSITORY_EVIDENCE_COMPLETE` means only that the cited repository-side
preparation exists; it never proves or authorizes a protected external effect.

| Prerequisite | Classification | Evidence and unsatisfied condition |
| --- | --- | --- |
| Logo / approved asset status | `DECISION_REQUIRED` | `visual-assets.md` and `listing.json` state that no approved asset exists. An authorized Human must select and approve an asset; no asset may be improvised or uploaded here. |
| Availability / public-directory decision | `DECISION_REQUIRED` | `availability.json` contains a recommendation only and remains `PENDING HUMAN DECISION`; the maintainer must decide final availability. |
| Developer/business identity verification | `HUMAN_OR_EXTERNAL_VERIFICATION_REQUIRED` | `listing.json` and the Human-prerequisite table record `L&Co.LLC` verification as pending; only the relevant Human/OpenAI process can establish its state. |
| Apps Management / OpenAI portal state | `HUMAN_OR_EXTERNAL_VERIFICATION_REQUIRED` | The owning organization, Apps Management permission, portal requirements, and draft state cannot be observed or proven from this repository. |
| Stable/final version decision | `DECISION_REQUIRED` | The Plugin remains `0.1.0-dev.3`; release guidance expects the first public release to remain a pre-release, but an authorized Human must choose the final SemVer and pre-release/stable status. |
| Tag / GitHub Release prerequisites | `BLOCKED_BY_PREREQUISITE` | Version, fixed audited source, final verified artifacts, release approval, and tag/release decisions are incomplete. No tag or GitHub Release exists by virtue of this work. |
| Final ZIP identity, provenance, digest, and upload boundary | `BLOCKED_BY_PREREQUISITE` | Deterministic tooling and documented provenance/checksum rules are `REPOSITORY_EVIDENCE_COMPLETE`, but the development preview is not the final ZIP. A chosen version, fixed re-audited source, independently verified final artifact set, and Human upload remain required. |
| Policy / attestation prerequisites | `HUMAN_OR_EXTERNAL_VERIFICATION_REQUIRED` | Repository privacy, support, license, and listing materials exist, but public URL review and legal policy attestations remain pending Human checks. |
| Submission readiness | `BLOCKED_BY_PREREQUISITE` | Repository-side draft materials and validators are `REPOSITORY_EVIDENCE_COMPLETE`; approved logo, availability, identity/portal observations, final submission artifact, URL review, attestations, portal draft, and final submit decision are not complete. |
| Public listing / directory publication | `BLOCKED_BY_PREREQUISITE` | Listing status is `not-submitted`; submission, external review/approval, and a Human publication decision must precede any public listing. |
| Public release / deployment | `BLOCKED_BY_PREREQUISITE` | Final version/artifacts, independent verification, Human approval, tag, draft release, uploaded-asset verification, and publish decision remain incomplete. Repository evidence neither proves nor authorizes release or deployment. |

No required inventory item is `NOT_APPLICABLE`. Repository preparation evidence
does not collapse a composite protected prerequisite into a completed external
state.

## Exactly one recommended next Human/external gate

`OPENAI_PORTAL_READ_ONLY_PREREQUISITE_VERIFICATION`

An authorized Human should perform one non-mutating, read-only observation of
the relevant OpenAI organization and Apps Management/submission portal and
return a public-safe packet that records:

1. whether the intended owning organization is selectable;
2. whether the acting account has the required Apps Management permission;
3. the displayed developer/business verification state;
4. whether a draft already exists, without creating or changing one;
5. the currently displayed required logo, availability, URL, artifact, policy,
   and attestation fields, without choosing, uploading, or attesting; and
6. any prerequisite the portal reports before a draft or submission can
   proceed.

The packet must omit credentials, account identifiers, personal data, private
links, and other non-public details. A failed or unavailable observation is
recorded as unavailable, not inferred as satisfied. This gate is recommended
because repository evidence cannot establish portal state, and observing it
can order later separately authorized decisions without executing them.

## Disposition and protected boundary

State in this candidate: `IMPLEMENTED / AWAITING INDEPENDENT AUDIT`.

This implementation does not self-audit or establish Ready, merge, release,
submission, publication, or deployment authority. It does not choose or upload
a logo; decide availability or version; perform developer/business verification;
change an organization, permission, credential, portal, or draft; create a tag
or GitHub Release; build, publish, or upload a final ZIP; attest; submit; list;
publish; release; or deploy.

The candidate requires exact-head checks and a separate independent fixed-head
audit. A correction would change the head and require a fresh independent
re-audit. The recommended gate above must not be executed under ACA-W016
implementation authority.
