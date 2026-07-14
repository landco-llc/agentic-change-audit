#!/usr/bin/env python3
"""Verify an Agentic Change Audit distribution archive and its integrity files."""

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
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SOURCE_REF_PATTERN = re.compile(r"^[0-9a-f]{40}$")
CHECKSUM_LINE_PATTERN = re.compile(r"^([0-9a-f]{64})  ([^/\r\n]+)$")
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PACKAGE_MANIFEST_NAME = "PACKAGE-MANIFEST.json"


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
        raise ValueError(f"Expected version is not valid SemVer: {value}")
    prerelease = match.group(4)
    if prerelease:
        for identifier in prerelease.split("."):
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
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
    return data


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
    }
    if set(package) != expected_package_keys:
        raise ValueError("Manifest package keys do not match the required schema.")

    expectations = {
        "name": config["package_name"],
        "version": expected_version,
        "archive_root": config["archive_root"],
        "source_repository": config["source_repository"],
        "source_ref": expected_source_ref,
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
) -> None:
    validate_semver(expected_version)
    validate_source_ref(expected_source_ref)

    config = load_config(config_path)
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
    )
    manifest_by_path = {item["path"]: item for item in manifest_files}

    expected_entries = {
        f"{config['archive_root']}/{relative}"
        for relative in config["files"]
    }
    internal_manifest_name = (
        f"{config['archive_root']}/{PACKAGE_MANIFEST_NAME}"
    )
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
        )
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(f"Distribution verification: FAIL: {exc}", file=sys.stderr)
        return 1

    print("Distribution verification: PASS")
    print(f"- archive: {args.archive}")
    print(f"- manifest: {args.manifest}")
    print(f"- checksums: {args.checksums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
