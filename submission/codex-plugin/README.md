# Codex Plugin submission package

## Purpose

This directory holds the repository-side materials for a future OpenAI submission of the skills-only Agentic Change Audit Codex Plugin.

It is **preparation material only**. It is not a submission, and it does not change the Plugin.

## Status

- **No submission has occurred.** Nothing in this directory has been sent to OpenAI, and no draft exists in the OpenAI submission portal.
- **No public availability is claimed.** The Plugin is not listed in, available from, or approved for OpenAI's public Plugins Directory.
- The Plugin version remains `0.1.0-dev.1`, a development identifier.
- The Plugin runtime is untouched by this package: the manifest, the marketplace entry, and the bundled Skill are all unchanged.
- Every remaining step to an actual submission is a human gate. See [human-prerequisites.md](human-prerequisites.md).

## Source commit

These materials were prepared against:

```text
Repository: landco-llc/agentic-change-audit
Base SHA:   af94afcf72ea4e2778d2f59152d764c6ea1ea151
```

This is a fixed base, not a submission candidate. The commit that is actually submitted must be fixed first and then re-audited against that fixed identity — an audit of this preparation branch does not transfer to a different commit.

## How these files map to the OpenAI portal

| Portal field | File | Notes |
|---|---|---|
| Submission type | [listing.json](listing.json) → `submissionType` | `skills-only` |
| Plugin name, descriptions, category | [listing.json](listing.json) | Matches the manifest `interface` block |
| Publisher | [listing.json](listing.json) → `publisher` | `L&Co.LLC` |
| Website URL | [listing.json](listing.json) → `websiteUrl` | Repository landing page |
| Support URL | [listing.json](listing.json) → `supportUrl` | Backed by [SUPPORT.md](../../SUPPORT.md) |
| Privacy URL | [listing.json](listing.json) → `privacyUrl` | Backed by [PRIVACY.md](../../PRIVACY.md) |
| Terms URL | [listing.json](listing.json) → `termsUrl` | Apache-2.0 [LICENSE](../../LICENSE) |
| Developer identity | [listing.json](listing.json) → `developerIdentity` | Human gate; status is pending |
| Logo | [visual-assets.md](visual-assets.md) | Human gate; no approved asset exists |
| Starter prompts | [starter-prompts.json](starter-prompts.json) | Exactly five |
| Test cases | [test-cases.json](test-cases.json) | Exactly five positive and three negative |
| Availability | [availability.json](availability.json) | Recommendation only; human decides |
| Release notes | [release-notes.md](release-notes.md) | Draft materials |
| Skill bundle / ZIP | — | Not built here; human gate |

## What is machine-validated

`scripts/validate-plugin-submission.py` runs offline, with the standard library only, and enforces:

- every required file exists;
- `listing.json` has the exact key contract and the exact fixed values;
- every public URL uses HTTPS;
- developer identity verification status is still `PENDING HUMAN CHECK`;
- logo status is still pending;
- public directory status is still `not-submitted`;
- exactly five starter prompts, each with all required fields;
- exactly eight test cases: five positive and three negative, with unique IDs and all required fields;
- no empty string values anywhere in the package;
- no private local filesystem paths;
- no email address other than an `example.invalid` placeholder in a test fixture;
- no secret-like token;
- `PRIVACY.md` states the no-collection, no-telemetry, and no-MCP boundaries;
- `SUPPORT.md` states best-effort support with no guaranteed response;
- availability status is still pending;
- `release-notes.md` claims no stable, submitted, approved, or published status;
- the Plugin manifest still declares version `0.1.0-dev.1` and the `Read` capability only, with no MCP, app, or hooks field;
- `scripts/validate-codex-plugin.py` still passes.

Run it from the repository root:

```bash
python scripts/validate-plugin-submission.py
```

`tests/test_plugin_submission.py` covers the validator itself, including that each guardrail actually fails when it should.

## What is a human gate

A validator can only check that this package does not overclaim. It cannot perform any of the following, and none of them are done:

- selecting the OpenAI Platform organization and obtaining Apps Management Write permission;
- L&Co.LLC business identity verification;
- reviewing the public website, support, privacy, and terms URLs once they resolve on `main`;
- deciding final availability;
- approving a logo;
- building and uploading the final Skill ZIP;
- creating the submission portal draft;
- making the policy attestations;
- deciding to submit.

All of these are tracked in [human-prerequisites.md](human-prerequisites.md), each as `PENDING HUMAN CHECK`.

## Evidence and tracking

**Issue #8 — desktop gate: PASS.** The development foundation was verified in the ChatGPT desktop app: CLI marketplace registration, Plugin visibility under the **L&Co.LLC Open Source** marketplace, explicit `$agentic-change-audit` invocation, and an unchanged Git working tree after the audit run. That gate covers the development foundation only. It is not evidence of an OpenAI submission, a directory listing, or an approval.

**Issue #9 — tracking.** The Codex Plugin release and public submission package are tracked in Issue #9, which remains open.

## Related documents

- [Codex Plugin README](../../plugins/agentic-change-audit/README.md)
- [Support](../../SUPPORT.md)
- [Privacy](../../PRIVACY.md)
- [Repository README](../../README.md)
