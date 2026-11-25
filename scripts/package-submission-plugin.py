#!/usr/bin/env python3
"""Build or check ACA's deterministic Skills-only Plugin ZIP from fixed Git source."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import unicodedata
from urllib.parse import urlsplit
import zipfile

import yaml


NAME = "agentic-change-audit"
PLUGIN_VERSION = "0.1.0-rc.1"
SKILL_VERSION = "0.1.0"
REPOSITORY = "https://github.com/landco-llc/agentic-change-audit"
SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN = f"plugins/{NAME}"
MIRROR = f"{PLUGIN}/skills/{NAME}"
SUBMISSION = "submission/codex-plugin"
PORTABLE = f"{SUBMISSION}/portable/plugin.json"
COMPATIBILITY = f"{PLUGIN}/.codex-plugin/plugin.json"
LISTING = f"{SUBMISSION}/listing.json"
AVAILABILITY = f"{SUBMISSION}/availability.json"
TOOL = "scripts/package-submission-plugin.py"
AVAILABILITY_SHA256 = "9a5133d1a6ecdefd78db1f18c2750bed42618e6d180e5c397fc510748f6ace2b"
SKILL_FILES = (
    "LICENSE",
    "NOTICE",
    "README.ja.md",
    "README.md",
    "SKILL.md",
    "docs/legal-attribution.md",
    "docs/product-definition.ja.md",
    "docs/product-definition.md",
    "guides/en/installation.md",
    "guides/ja/installation.md",
    "guides/zh-Hant/installation.md",
    "standard/audit-invalidation.ja.md",
    "standard/audit-invalidation.md",
    "standard/change-audit-standard.ja.md",
    "standard/change-audit-standard.md",
    "standard/evidence-requirements.ja.md",
    "standard/evidence-requirements.md",
    "standard/human-check-boundary.ja.md",
    "standard/human-check-boundary.md",
    "standard/output-schema.json",
    "standard/verdict-criteria.ja.md",
    "standard/verdict-criteria.md",
    "templates/audit-result.json",
    "templates/audit-result.md",
    "templates/focused-reaudit-result.md",
)
SOURCE_MAP = {
    f"{NAME}/plugin.json": PORTABLE,
    f"{NAME}/NOTICE": f"{PLUGIN}/NOTICE",
    **{f"{NAME}/skills/{NAME}/{path}": f"{MIRROR}/{path}" for path in SKILL_FILES},
}
METADATA_FILES = (PORTABLE, COMPATIBILITY, LISTING, AVAILABILITY)
REQUIRED_FILES = frozenset((*METADATA_FILES, TOOL, *SOURCE_MAP.values(), *SKILL_FILES))
PACKAGE_FIELDS = {
    "name": NAME,
    "version": PLUGIN_VERSION,
    "description": (
        "Evidence-first audits for AI-generated and human software changes "
        "before merge, release, or deployment."
    ),
    "author": {"name": "L&Co.LLC", "url": "https://github.com/landco-llc"},
    "homepage": REPOSITORY,
    "repository": REPOSITORY,
    "license": "Apache-2.0",
    "keywords": [
        "ai-agents", "agent-skills", "software-audit", "change-audit",
        "code-review", "release-readiness",
    ],
}
DISPLAY_NAME = "ACA - Agentic Change Audit"
SUBTITLE = "Evidence-first change audits"
PUBLISHER = "L&Co.LLC"
CATEGORY = "Productivity"
PROMPTS = [
    "Audit the current repository change without modifying files. "
    "Fix the result to the current base and target HEAD.",
    "Audit this AI-built application as a release candidate and identify "
    "missing evidence and required human checks.",
    "Re-audit the approved remediation against the previous findings and authorized scope.",
]
LISTING_DESCRIPTION = (
    "Agentic Change Audit reviews a fixed software change, records the checks "
    "and evidence actually available, identifies findings and required human "
    "checks, and returns one structured Verdict before merge, release, or "
    "deployment. It is evidence-first, agent-neutral, and read-only by default."
)

# The fixed package fits a tighter limit than the published 100,000,000-byte
# archive, 512 MiB expanded, and 100 MiB per-entry ceilings. Bound the local
# ZIP read even when its contents cannot be decoded as an archive.
MAX_LOCAL_BYTES = 2 * 1024 * 1024
MAX_ZIP_BYTES = 100_000_000
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_ENTRY_BYTES = 100 * 1024 * 1024
MAX_ENTRIES = 5_000
MAX_SEGMENTS = 20
FULL_SHA = re.compile(r"[0-9a-f]{40}")
ZIP_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
DIR_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
STEM = f"{NAME}-plugin-{PLUGIN_VERSION}"
ZIP_NAME = f"{STEM}.zip"
MANIFEST_NAME = f"{STEM}.manifest.json"
SUMS_NAME = f"{STEM}.SHA256SUMS"


class PackageError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PackageError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes, label: str) -> dict:
    def unique(pairs: list[tuple]) -> dict:
        result = {}
        for key, value in pairs:
            require(key not in result, f"{label} has a duplicate JSON key.")
            result[key] = value
        return result

    def invalid_constant(_: str) -> None:
        raise PackageError(f"{label} must use strict JSON.")

    try:
        result = json.loads(data.decode("utf-8"), object_pairs_hook=unique,
                            parse_constant=invalid_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise PackageError(f"{label} must be strict UTF-8 JSON.") from exc
    require(isinstance(result, dict), f"{label} must be a JSON object.")
    return result


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def check_plain_text(value: str, limit: int, label: str) -> None:
    require(isinstance(value, str) and 0 < len(value) <= limit
            and value == value.strip()
            and all(ch.isprintable() and ch not in "<>`" for ch in value),
            f"Invalid portable {label} text.")


def check_link(value: str) -> None:
    check_plain_text(value, 1024, "public URL")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and parsed.netloc == "github.com"
            and parsed.username is None and parsed.password is None
            and parsed.path and not parsed.query and not parsed.fragment,
            "Invalid portable public URL.")


def validate_metadata(source: dict[str, bytes]) -> None:
    portable = strict_json(source[PORTABLE], "Portable manifest")
    compatibility = strict_json(source[COMPATIBILITY], "Codex manifest")
    listing = strict_json(source[LISTING], "Submission listing")
    availability = strict_json(source[AVAILABILITY], "Availability record")

    website = REPOSITORY
    support = f"{REPOSITORY}/issues"
    privacy = f"{REPOSITORY}/blob/main/PRIVACY.md"
    common_interface = {
        "displayName": DISPLAY_NAME,
        "shortDescription": SUBTITLE,
        "developerName": PUBLISHER,
        "category": CATEGORY,
        "capabilities": ["Read"],
        "websiteURL": website,
        "defaultPrompt": PROMPTS,
    }
    compatibility_interface = {
        **common_interface,
        "longDescription": (
            "Review fixed software changes, verification evidence, remaining risks, "
            "and required human checks before merge, release, or deployment."
        ),
    }
    require(compatibility == {
        **PACKAGE_FIELDS, "skills": "./skills/", "interface": compatibility_interface,
    }, "Codex manifest has an unexpected shape or current value.")

    require(listing == {
        "submissionType": "skills-only",
        "pluginName": DISPLAY_NAME,
        "version": PLUGIN_VERSION,
        "publisher": PUBLISHER,
        "shortDescription": SUBTITLE,
        "longDescription": LISTING_DESCRIPTION,
        "category": CATEGORY,
        "websiteUrl": website,
        "supportUrl": support,
        "privacyUrl": privacy,
        "termsUrl": f"{REPOSITORY}/blob/main/LICENSE",
        "developerIdentity": {
            "type": "business", "name": PUBLISHER,
            "verificationStatus": "PENDING HUMAN CHECK",
        },
        "logoStatus": "PENDING APPROVED ASSET",
        "skills": [{"name": NAME, "path": MIRROR}],
        "releaseStatus": "pre-release",
        "publicDirectoryStatus": "not-submitted",
    }, "Submission listing has an unexpected shape or current value.")

    interface = {
        **{key: compatibility["interface"][key] for key in common_interface},
        "displayName": listing["pluginName"],
        "shortDescription": listing["shortDescription"],
        "developerName": listing["publisher"],
        "category": listing["category"],
        "longDescription": listing["longDescription"],
        "websiteURL": listing["websiteUrl"],
        "supportURL": listing["supportUrl"],
        "privacyPolicyURL": listing["privacyUrl"],
    }
    require(portable == {
        "$schema": SCHEMA,
        **{key: compatibility[key] for key in PACKAGE_FIELDS},
        "extensions": {"com.openai": {"interface": interface}},
    }, "Portable manifest must match the exact listing and Codex source mapping.")

    for key, limit in (
        ("displayName", 30), ("shortDescription", 30), ("developerName", 80),
        ("longDescription", 4000), ("category", 80),
    ):
        check_plain_text(interface[key], limit, key)
    check_plain_text(portable["description"], 1024, "package description")
    for key in ("websiteURL", "supportURL", "privacyPolicyURL"):
        check_link(interface[key])
    prompts = interface["defaultPrompt"]
    require(0 < len(prompts) <= 3, "Invalid portable prompt count.")
    for prompt in prompts:
        check_plain_text(prompt, 128, "starter prompt")
        require(not re.search(r"\bmcp\b", normalized(prompt)), "Invalid starter prompt.")
    require(len({normalized(prompt) for prompt in prompts}) == len(prompts),
            "Portable starter prompts must be unique after normalization.")

    require(sha256(source[AVAILABILITY]) == AVAILABILITY_SHA256
            and availability.get("status") == "PENDING HUMAN DECISION"
            and availability.get("recommendedInitialAvailability")
            == ["Japan", "Taiwan", "United States"],
            "Availability must retain the fixed pending recommendation.")


@contextmanager
def directory(start: int | None, parts: tuple[str, ...]):
    fd = os.open("/" if start is None else ".", DIR_FLAGS, dir_fd=start)
    try:
        for part in parts:
            next_fd = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd
    finally:
        os.close(fd)


def read_regular(parent_fd: int, name: str, maximum: int, *, single_link: bool = False) -> bytes:
    fd = os.open(name, READ_FLAGS, dir_fd=parent_fd)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and (not single_link or before.st_nlink == 1),
                "Input must be a regular file.")
        require(before.st_size <= maximum, "Input exceeds its bounded size.")
        value = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        require(len(value) == before.st_size == after.st_size
                and before.st_mtime_ns == after.st_mtime_ns
                and before.st_ctime_ns == after.st_ctime_ns,
                "Input size or identity changed during the read.")
        return value


def read_source(root_fd: int, path: str) -> bytes:
    *parents, name = path.split("/")
    with directory(root_fd, tuple(parents)) as parent_fd:
        return read_regular(parent_fd, name, MAX_LOCAL_BYTES)


def validate_metadata_at(root: Path) -> None:
    """Check ordinary source and test fixtures without requiring Git."""
    root = root.absolute()
    with directory(None, root.parts[1:]) as root_fd:
        validate_metadata({path: read_source(root_fd, path) for path in METADATA_FILES})


def git(root: Path, *arguments: str) -> bytes:
    env = {
        "PATH": os.defpath,
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false",
         "-c", "protocol.allow=never", *arguments],
        cwd=root, env=env, capture_output=True, timeout=20, check=False,
    )
    require(result.returncode == 0, f"Git source evidence unavailable ({arguments[0]}).")
    return result.stdout


def git_object_id(kind: str, content: bytes) -> str:
    header = f"{kind} {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content, usedforsecurity=False).hexdigest()


def read_object(root: Path, kind: str, object_id: str) -> bytes:
    require(bool(FULL_SHA.fullmatch(object_id)), "Invalid Git object identity.")
    size = int(git(root, "cat-file", "-s", object_id))
    require(0 <= size <= MAX_LOCAL_BYTES, "Git object exceeds its bounded size.")
    data = git(root, "cat-file", kind, object_id)
    require(len(data) == size and git_object_id(kind, data) == object_id,
            "Git object bytes do not match the recorded identity.")
    return data


def tracked_tree(root: Path, tree: str) -> dict[str, tuple[str, str]]:
    tracked = {}
    normalized_paths = set()
    read_object(root, "tree", tree)
    for record in git(root, "ls-tree", "-r", "-t", "-z", tree).split(b"\0")[:-1]:
        fields, raw_path = record.split(b"\t", 1)
        mode, kind, object_id = fields.decode("ascii").split()
        path = raw_path.decode("ascii")
        require(all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) and part not in {".", ".."}
                    and part.casefold() != ".git" for part in path.split("/")),
                "Git source contains a path alias or unsupported path.")
        normalized_path = normalized(path)
        require(normalized_path not in normalized_paths, "Git source paths collide.")
        normalized_paths.add(normalized_path)
        if mode == "040000" and kind == "tree":
            read_object(root, "tree", object_id)
        else:
            require(mode in {"100644", "100755"} and kind == "blob",
                    "Git source contains a symlink, submodule or nonregular entry.")
            tracked[path] = (mode, object_id)
    return tracked


def check_index(root: Path, tracked: dict[str, tuple[str, str]]) -> None:
    indexed = {}
    for record in git(root, "ls-files", "--stage", "-z").split(b"\0")[:-1]:
        fields, raw_path = record.split(b"\t", 1)
        mode, object_id, stage = fields.decode("ascii").split()
        path = raw_path.decode("ascii")
        require(stage == "0" and path not in indexed, "Git index is unmerged.")
        indexed[path] = (mode, object_id)
    require(indexed == tracked, "Git index differs from the fixed source tree.")
    require(not git(root, "ls-files", "--others", "-z"), "Git source contains untracked files.")


class UniqueSkillLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        # SafeLoader still permits aliases and duplicate keys by default.
        mapping = super().construct_mapping(node, deep=deep)
        require(len(mapping) == len(node.value), "Skill YAML has duplicate or merged keys.")
        return mapping


def check_skill(content: bytes) -> None:
    text = content.decode("utf-8")
    require(text.startswith("---\n") and "\n---\n" in text[4:], "Skill front matter is missing.")
    front, body = text[4:].split("\n---\n", 1)
    require(not any(isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken))
                    for token in yaml.scan(front)), "Skill YAML aliases and anchors are unsupported.")
    doc = yaml.load(front, Loader=UniqueSkillLoader)
    require(isinstance(doc, dict) and doc.get("name") == NAME
            and doc.get("license") == "Apache-2.0"
            and doc.get("metadata") == {"author": PUBLISHER, "version": SKILL_VERSION}
            and isinstance(doc.get("description"), str)
            and 0 < len(doc["description"].strip()) <= 1024 and bool(body.strip())
            and len(f"{NAME}:{doc['name']}") <= 64,
            "Bundled Skill identity, independent version, or content is invalid.")


@dataclass(frozen=True)
class Source:
    commit: str
    tree: str
    members: tuple[tuple[str, bytes], ...]


def load_fixed_source(root: Path, source_ref: str) -> Source:
    require(bool(FULL_SHA.fullmatch(source_ref)), "Source ref must be a full lowercase commit SHA.")
    require(Path(__file__).absolute() == root / TOOL,
            "Run the canonical packaging tool from the repository root.")
    with directory(None, root.parts[1:]) as root_fd:
        with directory(root_fd, (".git",)):
            require(git(root, "rev-parse", "--show-toplevel").rstrip(b"\n") == os.fsencode(root),
                    "The current directory must be the fixed Git repository root.")
            require(git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip() == source_ref,
                    "Source ref does not match the checked-out HEAD.")
            commit = read_object(root, "commit", source_ref)
            tree = git(root, "rev-parse", "--verify", "HEAD^{tree}").decode().strip()
            require(commit.startswith(f"tree {tree}\n".encode()), "Fixed commit and tree do not match.")
            tracked = tracked_tree(root, tree)
            check_index(root, tracked)
            require(REQUIRED_FILES <= tracked.keys()
                    and all(tracked[path][0] == "100644" for path in REQUIRED_FILES),
                    "Required package inputs must be committed regular nonexecutable blobs.")
            require({path for path in tracked if path.startswith(f"{MIRROR}/")}
                    == {f"{MIRROR}/{path}" for path in SKILL_FILES},
                    "The committed Skill mirror must have the exact package membership.")
            require({path for path in tracked if path.startswith(f"{SUBMISSION}/portable/")}
                    == {PORTABLE}, "The committed portable source must contain only plugin.json.")

            source = {}
            for path, (mode, object_id) in tracked.items():
                value = read_source(root_fd, path)
                require(git_object_id("blob", value) == object_id,
                        f"Working source differs from Git: {path}.")
                if path in REQUIRED_FILES:
                    data = read_object(root, "blob", object_id)
                    require(data == value, f"Fixed blob does not match working source: {path}.")
                    source[path] = data
                with directory(root_fd, tuple(path.split("/")[:-1])) as parent_fd:
                    file_mode = os.stat(path.rsplit("/", 1)[-1], dir_fd=parent_fd, follow_symlinks=False).st_mode
                require(stat.S_ISREG(file_mode) and bool(file_mode & stat.S_IXUSR) == (mode == "100755"),
                        f"Working source mode differs from Git: {path}.")

            check_index(root, tracked)
            require(git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip() == source_ref,
                    "Git HEAD changed during source validation.")

    validate_metadata(source)
    require(all(source[path] == source[f"{MIRROR}/{path}"] for path in SKILL_FILES),
            "Canonical source and bundled Skill files must match byte-for-byte.")
    require(bool(source["LICENSE"].strip()) and bool(source["NOTICE"].strip())
            and source[f"{PLUGIN}/NOTICE"] == source["NOTICE"],
            "Root and bundled legal attribution must match the canonical source.")
    check_skill(source[f"{MIRROR}/SKILL.md"])
    members = tuple((path, source[SOURCE_MAP[path]]) for path in sorted(SOURCE_MAP))
    check_members(members)
    return Source(source_ref, tree, members)


def check_members(members: tuple[tuple[str, bytes], ...]) -> None:
    require(0 < len(members) <= MAX_ENTRIES and len(members) == 27,
            "Invalid portable package entry count.")
    require(sum(len(data) for _, data in members) <= MAX_EXPANDED_BYTES,
            "Expanded package exceeds its size bound.")
    paths = set()
    parents = set()
    for path, data in members:
        segments = path.split("/")
        require(len(segments) <= MAX_SEGMENTS and segments[0] == NAME
                and all(ZIP_SEGMENT.fullmatch(segment) for segment in segments),
                "Invalid portable package member path.")
        require(len(data) <= min(MAX_LOCAL_BYTES, MAX_ENTRY_BYTES),
                "Package member exceeds its size bound.")
        key = normalized(path)
        key_parents = {normalized("/".join(segments[:end])) for end in range(1, len(segments))}
        require(key not in paths and key not in parents and not paths & key_parents,
                "Portable package paths collide.")
        paths.add(key)
        parents.update(key_parents)
    require(tuple(path for path, _ in members) == tuple(sorted(SOURCE_MAP)),
            "Portable package must contain the exact sorted member inventory.")


def canonical_outputs(source: Source) -> dict[str, bytes]:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED, allowZip64=False) as archive:
        for path, data in source.members:
            member = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(member, data)
    zip_bytes = output.getvalue()
    require(len(zip_bytes) <= min(MAX_LOCAL_BYTES, MAX_ZIP_BYTES), "ZIP exceeds its size bound.")
    manifest = {
        "format_version": 1,
        "package_name": NAME,
        "plugin_version": PLUGIN_VERSION,
        "skill_version": SKILL_VERSION,
        "source_repository": REPOSITORY,
        "source_commit": source.commit,
        "source_tree": source.tree,
        "zip_sha256": sha256(zip_bytes),
        "members": [
            {"path": path, "size": len(data), "sha256": sha256(data)}
            for path, data in source.members
        ],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=True, indent=2) + "\n").encode("ascii")
    checksums = f"{sha256(zip_bytes)}  {ZIP_NAME}\n{sha256(manifest_bytes)}  {MANIFEST_NAME}\n"
    return {ZIP_NAME: zip_bytes, MANIFEST_NAME: manifest_bytes, SUMS_NAME: checksums.encode("ascii")}


def require_private(fd: int) -> None:
    details = os.fstat(fd)
    require(details.st_uid == os.geteuid() and details.st_mode & 0o077 == 0,
            "Output directory and its immediate parent must be private and owned by the current user.")


def check_outputs(fd: int, outputs: dict[str, bytes]) -> None:
    require_private(fd)
    require(set(os.listdir(fd)) == outputs.keys(), "Output directory must contain exactly three package files.")
    for name, expected in outputs.items():
        # Compare bytes with an immutable regeneration. Never parse or open
        # any member named by a supplied ZIP or path named by a supplied receipt.
        actual = read_regular(fd, name, len(expected), single_link=True)
        require(actual == expected, f"Output differs from canonical source bytes: {name}.")
    require(set(os.listdir(fd)) == outputs.keys(), "Output directory changed during verification.")


def build_outputs(parent_fd: int, name: str, outputs: dict[str, bytes]) -> None:
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    with directory(parent_fd, (name,)) as fd:
        created = []
        finished = False
        try:
            require_private(fd)
            for filename, content in outputs.items():
                output_fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                    mode=0o600, dir_fd=fd)
                created.append(filename)
                with os.fdopen(output_fd, "wb") as output:
                    output.write(content)
            check_outputs(fd, outputs)
            finished = True
        finally:
            if not finished:
                for filename in created:
                    os.unlink(filename, dir_fd=fd)
                os.rmdir(name, dir_fd=parent_fd)


def operate_on_outputs(root: Path, path: str, outputs: dict[str, bytes], build: bool) -> None:
    parts = path.split("/")
    if path.startswith("/"):
        parts = parts[1:]
    require(bool(parts) and all(part and part not in {".", ".."} for part in parts),
            "Output must use a canonical directory path.")
    target = Path(path) if path.startswith("/") else root / path
    require(target != root and root not in target.parents, "Output must be outside the source checkout.")
    with directory(None, target.parts[1:-1]) as parent_fd:
        require_private(parent_fd)
        if build:
            build_outputs(parent_fd, target.name, outputs)
        else:
            with directory(parent_fd, (target.name,)) as fd:
                check_outputs(fd, outputs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check-source", "build", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--source-ref", required=True)
        if name != "check-source":
            command.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        root = Path.cwd()
        source = load_fixed_source(root, args.source_ref)
        if args.command != "check-source":
            outputs = canonical_outputs(source)
            operate_on_outputs(root, args.output_dir, outputs, args.command == "build")
    except (PackageError, UnicodeError, yaml.YAMLError, OSError, ValueError, subprocess.SubprocessError) as exc:
        detail = str(exc) if isinstance(exc, PackageError) else "Unable to validate source or access package files safely."
        print(f"ERROR: {detail}", file=sys.stderr)
        return 1
    print(f"Skills-only Plugin {args.command}: PASS ({source.commit}, tree {source.tree})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
