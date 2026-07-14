#!/usr/bin/env python3
"""Build a deterministic Agentic Change Audit distribution archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SOURCE_REF_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PACKAGE_MANIFEST_NAME = "PACKAGE-MANIFEST.json"


@dataclass(frozen=True)
class DistributionConfig:
    schema_version: int
    package_name: str
    archive_root: str
    source_repository: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class BuildOutputs:
    archive: Path
    manifest: Path
    checksums: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic, versioned ZIP whose internal root remains "
            "'agentic-change-audit' so the Skill name matches its parent directory."
        )
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--config",
        default="release/distribution-files.json",
        help="Distribution allowlist configuration.",
    )
    parser.add_argument("--version", required=True, help="Semantic version without a v prefix.")
    parser.add_argument(
        "--source-ref",
        required=True,
        help="Exact 40-character lowercase source commit SHA.",
    )
    parser.add_argument("--output-dir", default="dist", help="Output directory.")
    return parser.parse_args()


def validate_semver(value: str) -> str:
    match = SEMVER_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(f"Version is not valid SemVer: {value}")

    prerelease = match.group(4)
    if prerelease:
        for identifier in prerelease.split("."):
            if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
                raise ValueError(
                    "Numeric prerelease identifiers must not contain leading zeros: "
                    f"{identifier}"
                )
    return value


def validate_source_ref(value: str) -> str:
    if not SOURCE_REF_PATTERN.fullmatch(value):
        raise ValueError(
            "source-ref must be an exact 40-character lowercase hexadecimal commit SHA."
        )
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative_file_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Distribution file paths must be non-empty strings.")

    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Invalid distribution file path: {value}")
    if "\\" in value:
        raise ValueError(f"Distribution file paths must use POSIX separators: {value}")
    if value.startswith(".") or any(part.startswith(".") for part in path.parts):
        raise ValueError(f"Hidden paths are not allowed in the runtime package: {value}")
    return value


def load_config(path: Path) -> DistributionConfig:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Distribution config does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Distribution config must be a JSON object.")

    expected_keys = {
        "schema_version",
        "package_name",
        "archive_root",
        "source_repository",
        "files",
    }
    if set(data) != expected_keys:
        missing = sorted(expected_keys - set(data))
        extra = sorted(set(data) - expected_keys)
        raise ValueError(
            f"Distribution config keys mismatch; missing={missing}, extra={extra}"
        )

    if data["schema_version"] != 1:
        raise ValueError("Unsupported distribution config schema_version.")
    for key in ("package_name", "archive_root", "source_repository"):
        if not isinstance(data[key], str) or not data[key]:
            raise ValueError(f"{key} must be a non-empty string.")

    if data["package_name"] != "agentic-change-audit":
        raise ValueError("package_name must be agentic-change-audit.")
    if data["archive_root"] != data["package_name"]:
        raise ValueError(
            "archive_root must equal package_name so SKILL.md matches its parent directory."
        )

    files = data["files"]
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty JSON array.")

    normalized = tuple(validate_relative_file_path(item) for item in files)
    if len(normalized) != len(set(normalized)):
        raise ValueError("Distribution file list contains duplicates.")
    if list(normalized) != sorted(normalized):
        raise ValueError("Distribution file list must be sorted lexicographically.")
    if PACKAGE_MANIFEST_NAME in normalized:
        raise ValueError(f"{PACKAGE_MANIFEST_NAME} is generated and must not be listed.")

    return DistributionConfig(
        schema_version=1,
        package_name=data["package_name"],
        archive_root=data["archive_root"],
        source_repository=data["source_repository"],
        files=normalized,
    )


def read_source_files(root: Path, config: DistributionConfig) -> dict[str, bytes]:
    root_resolved = root.resolve()
    result: dict[str, bytes] = {}

    for relative in config.files:
        source = root / PurePosixPath(relative)
        if not source.exists():
            raise ValueError(f"Required distribution file is missing: {relative}")
        if source.is_symlink():
            raise ValueError(f"Symlinks are not allowed in the distribution: {relative}")
        if not source.is_file():
            raise ValueError(f"Distribution entry is not a regular file: {relative}")

        resolved = source.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(
                f"Distribution source escapes the repository root: {relative}"
            ) from exc

        result[relative] = source.read_bytes()

    return result


def build_manifest(
    config: DistributionConfig,
    version: str,
    source_ref: str,
    file_bytes: dict[str, bytes],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package": {
            "name": config.package_name,
            "version": version,
            "archive_root": config.archive_root,
            "source_repository": config.source_repository,
            "source_ref": source_ref,
        },
        "files": [
            {
                "path": relative,
                "sha256": sha256_bytes(file_bytes[relative]),
                "size": len(file_bytes[relative]),
            }
            for relative in config.files
        ],
    }


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    info.flag_bits = 0
    return info


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def build_archive_bytes(
    config: DistributionConfig,
    file_bytes: dict[str, bytes],
    manifest_bytes: bytes,
) -> bytes:
    with tempfile.SpooledTemporaryFile(max_size=4 * 1024 * 1024) as stream:
        with zipfile.ZipFile(stream, "w", allowZip64=False) as archive:
            for relative in config.files:
                archive.writestr(
                    zip_info(f"{config.archive_root}/{relative}"),
                    file_bytes[relative],
                )
            archive.writestr(
                zip_info(f"{config.archive_root}/{PACKAGE_MANIFEST_NAME}"),
                manifest_bytes,
            )
        stream.seek(0)
        return stream.read()


def build_distribution(
    *,
    root: Path,
    config_path: Path,
    version: str,
    source_ref: str,
    output_dir: Path,
) -> BuildOutputs:
    version = validate_semver(version)
    source_ref = validate_source_ref(source_ref)
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir

    config = load_config(config_path)
    file_bytes = read_source_files(root, config)
    manifest = build_manifest(config, version, source_ref, file_bytes)
    manifest_bytes = canonical_json_bytes(manifest)
    archive_bytes = build_archive_bytes(config, file_bytes, manifest_bytes)

    prefix = f"{config.package_name}-{version}"
    archive_path = output_dir / f"{prefix}.zip"
    manifest_path = output_dir / f"{prefix}.manifest.json"
    checksums_path = output_dir / f"{prefix}.SHA256SUMS"

    atomic_write(archive_path, archive_bytes)
    atomic_write(manifest_path, manifest_bytes)

    checksum_lines = [
        f"{sha256_bytes(archive_bytes)}  {archive_path.name}",
        f"{sha256_bytes(manifest_bytes)}  {manifest_path.name}",
    ]
    atomic_write(checksums_path, ("\n".join(checksum_lines) + "\n").encode("utf-8"))

    return BuildOutputs(
        archive=archive_path,
        manifest=manifest_path,
        checksums=checksums_path,
    )


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    try:
        outputs = build_distribution(
            root=root,
            config_path=Path(args.config),
            version=args.version,
            source_ref=args.source_ref,
            output_dir=Path(args.output_dir),
        )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Distribution build: FAIL: {exc}", file=sys.stderr)
        return 1

    print("Distribution build: PASS")
    print(f"- archive: {outputs.archive}")
    print(f"- manifest: {outputs.manifest}")
    print(f"- checksums: {outputs.checksums}")
    print(f"- archive sha256: {sha256_file(outputs.archive)}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main())
