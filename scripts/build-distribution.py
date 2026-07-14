#!/usr/bin/env python3
"""Build a deterministic Agentic Change Audit distribution archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
SOURCE_REF_PATTERN = re.compile(r"^[0-9a-f]{40}$")
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
PACKAGE_MANIFEST_NAME = "PACKAGE-MANIFEST.json"
VERIFIED_SOURCE_IDENTITY = "verified_git_clean"
UNVERIFIED_SOURCE_IDENTITY = "unverified_test_fixture"


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
    source_identity: str


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
    parser.add_argument(
        "--version",
        required=True,
        help="ASCII Semantic Version without a v prefix.",
    )
    parser.add_argument(
        "--source-ref",
        required=True,
        help="Exact 40-character lowercase source commit SHA.",
    )
    parser.add_argument("--output-dir", default="dist", help="Output directory.")
    parser.add_argument(
        "--test-only-unverified-source",
        action="store_true",
        help=(
            "Allow a non-Git synthetic test fixture. The manifest is marked "
            "unverified_test_fixture and normal verification rejects it. "
            "Never use this option for release artifacts."
        ),
    )
    return parser.parse_args()


def validate_semver(value: str) -> str:
    match = SEMVER_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(f"Version is not valid ASCII SemVer: {value}")

    prerelease = match.group(4)
    if prerelease:
        for identifier in prerelease.split("."):
            if re.fullmatch(r"[0-9]+", identifier) and len(identifier) > 1:
                if identifier.startswith("0"):
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
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
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


def run_git(
    root: Path,
    arguments: list[str],
    *,
    binary: bool = False,
) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=not binary,
        check=False,
    )
    if result.returncode != 0:
        stderr = (
            result.stderr.decode("utf-8", errors="replace")
            if binary
            else result.stderr
        )
        raise ValueError(
            f"Git source identity check failed for {' '.join(arguments)}: "
            f"{stderr.strip()}"
        )
    return result.stdout


def verified_identity_paths(
    root: Path,
    config_path: Path,
    config: DistributionConfig,
) -> tuple[str, ...]:
    try:
        config_relative = config_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("Distribution config must be inside the repository root.") from exc

    builder_path = Path(__file__).resolve()
    try:
        builder_relative = builder_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(
            "Verified builds must use the tracked scripts/build-distribution.py "
            "from the repository being packaged."
        ) from exc

    if builder_relative != "scripts/build-distribution.py":
        raise ValueError(
            "Verified builds must use scripts/build-distribution.py at its canonical path."
        )

    return tuple(dict.fromkeys((builder_relative, config_relative, *config.files)))


def verify_git_source_identity(
    root: Path,
    config_path: Path,
    config: DistributionConfig,
    source_ref: str,
) -> str:
    repository_root = Path(
        str(run_git(root, ["rev-parse", "--show-toplevel"])).strip()
    ).resolve()
    if repository_root != root:
        raise ValueError(
            f"Repository root mismatch: expected {root}, found {repository_root}"
        )

    actual_head = str(run_git(root, ["rev-parse", "HEAD"])).strip()
    if actual_head != source_ref:
        raise ValueError(
            f"source-ref does not match git HEAD: expected {actual_head}, "
            f"received {source_ref}"
        )

    identity_paths = verified_identity_paths(root, config_path, config)
    for relative in identity_paths:
        path = root / PurePosixPath(relative)
        if path.is_symlink():
            raise ValueError(f"Source identity path must not be a symlink: {relative}")
        run_git(root, ["ls-files", "--error-unmatch", "--", relative])
        committed = run_git(root, ["show", f"{source_ref}:{relative}"], binary=True)
        current = path.read_bytes()
        if committed != current:
            raise ValueError(
                f"Source identity path differs from {source_ref}: {relative}"
            )

    status = str(
        run_git(
            root,
            ["status", "--porcelain=v1", "--untracked-files=all", "--", *identity_paths],
        )
    ).strip()
    if status:
        raise ValueError(
            "Package-affecting source paths are not clean:\n" + status
        )

    return VERIFIED_SOURCE_IDENTITY


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
    source_identity: str,
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
            "source_identity": source_identity,
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


def write_synced_file(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def publish_output_set(
    output_dir: Path,
    output_bytes: dict[str, bytes],
) -> dict[str, Path]:
    """Publish all outputs, or remove the whole version set after any failure."""
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = {name: output_dir / name for name in output_bytes}

    with tempfile.TemporaryDirectory(
        prefix=".agentic-change-audit-output-",
        dir=output_dir.parent,
    ) as temporary:
        staging_dir = Path(temporary)
        for name, data in output_bytes.items():
            write_synced_file(staging_dir / name, data)
        fsync_directory(staging_dir)

        try:
            for target in targets.values():
                target.unlink(missing_ok=True)
            for name, target in targets.items():
                os.replace(staging_dir / name, target)
            fsync_directory(output_dir)
        except BaseException:
            cleanup_errors: list[str] = []
            for target in targets.values():
                try:
                    target.unlink(missing_ok=True)
                except OSError as exc:
                    cleanup_errors.append(f"{target}: {exc}")
            if cleanup_errors:
                raise RuntimeError(
                    "Output publication failed and cleanup was incomplete: "
                    + "; ".join(cleanup_errors)
                )
            raise

    return targets


def build_distribution(
    *,
    root: Path,
    config_path: Path,
    version: str,
    source_ref: str,
    output_dir: Path,
    test_only_unverified_source: bool = False,
) -> BuildOutputs:
    version = validate_semver(version)
    source_ref = validate_source_ref(source_ref)
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir

    config = load_config(config_path)
    if test_only_unverified_source:
        source_identity = UNVERIFIED_SOURCE_IDENTITY
    else:
        source_identity = verify_git_source_identity(
            root,
            config_path,
            config,
            source_ref,
        )

    file_bytes = read_source_files(root, config)

    if not test_only_unverified_source:
        verify_git_source_identity(root, config_path, config, source_ref)

    manifest = build_manifest(
        config,
        version,
        source_ref,
        source_identity,
        file_bytes,
    )
    manifest_bytes = canonical_json_bytes(manifest)
    archive_bytes = build_archive_bytes(config, file_bytes, manifest_bytes)

    prefix = f"{config.package_name}-{version}"
    archive_name = f"{prefix}.zip"
    manifest_name = f"{prefix}.manifest.json"
    checksums_name = f"{prefix}.SHA256SUMS"
    checksum_lines = [
        f"{sha256_bytes(archive_bytes)}  {archive_name}",
        f"{sha256_bytes(manifest_bytes)}  {manifest_name}",
    ]
    checksums_bytes = ("\n".join(checksum_lines) + "\n").encode("utf-8")

    published = publish_output_set(
        output_dir,
        {
            archive_name: archive_bytes,
            manifest_name: manifest_bytes,
            checksums_name: checksums_bytes,
        },
    )

    return BuildOutputs(
        archive=published[archive_name],
        manifest=published[manifest_name],
        checksums=published[checksums_name],
        source_identity=source_identity,
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
            test_only_unverified_source=args.test_only_unverified_source,
        )
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"Distribution build: FAIL: {exc}", file=sys.stderr)
        return 1

    print("Distribution build: PASS")
    print(f"- archive: {outputs.archive}")
    print(f"- manifest: {outputs.manifest}")
    print(f"- checksums: {outputs.checksums}")
    print(f"- source identity: {outputs.source_identity}")
    print(f"- archive sha256: {sha256_file(outputs.archive)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
