# ACA central DG routing reference

ACA consumes accepted/current central DG model, reasoning, risk and audit
selection. This file contains ACA constraints and source/deployment evidence;
it is not an independently maintained generic model table.

## Authority and fixed source

The pilot adoption Work is
`DG-PILOT-ROLL-20261025-landco-llc--agentic-change-audit`. Fresh Read the
central `registry/dg-pilot-model-routing-canonical-reference.md`,
`policies/ai-model-routing-gpt61-cloud-successor-policy.md` (AI-MODEL-006),
`policies/ai-model-routing-and-independent-audit-policy.md`,
`policies/ai-model-routing-gpt61-parent-low-amendment.md` (A06), and
`policies/DG-PILOT-OWNER-CONTINUITY-20261025.md`
with their applicable acceptance/activation records. Baseline acceptance/readback
are DG Issue #1140 comments `5913535415` / `5913575398`; A06 acceptance/readback
are DG Issue #1148 comments `5925131766` / `5925140446`. Historical candidate
headers neither negate these records nor activate unrelated candidate material.

The machine-readable pin, tree and eight canonical role blobs are in
[the source manifest](../../.codex/dg-routing-source.json). Refresh only in an
attributable Work after central-main applicability/currentness checks.
Already-fixed executions retain their bound routes and retry history.

## Generated deployment projection

`.codex/agents/*.toml` are generated project-bound projections of canonical
role bytes plus the preserved ACA instructions in
`.codex/aca-role-instructions/*.txt`. The manifest pins both source Git blobs
and local instruction SHA-256 values. Do not hand-edit generic model fields.
Run `python3 scripts/project-dg-routing.py` for offline drift, TOML, path and
schema checks. To regenerate, obtain trusted central source bytes at the
manifest commit and run `python3 scripts/project-dg-routing.py --source-dir
<CENTRAL_SOURCE_DIRECTORY>`. The generator has no network or authority to
update its own manifest. An intentional local-constraint change needs its own
scope and attributable manifest update.

Project `.codex/config.toml` references these local role layers with paths
relative to that declaring configuration. There are no machine-private paths
or cross-checkout assumptions. Generic fallback defaults were removed; the
Controller must select an adequate explicit accepted route. No GPT-5.6 default
is revived. The Work/result schema route constraints are generated from these
same pinned roles; other schema and transition constraints are preserved.
Historical reproduction may use an explicit fixed historical schema through
the existing validator `--schema` option. Historical bytes and fixtures are
not authority to launch a new Work with old routing.

Source pinning, generation and successful parsing do not prove App loading.
[Official configuration sample](https://learn.chatgpt.com/docs/config-file/config-sample)
and [subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents)
were read on 2026-10-25 JST. Host-enforced settings still control; a role's
`sandbox_mode` declaration is a requested boundary, not proof that a custom
role overrides its Parent sandbox. Audit execution must establish a real
read-only target independently. Change no trust, permission or global setting
to manufacture an effective-route claim.

## ACA safety and lifecycle constraints

The Parent remains control-plane only. Role selection never widens scope,
security, risk, Ready/merge, release, deployment, provider or Human authority.
Keep every ACA job instruction and stronger protection. Candidate, proposed,
shadow, experimental and non-active material is not executable authority.
Non-active Astra material cannot select a route, expand Parent powers,
continue a campaign or establish Fast Track eligibility.

A named complex Parent judgment may temporarily use a stronger route only
under accepted/current DG authority. Record prior and escalated route,
authority, reason, decision boundary, start and de-escalation point; return at
the permitted safe boundary after resolution or Child handoff. Routine
routing and evidence checks do not retain escalation. No stronger model
creates substantive Parent task-plane authority.

Formal audit requires a NEW fresh separate Audit Work/control-plane Audit
Parent which dispatches a dedicated fresh Audit Child against the immutable
repository/PR/full HEAD/tree/base/scope. A Child under the producer Parent is
self-validation. An audit performs no correction, Ready, merge or protected
external effect; changed HEAD requires fresh independent re-audit. Preserve
critical audit assurance and all correction history. `BLOCKED`,
`CHANGES_REQUESTED`, `NOT_AUDITABLE`, unresolved material findings and required
re-audit are not waived by pilot continuity. PR #44 remains its separate
`G1B-NEW-01 HIGH / BLOCKED VALID`, correction count 1 lineage.

The adoption receipt distinguishes `DECLARED`, `SOURCE_REFERENCED`,
`APP_LOADED` and `NATIVE_ROLE_EFFECTIVE`; missing proof is `NOT_VERIFIED` for
that layer. Serving metadata unavailable from the provider is `UNKNOWN`,
while explicit launch mismatch/refusal remains fail-closed. Model changes
reset neither retry identity nor audit/transition prerequisites.
