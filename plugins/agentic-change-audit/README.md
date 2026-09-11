# Agentic Change Audit — Codex Plugin (development preview)

## Status

**Development preview.** This is the first installable Codex Plugin foundation for Agentic Change Audit. It is a **skills-only Plugin**: it bundles the existing Agentic Change Audit Skill so it can be installed through a repository-scoped local marketplace instead of only a direct Skill folder.

This development preview uses the neutral **Agentic Change Audit marketplace**
identity and Plugin version `0.1.0-dev.3`.

## Development status

- **Phase C desktop verification is complete and accepted.** ACA-W010 verified
  marketplace discovery, installation, explicit invocation, and Git working-tree
  non-mutation for the fixed pre-reconciliation candidate at
  `26af2687d0bac87089abd975b571ace5398a1a0b`, Plugin `0.1.0-dev.3`, and package
  SHA-256 `af508f8284482ef0578385783f184972db786d7504f920c7597728552df50d57`.
- Earlier desktop evidence for the previous marketplace identity/version remains
  historical, superseded, and non-transferable. ACA-W010 evidence is likewise
  fixed to its recorded candidate and does not automatically transfer to a later
  repository/package identity.
- This Plugin has not been submitted to or approved for OpenAI's public Plugins
  Directory, is not listed there, and is not available from it.
- Publisher identity verification, logo approval, and other protected human
  decisions remain pending. **All human prerequisites remain pending.**
- [Support](https://github.com/landco-llc/agentic-change-audit/blob/main/SUPPORT.md)
  and [Privacy](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md)
  document the repository boundaries.

The repository-side preparation material is in the [submission package](https://github.com/landco-llc/agentic-change-audit/tree/main/submission/codex-plugin). It is preparation material, not a submission.

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

The `codex plugin marketplace add .` command registers the current repository's `.agents/plugins/marketplace.json` as a local marketplace source named `agentic-change-audit`. It does not install the Plugin by itself and does not contact any external service.

## Install and test in ChatGPT desktop

1. Restart the ChatGPT desktop app after adding or updating the marketplace, so it picks up the new source.
2. Open **Plugins**.
3. Select the **Agentic Change Audit marketplace**.
4. Install **Agentic Change Audit**.
5. Start a new task and invoke the Plugin to test it.

ACA-W010 completed this verification for its fixed candidate. These steps remain
reproduction guidance only; if the repository/package identity changes, the old
result is not evidence for the new final candidate.

## Registering from GitHub

Phase A is merged. The marketplace can be added directly from GitHub without a
local clone:

```bash
codex plugin marketplace add \
  landco-llc/agentic-change-audit \
  --ref main
```

ACA-W010 completed Phase C for its fixed source identity. A later changed `main`
requires a new fixed-candidate evaluation rather than reuse of the old evidence.

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

This Plugin uses a development version identifier, `0.1.0-dev.3`. It is not a public release or a stable Plugin version, and it does not correspond to a tagged Skill release.

## Language contract

English is the sole canonical language for machine semantics and exact tokens.
The runtime may write narrative prose in the user's conversation language, but
it must never translate or alias Verdicts, severities, schema keys or values,
human-check statuses, audit statuses, or other exact machine tokens.

## Related documents

- [Repository README](https://github.com/landco-llc/agentic-change-audit/blob/main/README.md)
- [Installation guides](https://github.com/landco-llc/agentic-change-audit/tree/main/guides)
- [Canonical Skill (`SKILL.md`)](https://github.com/landco-llc/agentic-change-audit/blob/main/SKILL.md)
- [Support](https://github.com/landco-llc/agentic-change-audit/blob/main/SUPPORT.md)
- [Privacy](https://github.com/landco-llc/agentic-change-audit/blob/main/PRIVACY.md)
- [Submission package](https://github.com/landco-llc/agentic-change-audit/tree/main/submission/codex-plugin)
- [License](https://github.com/landco-llc/agentic-change-audit/blob/main/LICENSE)
