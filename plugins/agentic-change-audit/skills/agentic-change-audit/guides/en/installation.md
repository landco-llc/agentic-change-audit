# Installation and Usage Guide

[日本語](../ja/installation.md) | [繁體中文](../zh-Hant/installation.md)

- Language: English
- Last reviewed: 2026-07-15
- Public version covered: `v0.1.0-rc.1`
- Direct-install targets: Claude Code and OpenAI Codex
- Package name: `agentic-change-audit`
- Status: Pre-release

## 1. What this package is

Agentic Change Audit is an open-source Agent Skill for auditing software changes before a human merge, release, or deployment decision.

It can audit:

- pull requests and fixed commits;
- local working-tree changes;
- release candidates;
- AI-generated, human-written, and mixed changes;
- applications, websites, automation, configuration, infrastructure, migrations, dependencies, and documentation.

The skill is evidence-first. It records what was inspected, what checks were executed, what was not checked, remaining findings, human checks, and one final verdict.

The skill supports decisions. It does not replace human authority and is not a security, legal, regulatory, or production-safety certification.

## 2. Current compatibility

This release includes direct installation instructions for:

- Claude Code
- OpenAI Codex

The core is agent-neutral, but this release does not yet provide:

- a Claude Code Plugin package;
- a one-click ChatGPT Web installation;
- a Custom GPT;
- dedicated Gemini CLI or GitHub Copilot packages.

OpenAI direct Skill folders remain fully supported for local authoring and discovery. In addition, a **development skills-only Codex Plugin** is now available from this repository's local marketplace. It bundles the same canonical Skill and audit workflow, adds no MCP server, ChatGPT app, connector, or lifecycle hooks, and does not grant approval, merge, deploy, or release authority. Public OpenAI Plugins Directory submission is not complete; this Plugin is installable only through the repository-scoped local marketplace, or a Git-backed marketplace source once merged to `main`, and installation/testing occurs through the ChatGPT desktop app.

Register the local marketplace:

```bash
codex plugin marketplace add .
```

