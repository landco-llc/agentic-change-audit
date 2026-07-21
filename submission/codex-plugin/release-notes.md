# Release notes — Codex Plugin submission package

Plugin: `agentic-change-audit`
Version: `0.1.0-dev.2` (development package)
Package status: draft materials only

## Summary

This is the first submission package for the skills-only Agentic Change Audit Codex Plugin. It prepares the repository-side materials that the OpenAI submission form asks for. It changes nothing about the Plugin runtime.

## What this package contains

- The first skills-only Plugin submission package: listing details, starter prompts, positive and negative test cases, an availability recommendation, and these notes.
- The bundled canonical Agentic Change Audit Skill, unchanged: the Plugin ships the same evidence-first, agent-neutral audit workflow as the repository-root Skill sources.
- English, Japanese, and Traditional Chinese guidance for installation and use.
- Public support and privacy policies for the Plugin.

## Runtime boundary

- Declared capability: `Read` only.
- No MCP server.
- No ChatGPT app and no connector.
- No lifecycle hooks.
- No authentication flow.
- No telemetry and no analytics.

## Verified for the development foundation

- CLI marketplace registration: verified. `codex plugin marketplace add .` registers the repository's local marketplace source `landco-llc-open-source`.
- ChatGPT desktop visibility: verified. The Plugin appears under the **L&Co.LLC Open Source** marketplace and installs from it.
- Explicit invocation: verified. `$agentic-change-audit` selects the bundled Skill and runs the audit workflow.
- Unchanged Git state: verified. The audit run left the working tree unchanged.

This evidence comes from the desktop gate recorded in Issue #8.

## Status

- The Plugin version is `0.1.0-dev.2`. It is not a stable version and not a public release.
- This package has not been released, and it has not been submitted to OpenAI.
- No approval has been granted, and no listing has been published in any public directory.
- The existing Skill release `v0.1.0-rc.1` and its assets are not modified by this package.
- Business identity verification, logo approval, availability selection, and the final submit decision all remain pending human decisions.

## Not included

- No release candidate tag.
- No published ZIP bundle.
- No public Plugins Directory availability claim.
