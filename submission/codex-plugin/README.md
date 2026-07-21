# Codex Plugin submission package

## Purpose

This directory holds the repository-side materials for a future OpenAI submission of the skills-only Agentic Change Audit Codex Plugin.

It is **preparation material only**. It is not a submission, and it does not change the Plugin.

## Status

- **No submission has occurred.** Nothing in this directory has been sent to OpenAI. No portal action is performed or evidenced by this repository lane. Portal state remains a human verification gate.
- **Audit history: four independent audit rounds have returned `CHANGES REQUESTED`.** The first remediation fixed the originally reported false-PASS mutations; the second addressed multilingual and punctuation claim evasions and Support-channel classification; the third added Markdown-aware scanning; this fourth remediation closes CommonMark edge cases in both the claim scan and reference resolution. Final repository-side acceptance still requires another focused independent re-audit of the new fixed HEAD.
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

`scripts/validate-plugin-submission.py` enforces:

- every required file exists, including the three Plugin READMEs;
- `listing.json` has the exact key contract and the exact fixed values;
- every public URL uses HTTPS;
- developer identity verification status is still `PENDING HUMAN CHECK`;
- logo status is still pending;
- public directory status is still `not-submitted`;
- exactly five starter prompts, each with all required fields;
- exactly eight test cases: five positive and three negative, with unique IDs and all required fields;
- no empty string values anywhere in the package;
- no private local filesystem paths, in the package or the Plugin READMEs;
- no email address other than an `example.invalid` placeholder in a test fixture;
- no secret-like token;
- `PRIVACY.md` states every canonical boundary, so removing any single one fails even while the others remain — and every single boundary has its own independent removal regression test through the full validator;
- `SUPPORT.md` states every canonical boundary. Noncanonical destinations are resolved from raw URLs, inline Markdown links, full, collapsed, and shortcut reference links, and images — including a linked image, whose outer destination is the support destination. Reference definitions accept bare and angle-bracket destinations with an optional title, labels are normalized case-insensitively with whitespace collapsed and backslash escapes decoded (so an escaped bracket cannot hide a keyword), and a duplicate definition never overrides the first, matching CommonMark's first-definition-wins rule. A destination is rejected only when visible prose, a link label, or image alt text on the same line asserts an official support, contact, or help-desk channel — in English, Japanese, Traditional Chinese, or mixed-language phrasing — or when an immediately preceding colon-terminated assertion line introduces a URL-only destination. The carried context expires at any other prose, heading, list item, URL, or reference definition. Documentation and reference wording (glossary, terminology, 説明, 術語, and similar) is explanatory, never a channel assertion; an unused reference definition alone is never a finding; and a URL path alone is never treated as proof of a channel;
- each Plugin README still states its development-preview and pending-submission boundaries;
- availability status is still pending;
- no positive product-status claim survives in the release notes, this README, or the three Plugin READMEs. The scan runs on Markdown visible text, normalized in a fixed order: fenced and top-level indented code blocks are excluded as examples; HTML comments are removed, so a comment cannot split a word or hide a claim; named, decimal, and hexadecimal HTML character references are decoded; CommonMark backslash escapes for ASCII punctuation are resolved; link and image labels stay visible while destinations and reference definitions are dropped; HTML emphasis tags and emphasis, strong, and strikethrough delimiters are processed; block markers are removed; and soft line breaks are joined inside each paragraph — with a space, or without one between two CJK characters, matching how each renders — while paragraph boundaries are never fused. Struck-through text is excluded because it reads as deleted, so `~~not~~ published` asserts publication. Negation is then bound to the specific claim it negates: explicitly negated status spans are masked first, and any status claim remaining anywhere afterwards fails, so neither formatting nor a negation in another span can license a claim across an em dash, an en dash, a comma, or a contrastive connector. The scan covers English, Japanese, and Traditional Chinese status claims about submission, approval, publication, release, stability, and public Directory availability, while coordinated negations and benign wording (prepared policy URLs, policies described as coming from this repository, neutral link labels over any destination, genuine indented code examples) continue to pass. **This is a conservative submission-policy normalizer, not a complete CommonMark renderer**, and the language coverage is the enumerated claim set, not every possible phrasing;
- every human prerequisite row parses to exactly three cells whose status equals `PENDING HUMAN CHECK` exactly, so `COMPLETE — previously PENDING HUMAN CHECK` fails;
- the Plugin manifest still declares version `0.1.0-dev.1` and the `Read` capability only, with no MCP, app, or hooks field;
- `scripts/validate-codex-plugin.py` still passes.

The new submission validator itself uses only the Python standard library and makes no network requests. End-to-end validation also invokes the existing Codex Plugin and Skill validators, so install the repository's existing validation dependencies from `requirements-validation.txt` first. This PR adds no new third-party dependency; `requirements-validation.txt` is unchanged.

Run it from the repository root:

```bash
python -m pip install -r requirements-validation.txt
python scripts/validate-plugin-submission.py
```

`tests/test_plugin_submission.py` covers the validator itself with 144 tests, including that each guardrail actually fails when it should; the repository's full suite is 208 tests. Every status-claim and Support-channel acceptance test runs the real validator as a subprocess against a fresh temporary repository copy — no test re-derives the validator's internal patterns or parser functions. All 18 canonical Privacy boundaries keep their independent removal regressions, and every test snapshots every tracked repository file plus the complete `git status` output before and after, proving that mutations happen only in the temporary copies.

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
