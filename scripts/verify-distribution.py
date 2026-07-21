#!/usr/bin/env python3
"""Verify an Agentic Change Audit distribution archive and integrity files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SOURCE_REF_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})  ([^/\r\n]+)$")
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PACKAGE_MANIFEST_NAME = "PACKAGE-MANIFEST.json"
VERIFIED_SOURCE_IDENTITY = "verified_git_clean"
UNVERIFIED_SOURCE_IDENTITY = "unverified_test_fixture"
SOURCE_IDENTITIES = {VERIFIED_SOURCE_IDENTITY, UNVERIFIED_SOURCE_IDENTITY}
EXPECTED_SOURCE_URL = "https://github.com/landco-llc/agentic-change-audit"
EXPECTED_AUTHOR = "L&Co.LLC"
EXPECTED_SKILL_VERSION = "0.1.0"
EXPECTED_LICENSE_SHA256 = (
    "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
)
EXPECTED_NOTICE_BYTES = (
    "Agentic Change Audit\n"
    "Copyright 2026 L&Co.LLC\n"
    "\n"
    "Agentic Change Audit is developed and distributed by L&Co.LLC.\n"
    "\n"
    "Source:\n"
    f"{EXPECTED_SOURCE_URL}\n"
    "\n"
    "Licensed under the Apache License, Version 2.0.\n"
).encode("utf-8")
REQUIRED_ATTRIBUTION_PATHS = {
    "LICENSE",
    "NOTICE",
    "SKILL.md",
    "docs/legal-attribution.md",
}
REQUIRED_LEGAL_ATTRIBUTION_PHRASES = (
    "`LICENSE` contains the Apache License, Version 2.0 terms",
    "`NOTICE` records the project's legal attribution and source identity",
    "`SKILL.md` metadata separately identifies the author for Skill consumers",
    "These three mechanisms have distinct roles; none replaces either of the others",
    "Technical GitHub URLs may contain the repository identifier `landco-llc`",
    "the legal identity is `L&Co.LLC`",
    "Downstream redistributed copies must retain `LICENSE` and `NOTICE`",
    "Agentic Change Audit distribution contract",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify archive structure, manifest content, source identity, "
            "file hashes, deterministic ZIP metadata, and external checksums."
        )
    )
    parser.add_argument("archive", help="Distribution ZIP.")
    parser.add_argument("--manifest", required=True, help="External manifest JSON.")
    parser.add_argument("--checksums", required=True, help="SHA256SUMS file.")
    parser.add_argument(
        "--config",
        default="release/distribution-files.json",
        help="Distribution allowlist configuration.",
    )
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-source-ref", required=True)
    parser.add_argument(
        "--expected-source-identity",
        choices=sorted(SOURCE_IDENTITIES),
        default=VERIFIED_SOURCE_IDENTITY,
        help=(
            "Required manifest source identity. Release verification defaults to "
            "verified_git_clean. unverified_test_fixture is only for synthetic tests."
        ),
    )
    return parser.parse_args()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"File does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def validate_semver(value: str) -> None:
    match = SEMVER_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(f"Expected version is not valid ASCII SemVer: {value}")
    prerelease = match.group(4)
    if prerelease:
        for identifier in prerelease.split("."):
            if re.fullmatch(r"[0-9]+", identifier) and len(identifier) > 1:
                if identifier.startswith("0"):
                    raise ValueError(
                        "Numeric prerelease identifiers must not contain leading zeros."
                    )


def validate_source_ref(value: str) -> None:
    if not SOURCE_REF_PATTERN.fullmatch(value):
        raise ValueError(
            "Expected source ref must be a 40-character lowercase commit SHA."
        )


def load_config(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValueError("Distribution config must be a JSON object.")
    required = {
        "schema_version",
        "package_name",
        "archive_root",
        "source_repository",
        "files",
    }
    if set(data) != required:
        raise ValueError("Distribution config keys do not match the required schema.")
    if data["schema_version"] != 1:
        raise ValueError("Unsupported distribution config schema_version.")
    if data["package_name"] != "agentic-change-audit":
        raise ValueError("Unexpected package_name.")
    if data["archive_root"] != data["package_name"]:
        raise ValueError("archive_root must equal package_name.")
    files = data["files"]
    if (
        not isinstance(files, list)
        or not files
        or any(not isinstance(item, str) or not item for item in files)
    ):
        raise ValueError("Distribution files must be a non-empty string array.")
    if files != sorted(files) or len(files) != len(set(files)):
        raise ValueError("Distribution files must be sorted and unique.")
    for value in files:
        path_value = PurePosixPath(value)
        if (
            path_value.is_absolute()
            or any(part in {"", ".", ".."} for part in path_value.parts)
            or "\\" in value
            or any(part.startswith(".") for part in path_value.parts)
        ):
            raise ValueError(f"Invalid distribution path: {value}")
        basename = path_value.name.casefold()
        if (basename == "notice" or basename.startswith("notice.")) and value != "NOTICE":
            raise ValueError(
                f"Distribution NOTICE must use the exact archive-root path 'NOTICE': {value}"
            )
    missing_attribution = sorted(REQUIRED_ATTRIBUTION_PATHS - set(files))
    if missing_attribution:
        raise ValueError(
            "Distribution allowlist is missing required attribution paths: "
            f"{missing_attribution}"
        )
    return data


def read_regular_source_file(root: Path, relative: str) -> bytes:
    path = root / PurePosixPath(relative)
    if path.is_symlink():
        raise ValueError(f"Canonical attribution source must not be a symlink: {relative}")
    if not path.exists():
        raise ValueError(f"Canonical attribution source is missing: {relative}")
    if not path.is_file():
        raise ValueError(
            f"Canonical attribution source is not a regular file: {relative}"
        )
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Canonical attribution source escapes the repository root: {relative}"
        ) from exc
    return path.read_bytes()


def parse_skill_frontmatter(skill_bytes: bytes) -> dict[str, str]:
    try:
        text = skill_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Distributed SKILL.md must be valid UTF-8.") from exc
    if not text.startswith("---\n"):
        raise ValueError("Distributed SKILL.md is missing canonical frontmatter.")
    closing = text.find("\n---\n", 4)
    if closing == -1:
        raise ValueError("Distributed SKILL.md frontmatter is not closed.")
    frontmatter = text[4:closing]
    fields: dict[str, str] = {}
    metadata_section = False
    for line in frontmatter.splitlines():
        if line == "metadata:":
            metadata_section = True
            continue
        if metadata_section and line.startswith("  "):
            key, separator, value = line.strip().partition(":")
            if separator:
                fields[f"metadata.{key}"] = value.strip().strip('"\'')
            continue
        metadata_section = False
        key, separator, value = line.partition(":")
        if separator:
            fields[key] = value.strip().strip('"\'')
    return fields


def load_canonical_attribution_sources(config_path: Path) -> dict[str, bytes]:
    config_path = config_path.resolve()
    if config_path.name != "distribution-files.json" or config_path.parent.name != "release":
        raise ValueError(
            "Attribution verification requires release/distribution-files.json."
        )
    root = config_path.parent.parent
    sources = {
        relative: read_regular_source_file(root, relative)
        for relative in REQUIRED_ATTRIBUTION_PATHS
    }

    if sources["NOTICE"] != EXPECTED_NOTICE_BYTES:
        raise ValueError("Canonical NOTICE bytes do not match the attribution contract.")
    if sha256_bytes(sources["LICENSE"]) != EXPECTED_LICENSE_SHA256:
        raise ValueError("Canonical LICENSE differs from the fixed Apache-2.0 license.")

    skill_fields = parse_skill_frontmatter(sources["SKILL.md"])
    if skill_fields.get("name") != "agentic-change-audit":
        raise ValueError("Distributed SKILL.md name must remain company-neutral.")
    if skill_fields.get("metadata.author") != EXPECTED_AUTHOR:
        raise ValueError(
            f"Distributed SKILL.md metadata.author must equal {EXPECTED_AUTHOR!r}."
        )
    if skill_fields.get("metadata.version") != EXPECTED_SKILL_VERSION:
        raise ValueError(
            "Distributed SKILL.md metadata.version must remain "
            f"{EXPECTED_SKILL_VERSION!r}."
        )
    description = skill_fields.get("description", "").casefold()
    if "landco-llc" in description or "l&co.llc" in description:
        raise ValueError("Distributed SKILL.md description must remain company-neutral.")

    try:
        legal_text = sources["docs/legal-attribution.md"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Canonical legal attribution document must be valid UTF-8.") from exc
    for phrase in REQUIRED_LEGAL_ATTRIBUTION_PHRASES:
        if phrase not in legal_text:
            raise ValueError(
                "Canonical legal attribution document is missing required language: "
                f"{phrase!r}"
            )

    return sources


def parse_checksums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValueError(f"Checksums file does not exist: {path}") from exc

    if not lines:
        raise ValueError("Checksums file is empty.")

    result: dict[str, str] = {}
    for line in lines:
        match = CHECKSUM_LINE_PATTERN.fullmatch(line)
        if not match:
            raise ValueError(f"Invalid checksum line: {line!r}")
        digest, filename = match.groups()
        if filename in result:
            raise ValueError(f"Duplicate checksum filename: {filename}")
        result[filename] = digest
    return result


def validate_manifest(
    manifest: Any,
    config: dict[str, Any],
    expected_version: str,
    expected_source_ref: str,
    expected_source_identity: str,
) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict):
        raise ValueError("Package manifest must be a JSON object.")
    if set(manifest) != {"schema_version", "package", "files"}:
        raise ValueError("Package manifest keys do not match the required schema.")
    if manifest["schema_version"] != 1:
        raise ValueError("Unsupported package manifest schema_version.")

    package = manifest["package"]
    if not isinstance(package, dict):
        raise ValueError("Manifest package must be an object.")
    expected_package_keys = {
        "name",
        "version",
        "archive_root",
        "source_repository",
        "source_ref",
        "source_identity",
    }
    if set(package) != expected_package_keys:
        raise ValueError("Manifest package keys do not match the required schema.")

    expectations = {
        "name": config["package_name"],
        "version": expected_version,
        "archive_root": config["archive_root"],
        "source_repository": config["source_repository"],
        "source_ref": expected_source_ref,
        "source_identity": expected_source_identity,
    }
    for key, expected in expectations.items():
        if package[key] != expected:
            raise ValueError(
                f"Manifest package.{key} mismatch: expected {expected!r}, "
                f"found {package[key]!r}"
            )

    files = manifest["files"]
    if not isinstance(files, list):
        raise ValueError("Manifest files must be an array.")
    expected_paths = config["files"]
    actual_paths: list[str] = []
    for index, item in enumerate(files):
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            raise ValueError(f"Manifest file entry {index} is invalid.")
        if not isinstance(item["path"], str):
            raise ValueError(f"Manifest file entry {index} path is invalid.")
        if not isinstance(item["sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", item["sha256"]
        ):
            raise ValueError(f"Manifest file entry {index} sha256 is invalid.")
        if not isinstance(item["size"], int) or item["size"] < 0:
            raise ValueError(f"Manifest file entry {index} size is invalid.")
        actual_paths.append(item["path"])

    if actual_paths != expected_paths:
        raise ValueError(
            "Manifest file list does not exactly match the distribution allowlist."
        )
    return files


def validate_zip_member_name(name: str, archive_root: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe archive entry path: {name}")
    if "\\" in name:
        raise ValueError(f"Archive entry uses a non-POSIX separator: {name}")
    if not path.parts or path.parts[0] != archive_root:
        raise ValueError(f"Archive entry is outside the required root: {name}")


def verify_distribution(
    *,
    archive_path: Path,
    manifest_path: Path,
    checksums_path: Path,
    config_path: Path,
    expected_version: str,
    expected_source_ref: str,
    expected_source_identity: str = VERIFIED_SOURCE_IDENTITY,
) -> None:
    validate_semver(expected_version)
    validate_source_ref(expected_source_ref)
    if expected_source_identity not in SOURCE_IDENTITIES:
        raise ValueError(f"Unsupported expected source identity: {expected_source_identity}")

    config = load_config(config_path)
    canonical_attribution = load_canonical_attribution_sources(config_path)
    expected_prefix = f"{config['package_name']}-{expected_version}"
    expected_filenames = {
        f"{expected_prefix}.zip",
        f"{expected_prefix}.manifest.json",
    }

    if archive_path.name != f"{expected_prefix}.zip":
        raise ValueError("Archive filename does not match package name and version.")
    if manifest_path.name != f"{expected_prefix}.manifest.json":
        raise ValueError("Manifest filename does not match package name and version.")
    if checksums_path.name != f"{expected_prefix}.SHA256SUMS":
        raise ValueError("Checksums filename does not match package name and version.")

    checksums = parse_checksums(checksums_path)
    if set(checksums) != expected_filenames:
        raise ValueError(
            "Checksums file must contain exactly the archive and external manifest."
        )
    if checksums[archive_path.name] != sha256_file(archive_path):
        raise ValueError("Archive SHA-256 does not match the checksums file.")
    if checksums[manifest_path.name] != sha256_file(manifest_path):
        raise ValueError("Manifest SHA-256 does not match the checksums file.")

    external_manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(external_manifest_bytes.decode("utf-8"))
    canonical_manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if external_manifest_bytes != canonical_manifest_bytes:
        raise ValueError("External manifest is not in canonical JSON form.")
    manifest_files = validate_manifest(
        manifest,
        config,
        expected_version,
        expected_source_ref,
        expected_source_identity,
    )
    manifest_by_path = {item["path"]: item for item in manifest_files}

    expected_entries = {
        f"{config['archive_root']}/{relative}" for relative in config["files"]
    }
    internal_manifest_name = f"{config['archive_root']}/{PACKAGE_MANIFEST_NAME}"
    expected_entries.add(internal_manifest_name)

    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            if archive.comment:
                raise ValueError("Archive comment must be empty.")
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise ValueError("Archive contains duplicate entry names.")
            if set(names) != expected_entries:
                missing = sorted(expected_entries - set(names))
                extra = sorted(set(names) - expected_entries)
                raise ValueError(
                    f"Archive entries mismatch; missing={missing}, extra={extra}"
                )

            for info in infos:
                validate_zip_member_name(info.filename, config["archive_root"])
                if info.is_dir():
                    raise ValueError(
                        f"Explicit directory entries are not allowed: {info.filename}"
                    )
                if info.flag_bits & 0x1:
                    raise ValueError(f"Encrypted entries are not allowed: {info.filename}")
                if info.date_time != FIXED_ZIP_TIMESTAMP:
                    raise ValueError(
                        f"Archive entry timestamp is not deterministic: {info.filename}"
                    )
                if info.compress_type != zipfile.ZIP_STORED:
                    raise ValueError(
                        f"Archive entry must use ZIP_STORED: {info.filename}"
                    )
                if info.create_system != 3:
                    raise ValueError(
                        f"Archive entry must use Unix metadata: {info.filename}"
                    )
                mode = info.external_attr >> 16
                if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o644:
                    raise ValueError(
                        f"Archive entry mode must be regular 0644: {info.filename}"
                    )

            internal_manifest_bytes = archive.read(internal_manifest_name)
            if internal_manifest_bytes != external_manifest_bytes:
                raise ValueError(
                    "Internal and external package manifests are not byte-identical."
                )

            for relative in config["files"]:
                entry_name = f"{config['archive_root']}/{relative}"
                data = archive.read(entry_name)
                record = manifest_by_path[relative]
                if len(data) != record["size"]:
                    raise ValueError(f"Size mismatch for {relative}")
                if sha256_bytes(data) != record["sha256"]:
                    raise ValueError(f"SHA-256 mismatch for {relative}")
                canonical = canonical_attribution.get(relative)
                if canonical is not None and data != canonical:
                    raise ValueError(
                        f"Distributed attribution file differs from canonical source: {relative}"
                    )
    except FileNotFoundError as exc:
        raise ValueError(f"Distribution input does not exist: {exc.filename}") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid ZIP archive: {archive_path}") from exc


def main() -> int:
    args = parse_args()
    try:
        verify_distribution(
            archive_path=Path(args.archive),
            manifest_path=Path(args.manifest),
            checksums_path=Path(args.checksums),
            config_path=Path(args.config),
            expected_version=args.expected_version,
            expected_source_ref=args.expected_source_ref,
            expected_source_identity=args.expected_source_identity,
        )
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(f"Distribution verification: FAIL: {exc}", file=sys.stderr)
        return 1

    print("Distribution verification: PASS")
    print(f"- archive: {args.archive}")
    print(f"- manifest: {args.manifest}")
    print(f"- checksums: {args.checksums}")
    print(f"- source identity: {args.expected_source_identity}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
