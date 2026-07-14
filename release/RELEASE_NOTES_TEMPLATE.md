# Agentic Change Audit v<version>

[日本語](RELEASE_NOTES_TEMPLATE.ja.md)

## Status

**Pre-release** | **Stable**

## Summary

Describe the purpose of this release and the fixed source commit.

## Included

- Agent-neutral audit Skill
- English canonical standards
- Official Japanese translations
- JSON Schema and result templates
- Local installation guides

## Source identity

```text
Repository: landco-llc/agentic-change-audit
Tag: v<version>
Source commit: <full-source-sha>
```

## Assets

```text
agentic-change-audit-<version>.zip
agentic-change-audit-<version>.manifest.json
agentic-change-audit-<version>.SHA256SUMS
```

The ZIP extracts to the unversioned Skill directory:

```text
agentic-change-audit/
```

## Verification

Verify the SHA-256 values before installation and run `scripts/verify-distribution.py` from the source repository when practical.

## Compatibility

State the tested Claude Code and Codex installation behavior and any minimum versions.

## Known limitations

- Automated validation does not replace independent audit judgment.
- Audit output is not security certification, legal advice, regulatory certification, or a production-safety guarantee.
- Codex Plugin packaging is not included in this release unless explicitly stated.
- List release-specific limitations.

## Support

The project is provided as is. Free installation support, troubleshooting, maintenance, and response-time guarantees are not included. Paid professional implementation or integration may be offered separately.
