# Agentic Change Audit — Product Definition

## Status

- Version: Draft 0.1
- Language: English
- Canonical: Yes
- Last updated: 2026-07-12

## One-line Description

Agentic Change Audit is an evidence-first, agent-neutral standard and reusable skill for auditing software changes before merge or release.

## Purpose

The project helps AI agents and human reviewers determine whether a software change is ready to be accepted, merged, deployed, or released.

It focuses on the validity of the entire change, not only on code quality.

## Target Users

- Individual developers
- OSS maintainers
- Startups
- Software teams
- AI-assisted developers
- Non-engineers using coding agents
- Organizations reviewing AI-generated or human-written changes

## In Scope

- Pull requests
- Local working-tree changes
- Release candidates
- Documentation changes
- Application code changes
- Infrastructure changes
- Configuration changes
- Database and migration changes
- Human-written changes
- AI-generated changes
- Mixed human and AI changes

## Out of Scope

- Automatic merge approval
- Automatic production deployment
- Legal or regulatory certification
- Security guarantees
- Replacement of human review
- Paid support as part of the OSS release

## Core Principles

1. Evidence first
2. Agent neutral
3. Fixed target identity
4. Explicit scope control
5. Audit invalidation after target changes
6. Clear stop conditions
7. Human responsibility for final decisions

## Primary Question

The project does not only ask:

> Is this code good?

It asks:

> Is this change safe and sufficiently verified to be accepted, merged, deployed, or released?

## Initial Supported Languages

- English
- Japanese

English is the canonical specification. Japanese is an official translation.

## Initial Supported Agents

- Claude Code
- Codex

The core standard must remain agent-neutral.

## Support Policy

The OSS project is provided as-is.

Free installation support, troubleshooting, implementation assistance, and response-time guarantees are not provided.

Issues and pull requests may be reviewed at the maintainers' discretion.

Professional implementation support, custom audit policy design, workflow integration, and organizational adoption may be provided as paid services.

## License

Apache License 2.0
