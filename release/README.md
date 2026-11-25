# Distribution and Release Preparation

[日本語](README.ja.md)

This directory defines how Agentic Change Audit produces a portable Skill archive before a GitHub Release is created.

The packaging workflow is deliberately separated from release publication:

- pull requests and `main` builds create temporary workflow artifacts;
- no workflow creates a tag, GitHub Release, approval, or merge;
- a maintainer publishes a release only after the fixed source commit and generated artifact hashes are independently reviewed.

## Preparation-only two-family design (NONACTIVE)

`ACA-C02-AUDIT-HOLD-PREP-001` adds a documentation-only packaging proposal.
Family A is the existing runtime Skill ZIP described below: one
`agentic-change-audit/` root, the exact 24 files in
[distribution-files.json](distribution-files.json), generated
`PACKAGE-MANIFEST.json`, and the separate external manifest and `SHA256SUMS`.
All existing output names, build/verify commands, and runtime boundaries remain
unchanged.

Family B is a proposed separate Skills-only Plugin ZIP named
`agentic-change-audit-plugin-<plugin-version>.zip`, rooted at
`agentic-change-audit/`. Its exact 28-existing-file source boundary is defined
in the [submission packaging design](../submission/codex-plugin/README.md#preparation-only-two-package-design-nonactive):
`.codex-plugin/plugin.json`, `NOTICE`, `README.md`, and the 25 currently bundled
Skill files under `skills/agentic-change-audit/`. It adds no second root,
sibling, scripts, tests, submission files, private data, or caches. The Actions
outer transport ZIP is neither output family.

No Family B builder, verifier, or submission ZIP is produced by this candidate.
Archive/path-parser code is deferred High Risk work requiring security-specialist
assurance and formal Critical Audit admission; neither is supplied by these
docs. Plugin `0.1.0-dev.3` and Skill metadata `0.1.0` remain current;
`0.1.0-rc.1` is provisional future Plugin intent requiring a separately coherent
transition. The existing commands below remain runtime examples, not a Plugin
version transition.

An existing-tooling runtime rehearsal may use a clean exact-source binding and
private scratch only. Its hashes and repeated-build results are preparation
evidence, not release/submission artifacts, formal audit, or source acceptance.
This proposal changes no pending Human identity, logo, availability, legal, or
submission prerequisite. G1B remains `HOLD`; W021–W024 remain `NOT ACTIVATED`.

## Release outputs

For version `<version>`, the build produces:

```text
agentic-change-audit-<version>.zip
agentic-change-audit-<version>.manifest.json
agentic-change-audit-<version>.SHA256SUMS
```

The ZIP contains one unversioned root directory:

```text
agentic-change-audit/
```

The root must not include the version. Agent Skills requires the Skill `name` to match its parent directory, so a root such as `agentic-change-audit-0.1.0` would be incorrect.

## Runtime-only package

[distribution-files.json](distribution-files.json) is an exact allowlist.

The public archive includes the Skill, license, READMEs, installation guides, canonical standards, Schema, and result templates.

It intentionally excludes repository-maintenance content such as:

- `.github/`;
- `release/`;
- `scripts/`;
- `tests/`;
- `requirements-validation.txt`;
- generated caches and build output.

The source repository remains the place for validation tooling and contribution history.

## Deterministic build

The builder:

- requires ASCII SemVer without a `v` prefix;
- requires an exact 40-character source commit SHA;
- verifies that `--source-ref` equals the repository `HEAD`;
- verifies that the allowlist, distribution config, runtime files, and canonical builder are tracked and byte-identical to that commit;
- rejects package-affecting dirty or untracked files;
- records `source_identity: verified_git_clean` in release-capable manifests;
- rejects missing files, symlinks, hidden paths, duplicates, and path traversal;
- sorts archive entries;
- uses fixed ZIP timestamps and file modes;
- uses `ZIP_STORED` to avoid compression-runtime variance;
- writes the same manifest inside and outside the ZIP;
- generates external SHA-256 checksums.

The same source bytes, version, source SHA, and allowlist must produce byte-identical outputs.

`--test-only-unverified-source` exists only for synthetic unit-test fixtures. It marks the manifest as `unverified_test_fixture`, and the verifier rejects that identity by default. Never use it for a release or release candidate.

The three output files are published as one version set. If publication of any member fails, the builder removes the whole version set rather than leaving mixed old and new files.

## Local commands

```bash
python scripts/build-distribution.py \
  --version 0.1.0-rc.1 \
  --source-ref <full-40-character-commit-sha> \
  --output-dir dist/release
```

Verify all three outputs:

```bash
python scripts/verify-distribution.py \
  dist/release/agentic-change-audit-0.1.0-rc.1.zip \
  --manifest dist/release/agentic-change-audit-0.1.0-rc.1.manifest.json \
  --checksums dist/release/agentic-change-audit-0.1.0-rc.1.SHA256SUMS \
  --expected-version 0.1.0-rc.1 \
  --expected-source-ref <full-40-character-commit-sha>
```

## Workflow artifact

The `Package` workflow runs on pull requests, pushes to `main`, and manual dispatch.

For pull requests and ordinary pushes, it uses a commit-scoped development version:

```text
0.0.0-dev.<12-character-source-sha>
```

A manual run may supply an explicit SemVer version for release-candidate preparation.

Workflow artifacts are temporary review evidence. They are not GitHub Releases and are not a guarantee that the package should be published.

When downloaded through the GitHub web interface or artifact API, the workflow artifact is an **outer transport ZIP** containing the three release-candidate files. Extract that wrapper first. The outer transport ZIP is not the runtime Skill archive and must never be attached to a GitHub Release. Only the inner runtime ZIP, external manifest, and `SHA256SUMS` file are candidate release assets.

See [Release Checklist](RELEASE_CHECKLIST.md) before publishing.
