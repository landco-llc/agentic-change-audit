# Agentic Change Audit — Codex Plugin (development preview)

[日本語](README.ja.md) | [繁體中文](README.zh-Hant.md)

## Status

**Development preview.** This is the first installable Codex Plugin foundation for Agentic Change Audit. It is a **skills-only Plugin**: it bundles the existing Agentic Change Audit Skill so it can be installed through a repository-scoped local marketplace instead of only a direct Skill folder.

This development Plugin is not submitted to, listed in, or available from OpenAI's public Plugins Directory. Public submission materials, publisher identity verification, and directory listing are a later phase and are out of scope for this foundation.

## What this Plugin is

- A **skills-only** package: `.codex-plugin/plugin.json` plus a bundled Skill under `skills/agentic-change-audit/`.
- The bundled Skill is byte-identical to the canonical repository-root Skill sources at the commit this Plugin was built from.
- The audit workflow itself is unchanged: evidence-first, agent-neutral, and read-only by default.

## What this Plugin is not

- **No MCP server.** No `.mcp.json` and no `mcpServers` entry.
- **No ChatGPT app or connector.** No `.app.json` and no `apps` entry.
- **No lifecycle hooks.** No `hooks/` directory and no `hooks` entry.
- **No authentication flow.** The manifest declares no login or token exchange.
- **No telemetry.** Nothing in this Plugin reports usage, analytics, or events anywhere.
- **No write-capable tool.** The manifest declares exactly one capability: `Read`.

Direct Skill installation — copying or symlinking the repository into `~/.claude/skills/` or `~/.agents/skills/` — remains fully supported and is not replaced by this Plugin. See the [installation guides](https://github.com/landco-llc/agentic-change-audit/tree/main/guides) for that path.

## Local marketplace testing

Clone the repository and register it as a local Plugin marketplace source:

```bash
git clone \
  https://github.com/landco-llc/agentic-change-audit.git

cd agentic-change-audit

codex plugin marketplace add .
codex plugin marketplace list
```

The `codex plugin marketplace add .` command registers the current repository's `.agents/plugins/marketplace.json` as a local marketplace source named `landco-llc-open-source`. It does not install the Plugin by itself and does not contact any external service.

## Install and test in ChatGPT desktop

1. Restart the ChatGPT desktop app after adding or updating the marketplace, so it picks up the new source.
2. Open **Plugins**.
3. Select the **L&Co.LLC Open Source** marketplace.
4. Install **Agentic Change Audit**.
5. Start a new task and invoke the Plugin to test it.

A full ChatGPT desktop UI installation walkthrough is a **PENDING HUMAN CHECK** for anyone reproducing these steps; it is not something this repository can execute or attest to automatically.

## Registering from GitHub after this branch is merged

Once this Plugin foundation is merged into `main`, the marketplace can also be added directly from GitHub without a local clone:

```bash
codex plugin marketplace add \
  landco-llc/agentic-change-audit \
  --ref main
```

Until then, use the local `codex plugin marketplace add .` command above against a checkout of this branch.

## Invocation examples

```text
$agentic-change-audit

Audit the current repository change.
Fix the audit to the current base and target HEAD.
Do not modify files.
Return Markdown.
```

```text
Use Agentic Change Audit to audit this AI-built application as a release candidate.

Record missing evidence, findings, human checks, one Verdict,
and the next permitted action.
Do not modify, deploy, or release anything.
```

## Read-only audit boundary

The bundled Skill audits; it does not act. The Plugin declares only the `Read` capability, and the audit workflow itself instructs the agent not to modify files, commit, push, approve, merge, deploy, or release during the audit phase. Any state-changing action a user requests afterward is a separate, explicitly authorized step outside the audit.

## No organizational authority

Installing this Plugin does not grant approval, merge, deployment, or release authority to the agent or to the Plugin. A passing Verdict is a decision aid, not a substitute for the humans who hold that authority.

## No security, legal, or production guarantee

The audit result produced through this Plugin is not a security certification, legal opinion, regulatory certification, or production-safety guarantee. Human review remains required for applicable visual, business, privacy, payment, legal, destructive-operation, deployment, and final-approval decisions.

## Version

This Plugin uses a development version identifier, `0.1.0-dev.1`. It is not a public release or a stable Plugin version, and it does not correspond to a tagged Skill release.

## Related documents

- [Repository README](https://github.com/landco-llc/agentic-change-audit/blob/main/README.md)
- [Installation guides](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)
- [Canonical Skill (`SKILL.md`)](https://github.com/landco-llc/agentic-change-audit/blob/main/SKILL.md)
- [License](https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE)