See the [Codex Plugin README](https://github.com/landco-llc/agentic-change-audit/tree/main/plugins/agentic-change-audit) for local marketplace testing, ChatGPT desktop installation, and invocation examples.

## 3. Required package layout

A valid installation has `SKILL.md` at the package root:

```text
agentic-change-audit/
├── SKILL.md
├── README.md
├── README.ja.md
├── docs/
├── guides/
├── standard/
└── templates/
```

Do not add the version to the root directory name.

```text
Correct:
agentic-change-audit/

Incorrect:
agentic-change-audit-0.1.0-rc.1/
```

Avoid a nested package such as:

```text
agentic-change-audit/
└── agentic-change-audit/
    └── SKILL.md
```

## 4. Public source and release

Repository:

```text
https://github.com/landco-llc/agentic-change-audit
```

Release:

```text
https://github.com/landco-llc/agentic-change-audit/releases/tag/v0.1.0-rc.1
```

Published assets:

```text
agentic-change-audit-0.1.0-rc.1.zip
agentic-change-audit-0.1.0-rc.1.manifest.json
agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

Published SHA-256 values:

```text
0e9fe576b2db43e29817df0a15d5e1eea2c07eeb8a0843c0b88117d81ac270ac  agentic-change-audit-0.1.0-rc.1.zip
df12de142bc2e6207d3325902043a81563e6429bd783405cde8749c62a6edffe  agentic-change-audit-0.1.0-rc.1.manifest.json
57327a19cecfc01ce5da924b0d02735b046dbddcffc2673fc70da50ea0e2c6bb  agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

The GitHub-generated `Source code (zip)` and `Source code (tar.gz)` downloads are not the runtime Skill archive. Use the three named release assets above.

## 5. Recommended shared-source layout

A convenient local setup is:

```text
Shared package:
~/.local/share/agentic-change-audit/

Codex link:
~/.agents/skills/agentic-change-audit
    -> ~/.local/share/agentic-change-audit/

Claude Code link:
~/.claude/skills/agentic-change-audit
    -> ~/.local/share/agentic-change-audit/
```

This lets both agents read the same package and reduces version drift.

## 6. Install the fixed release with Git

Use this when Git is available and you want the exact tagged source.

First confirm that the destination does not already exist:

```bash
test ! -e "$HOME/.local/share/agentic-change-audit" \
  && test ! -L "$HOME/.local/share/agentic-change-audit"
```

Clone the fixed tag:

```bash
mkdir -p "$HOME/.local/share"

git clone \
  --branch v0.1.0-rc.1 \
  --depth 1 \
  https://github.com/landco-llc/agentic-change-audit.git \
  "$HOME/.local/share/agentic-change-audit"
```

Verify the identity:

```bash
cd "$HOME/.local/share/agentic-change-audit"

git describe --tags --exact-match
git rev-parse HEAD
git status --short
```

Expected:

```text
Tag:
v0.1.0-rc.1

Commit:
f421571f25d090cbd7b5e387e82db86a688cd229

Working tree:
clean
```

Confirm the Skill entrypoint:

```bash
test -f "$HOME/.local/share/agentic-change-audit/SKILL.md" \
  && echo "Agentic Change Audit package: OK"
```

## 7. Install from the release ZIP

Use this when you prefer the audited release archive.

Download the three named assets from the Release page, or use GitHub CLI:

```bash
mkdir -p "$HOME/Downloads/agentic-change-audit-v0.1.0-rc.1"
cd "$HOME/Downloads/agentic-change-audit-v0.1.0-rc.1"

gh release download v0.1.0-rc.1 \
  --repo landco-llc/agentic-change-audit \
  --pattern 'agentic-change-audit-0.1.0-rc.1.zip' \
  --pattern 'agentic-change-audit-0.1.0-rc.1.manifest.json' \
  --pattern 'agentic-change-audit-0.1.0-rc.1.SHA256SUMS'
```

Verify the checksum records.

macOS:

```bash
shasum -a 256 -c agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

Linux:

```bash
sha256sum -c agentic-change-audit-0.1.0-rc.1.SHA256SUMS
```

Both listed files must report `OK`.

Extract and verify:

```bash
unzip agentic-change-audit-0.1.0-rc.1.zip

test -f agentic-change-audit/SKILL.md \
  && echo "Skill package: OK"
```

Move it into the shared location only after confirming that the destination is unused:

```bash
mkdir -p "$HOME/.local/share"

mv agentic-change-audit \
  "$HOME/.local/share/agentic-change-audit"
```

## 8. Install for Codex

### 8.1 User-wide installation

```bash
mkdir -p "$HOME/.agents/skills"

destination="$HOME/.agents/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf 'Destination already exists: %s\n' "$destination" >&2
else
  ln -s \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

Verify:

```bash
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md" \
  && echo "Codex Skill: OK"
```

### 8.2 Repository-scoped installation

From the target repository:

```bash
mkdir -p .agents/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .agents/skills/agentic-change-audit
```

Do not commit an absolute machine-specific symlink into a shared repository. For team distribution, use a repository-relative arrangement or copy the complete package through a controlled process.

### 8.3 Invoke in Codex

Start Codex inside the repository to audit.

Explicit invocation:

```text
$agentic-change-audit

Audit the current project.
Fix the audit to the current commit and effective diff.
Do not modify files, commit, push, merge, deploy, or release.
Return the result in Markdown.
```

You can also:

- run `/skills`;
- type `$` and select `agentic-change-audit`;
- mention the Skill directly in the prompt;
- allow Codex to select it implicitly when the request matches its description.

If a newly installed Skill does not appear, restart Codex.

### 8.4 Temporarily disable in Codex

Add an entry to `~/.codex/config.toml`:

```toml
[[skills.config]]
path = "/absolute/path/to/.agents/skills/agentic-change-audit/SKILL.md"
enabled = false
```

Restart Codex after changing the configuration.

## 9. Install for Claude Code

### 9.1 Check the version

Symlinked Skill directories require Claude Code `v2.1.203` or later.

```bash
claude --version
```

Use the copy method below or update Claude Code when using an older version.

### 9.2 Personal installation with a symlink

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf 'Destination already exists: %s\n' "$destination" >&2
else
  ln -s \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

Verify:

```bash
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md" \
  && echo "Claude Code Skill: OK"
```

### 9.3 Personal installation by copying

Use this when symlinks are unavailable:

```bash
mkdir -p "$HOME/.claude/skills"

destination="$HOME/.claude/skills/agentic-change-audit"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  printf 'Destination already exists: %s\n' "$destination" >&2
else
  cp -R \
    "$HOME/.local/share/agentic-change-audit" \
    "$destination"
fi
```

Do not rerun `cp -R` into an existing destination. It can leave stale files or create a nested package. Replace copied installations as complete versioned sets.

### 9.4 Project-scoped installation

From the target project:

```bash
mkdir -p .claude/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .claude/skills/agentic-change-audit
```

Do not commit an absolute machine-specific symlink into a shared repository.

### 9.5 Invoke in Claude Code

Start Claude Code inside the project:

```bash
cd /path/to/project
claude
```

Invoke explicitly:

```text
/agentic-change-audit

Audit this project as a release candidate.
Fix the audit to the current commit.
Do not modify files, commit, push, deploy, or release.
Return the result in Markdown.
```

Claude Code may also load the Skill automatically when the request matches its description.

Claude Code monitors existing Skill directories for `SKILL.md` changes. If the top-level Skills directory did not exist when the session started, restart Claude Code.

## 10. ChatGPT desktop and ChatGPT Web

OpenAI Skills are available in the ChatGPT desktop app, Codex CLI, and the Codex IDE extension. In the desktop app, use the Skills section in the sidebar to inspect Skills discovered across projects.

This release is not a published ChatGPT Plugin and cannot be installed into ordinary ChatGPT Web with a one-click action.

For a temporary Web-chat use, upload `SKILL.md` and the relevant standard files, then instruct ChatGPT to treat them as the audit authority. That is document-assisted use, not an installed Skill.

Example:

```text
Use the attached Agentic Change Audit SKILL.md and standards as the governing audit instructions.

Audit the current change without modifying files.
Record the fixed target, checks performed, checks not performed, findings, human checks, one verdict, and the next permitted action.
```

## 11. Recommended first test

Start with a low-risk documentation-only change.

Codex:

```text
$agentic-change-audit

Use DOCS_ONLY mode.
Audit the current branch against main.
Record the repository, base SHA, target HEAD, and changed files.
Run only relevant read-only documentation and Git checks.
Do not modify files.
Return the Markdown audit result.
```

Claude Code:

```text
/agentic-change-audit

Use DOCS_ONLY mode.
Audit the current branch against main.
Record the repository, base SHA, target HEAD, and changed files.
Run only relevant read-only documentation and Git checks.
Do not modify files.
Return the Markdown audit result.
```

Confirm that the result:

- fixes the base and target identity;
- lists reviewed files;
- records executed and unexecuted checks;
- states evidence limitations;
- uses exactly one verdict;
- states the next permitted action;
- includes an invalidation notice.

## 12. Common audit modes

```text
FULL
Audit the complete change against its requirements.

FOCUSED_REAUDIT
Verify authorized remediation against a previous fixed audit.

RELEASE
Audit a fixed release candidate.

DOCS_ONLY
Audit documentation-only changes without unrelated application checks.
```

For an app built quickly by AI without independent review, use `RELEASE` mode to establish the current state and identify missing verification.

## 13. Verdicts

Agentic Change Audit returns exactly one:

```text
PASS
Required verification is complete and no blocking issue remains.

PASS WITH COMMENTS
The change may proceed with only non-blocking observations.

CHANGES REQUESTED
Modification is required before acceptance.

BLOCKED
The target is fixed, but required verification cannot be completed.

NOT AUDITABLE
A reliable target or minimum audit contract cannot be established.
```

A passing verdict is not a certification or guarantee. Human review remains required for applicable visual, business, privacy, payment, legal, destructive-operation, deployment, and final-approval decisions.

## 14. Permission boundary

Begin audits with the least authority needed.

Recommended audit prompt boundary:

```text
Work read-only during the audit.

Do not modify files, commit, push, approve, merge, deploy, release, change a database, run a real payment, or notify real users.

Do not reveal secret values. Report only the possible location and type of sensitive information.
```

Any later fix, merge, deployment, or release should be a separate explicitly authorized step after the audit.

## 15. Updating

For a fixed audited version, prefer a new tag or a new release asset set rather than silently tracking `main`.

For a Git-based fixed installation, install and verify the next tag separately before replacing the shared package.

For a copied installation, replace the complete directory. Do not mix old and new files.

If intentionally following the development branch:

```bash
cd "$HOME/.local/share/agentic-change-audit"
git switch main
git pull --ff-only origin main
```

The development branch may differ from the published release candidate.

## 16. Removing the Skill

Remove a Codex symlink:

```bash
rm "$HOME/.agents/skills/agentic-change-audit"
```

Remove a Claude Code symlink:

```bash
rm "$HOME/.claude/skills/agentic-change-audit"
```

These commands remove only the links.

Delete the shared package only after checking the exact path:

```bash
printf '%s\n' "$HOME/.local/share/agentic-change-audit"
```

## 17. Troubleshooting

### Skill is not listed

Check the entrypoints:

```bash
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md"
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md"
```

Then confirm:

- the directory is named `agentic-change-audit`;
- `SKILL.md` is at the package root;
- the package is not nested;
- the symlink target exists;
- the current user can read the files;
- the agent was restarted when required.

Inspect links:

```bash
ls -la "$HOME/.agents/skills/agentic-change-audit"
ls -la "$HOME/.claude/skills/agentic-change-audit"
```

### Automatic invocation does not occur

Invoke explicitly:

```text
Codex:
$agentic-change-audit

Claude Code:
/agentic-change-audit
```

### Destination already exists

Do not overwrite it immediately.

```bash
ls -la "$HOME/.local/share/agentic-change-audit"
ls -la "$HOME/.agents/skills/agentic-change-audit"
ls -la "$HOME/.claude/skills/agentic-change-audit"
```

Determine whether each path is an older copy, a symlink, or another installation before replacing anything.

## 18. Security and support

Installing a Skill loads operational instructions into an AI agent.

Before enabling a third-party Skill:

- review `SKILL.md` and referenced files;
- confirm the repository owner;
- confirm the version, tag, and commit;
- restrict tool permissions;
- do not treat schema-valid output as proof that an audit is correct.

Fixed public identity for this guide:

```text
Version:
v0.1.0-rc.1

Source commit:
f421571f25d090cbd7b5e387e82db86a688cd229

Tag object:
b81907105e477d50bfc35d8b723a6614916fa868
```

The project is provided as is. Free installation support, troubleshooting, maintenance, and response-time guarantees are not provided. Professional implementation and organizational integration may be offered separately under a separate agreement.

## 19. Official references

- [Agentic Change Audit repository](https://github.com/landco-llc/agentic-change-audit)
- [Agentic Change Audit v0.1.0-rc.1](https://github.com/landco-llc/agentic-change-audit/releases/tag/v0.1.0-rc.1)
- [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Claude Code: Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Agent Skills specification](https://agentskills.io/specification)
