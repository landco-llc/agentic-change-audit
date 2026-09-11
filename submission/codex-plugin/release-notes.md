# Release notes — Codex Plugin submission package

Plugin: `agentic-change-audit`
Version: `0.1.0-dev.3` (development package)
Identity: `Agentic Change Audit marketplace`

## Summary

This records repository-side preparation material for the skills-only Agentic
Change Audit Codex Plugin. It changes nothing about the Plugin runtime and does
not itself create a release or submission.

## What this package contains

- The first skills-only Plugin submission package: listing details, starter prompts, positive and negative test cases, an availability recommendation, and these notes.
- The bundled canonical Agentic Change Audit Skill, unchanged: the Plugin ships the same evidence-first, agent-neutral audit workflow as the repository-root Skill sources.
- English is the sole canonical language for machine semantics and exact
  tokens. Runtime narrative follows the user's conversation language.
- Public support and privacy policies for the Plugin.

## Runtime boundary

- Declared capability: `Read` only.
- No MCP server.
- No ChatGPT app and no connector.
- No lifecycle hooks.
- No authentication flow.
- No telemetry and no analytics.

## Desktop evidence boundary

- ACA-W010 Phase C desktop verification is complete and accepted for fixed main
  `26af2687d0bac87089abd975b571ace5398a1a0b`, Plugin `0.1.0-dev.3`, and package
  SHA-256 `af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57`.
- The Human-operated verification covered marketplace discovery, installation,
  explicit invocation, absence of unexpected MCP/connector/auth/write requests,
  and Git working-tree non-mutation.
- Earlier desktop evidence for a previous marketplace identity/version remains
  historical, superseded, and non-transferable.
- ACA-W010 evidence is also fixed to its exact candidate. A later repository or
  package identity requires a new fixed-candidate evaluation before it can be
  used as final submission evidence.

## Status

- The Plugin version is `0.1.0-dev.3`, a development identifier.
- This package is repository-side preparation material only.
- Every human-prerequisite row remains `PENDING HUMAN CHECK`.
- Availability remains a pending Human decision.
- No approved logo exists.
- No OpenAI submission portal draft or policy attestation is established here.

## Not included

- No final-candidate post-reconciliation desktop evaluation is claimed by these
  notes.
- No external submission, public listing, tag, GitHub Release, final ZIP upload,
  or directory publication is performed.
