# Installation and Usage

- Language: English
- Last reviewed: 2026-07-13
- Supported initial agents: Claude Code and Codex
- Package name: `agentic-change-audit`

## Important concept

This GitHub repository is the skill package directory itself.

A valid installed package looks like:

```text
agentic-change-audit/
├── SKILL.md
├── standard/
├── templates/
└── ...
```

Cloning the repository into an arbitrary folder does not automatically make the skill discoverable. The whole folder must be copied or linked into a discovery location supported by the agent.

The commands below use a shared source checkout so Claude Code and Codex can use the same files.

Examples use a POSIX shell on macOS or Linux. Equivalent directory-copy or directory-link operations can be used on other platforms.

## 1. Clone the source package

```bash
mkdir -p "$HOME/.local/share"

git clone \
  https://github.com/landco-llc/agentic-change-audit.git \
  "$HOME/.local/share/agentic-change-audit"
```

Confirm:

```bash
test -f "$HOME/.local/share/agentic-change-audit/SKILL.md"
```

Review the repository before enabling any third-party skill.

## Claude Code

Claude Code supports personal skills at:

```text
~/.claude/skills/<skill-name>/SKILL.md
```

and project skills at:

```text
<project>/.claude/skills/<skill-name>/SKILL.md
```

Claude Code can invoke a skill automatically when its description matches the request, or explicitly with `/skill-name`.

### 2A. Personal installation with a symlink

Use this to make the skill available across projects.

```bash
mkdir -p "$HOME/.claude/skills"

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  "$HOME/.claude/skills/agentic-change-audit"
```

Claude Code follows symlinked skill directories in current versions. On an older version that does not detect the link, use the copy method below or update Claude Code.

### 2B. Personal installation by copying

Use this instead of a symlink when required by the environment.

```bash
mkdir -p "$HOME/.claude/skills"

cp -R \
  "$HOME/.local/share/agentic-change-audit" \
  "$HOME/.claude/skills/agentic-change-audit"
```

A copied installation does not update automatically when the source checkout changes.

### 2C. Project-scoped installation

From the target project:

```bash
mkdir -p .claude/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .claude/skills/agentic-change-audit
```

Do not commit an absolute machine-specific symlink into a shared repository. For a team-shared installation, copy the package into the project or define a repository-relative distribution method appropriate to the team.

### 3. Verify in Claude Code

Start Claude Code inside a Git project:

```bash
claude
```

Invoke explicitly:

```text
/agentic-change-audit
```

Or ask a matching request:

```text
Audit the current pull request with Agentic Change Audit.
Fix the result to the live target HEAD and do not modify the PR.
```

Claude Code watches existing skill directories for changes. If a newly created top-level skill directory is not detected, restart Claude Code.

## Codex

Codex supports user skills at:

```text
$HOME/.agents/skills/<skill-name>/SKILL.md
```

and repository skills under:

```text
<repository>/.agents/skills/<skill-name>/SKILL.md
```

Codex scans `.agents/skills` from the current working directory up to the repository root. It supports symlinked skill folders.

### 4A. User installation with a symlink

```bash
mkdir -p "$HOME/.agents/skills"

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  "$HOME/.agents/skills/agentic-change-audit"
```

### 4B. User installation by copying

```bash
mkdir -p "$HOME/.agents/skills"

cp -R \
  "$HOME/.local/share/agentic-change-audit" \
  "$HOME/.agents/skills/agentic-change-audit"
```

### 4C. Repository-scoped installation

From the target repository:

```bash
mkdir -p .agents/skills

ln -s \
  "$HOME/.local/share/agentic-change-audit" \
  .agents/skills/agentic-change-audit
```

Do not commit an absolute machine-specific symlink into a shared repository.

### 5. Verify in Codex

Start Codex in a Git repository.

Use `/skills` to inspect available skills, or type `$` and select `agentic-change-audit`.

Example:

```text
$agentic-change-audit

Audit PR #123 against issue #98.
Fix the audit to the live base SHA and target HEAD.
Do not modify the repository or PR.
Return Markdown.
```

Codex can also select the skill implicitly when the request matches its description. If a newly installed skill does not appear, restart Codex.

## 6. Recommended first test

Use a low-risk documentation-only change.

```text
Use Agentic Change Audit in DOCS_ONLY mode.

Audit the current branch against main.
Record repository, base SHA, target HEAD, and changed files.
Run relevant read-only documentation and git checks.
Do not modify files.
Return the Markdown audit template.
```

Confirm that the result:

- records a fixed base and target HEAD;
- lists the reviewed files;
- records commands and checks not executed;
- states evidence limitations;
- uses exactly one allowed verdict;
- states the next permitted action;
- includes an invalidation notice.

## 7. Updating

Update the shared source checkout:

```bash
cd "$HOME/.local/share/agentic-change-audit"

git pull --ff-only origin main
```

Symlink installations use the updated files immediately or after the agent reloads them.

For copied installations, remove or replace the copied folder using your normal controlled update process. Do not mix old and new files.

## 8. Removing the skill

For a symlinked personal installation:

### Claude Code

```bash
rm "$HOME/.claude/skills/agentic-change-audit"
```

### Codex

```bash
rm "$HOME/.agents/skills/agentic-change-audit"
```

These commands remove the link, not the shared source checkout.

Review the target path before running removal commands.

## 9. Troubleshooting

### Skill is not listed

Check:

```bash
test -f "$HOME/.claude/skills/agentic-change-audit/SKILL.md"
test -f "$HOME/.agents/skills/agentic-change-audit/SKILL.md"
```

Then:

- confirm the directory is named `agentic-change-audit`;
- confirm `SKILL.md` is at the package root;
- restart the agent;
- confirm the correct user account and home directory;
- confirm the link target exists;
- confirm the agent has permission to read the package.

### Skill does not trigger automatically

Invoke it explicitly first.

For Claude Code:

```text
/agentic-change-audit
```

For Codex:

```text
Type `$` and select `agentic-change-audit`.
```

Automatic selection depends on the task matching the skill description.

### The repository was cloned but the skill is unavailable

A clone outside a supported discovery location is only a source checkout. Link or copy the complete folder into the appropriate skill location.

## 10. Security and authority

Installing a skill loads operational instructions into an AI agent.

Before use:

- review `SKILL.md` and referenced files;
- confirm repository ownership and the exact version or commit;
- keep agent tool permissions appropriately restricted;
- do not assume a third-party audit result is correct merely because it matches the JSON Schema.

This skill does not grant organizational authority to approve, merge, deploy, or release.

## 11. Support

The project is provided as is.

Free installation support, troubleshooting, response-time guarantees, and maintenance commitments are not provided.

Professional implementation support and organizational integration may be available separately as paid services under a separate agreement.

## Official references

- [Agent Skills specification](https://agentskills.io/specification)
- [Claude Code skills documentation](https://code.claude.com/docs/en/skills)
- [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills)
