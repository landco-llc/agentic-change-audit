from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/build-distribution.py"
VERIFY = ROOT / "scripts/verify-distribution.py"
SOURCE_REF = "0123456789abcdef0123456789abcdef01234567"
OTHER_SOURCE_REF = "fedcba9876543210fedcba9876543210fedcba98"
VERSION = "0.1.0-rc.1"
UNVERIFIED_IDENTITY = "unverified_test_fixture"
VERIFIED_IDENTITY = "verified_git_clean"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build_module = load_module("build_distribution_for_tests", BUILD)


class DistributionIntegrationTests(unittest.TestCase):
    def make_project(self, temp: str) -> tuple[Path, Path]:
        project = Path(temp) / "project"
        project.mkdir()
        (project / "release").mkdir()

        files = [
            "LICENSE",
            "README.md",
            "SKILL.md",
            "docs/example.md",
        ]
        config = {
            "schema_version": 1,
            "package_name": "agentic-change-audit",
            "archive_root": "agentic-change-audit",
            "source_repository": "https://github.com/landco-llc/agentic-change-audit",
            "files": files,
        }
        config_path = project / "release/distribution-files.json"
        config_path.write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        for relative in files:
            path = project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"fixture for {relative}\n", encoding="utf-8")
        return project, config_path

    def git(self, project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(project), *arguments],
            text=True,
            capture_output=True,
        )

    def make_git_project(
        self,
        temp: str,
        *,
        leave_runtime_untracked: bool = False,
    ) -> tuple[Path, str]:
        project, _ = self.make_project(temp)
        scripts = project / "scripts"
        scripts.mkdir()
        shutil.copy2(BUILD, scripts / "build-distribution.py")

        self.assertEqual(0, self.git(project, "init", "-q").returncode)
        self.assertEqual(
            0,
            self.git(project, "config", "user.name", "Distribution Test").returncode,
        )
        self.assertEqual(
            0,
            self.git(project, "config", "user.email", "test@example.invalid").returncode,
        )
        self.assertEqual(0, self.git(project, "add", ".").returncode)
        if leave_runtime_untracked:
            self.assertEqual(
                0,
                self.git(project, "reset", "--", "docs/example.md").returncode,
            )
        committed = self.git(project, "commit", "-q", "-m", "fixture")
        self.assertEqual(0, committed.returncode, committed.stderr)
        head = self.git(project, "rev-parse", "HEAD")
        self.assertEqual(0, head.returncode, head.stderr)
        return project, head.stdout.strip()

    def run_build(
        self,
        project: Path,
        output: str = "dist",
        *,
        source_ref: str = SOURCE_REF,
        version: str = VERSION,
        verified: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        builder = (
            project / "scripts/build-distribution.py" if verified else BUILD
        )
        command = [
            sys.executable,
            str(builder),
            "--root",
            str(project),
            "--config",
            "release/distribution-files.json",
            "--version",
            version,
            "--source-ref",
            source_ref,
            "--output-dir",
            output,
        ]
        if not verified:
            command.append("--test-only-unverified-source")
        return subprocess.run(command, text=True, capture_output=True)

    def paths(
        self,
        project: Path,
        output: str = "dist",
        *,
        version: str = VERSION,
    ) -> tuple[Path, Path, Path]:
        directory = project / output
        prefix = f"agentic-change-audit-{version}"
        return (
            directory / f"{prefix}.zip",
            directory / f"{prefix}.manifest.json",
            directory / f"{prefix}.SHA256SUMS",
        )

    def run_verify(
        self,
        project: Path,
        output: str = "dist",
        *,
        source_ref: str = SOURCE_REF,
        version: str = VERSION,
        source_identity: str = UNVERIFIED_IDENTITY,
    ) -> subprocess.CompletedProcess[str]:
        archive, manifest, checksums = self.paths(
            project,
            output,
            version=version,
        )
        return subprocess.run(
            [
                sys.executable,
                str(VERIFY),
                str(archive),
                "--manifest",
                str(manifest),
                "--checksums",
                str(checksums),
                "--config",
                str(project / "release/distribution-files.json"),
                "--expected-version",
                version,
                "--expected-source-ref",
                source_ref,
                "--expected-source-identity",
                source_identity,
            ],
            text=True,
            capture_output=True,
        )

    def test_build_and_verify_valid_distribution(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            built = self.run_build(project)
            self.assertEqual(0, built.returncode, built.stderr)

            verified = self.run_verify(project)
            self.assertEqual(0, verified.returncode, verified.stderr)

            archive, manifest, checksums = self.paths(project)
            self.assertTrue(archive.is_file())
            self.assertTrue(manifest.is_file())
            self.assertTrue(checksums.is_file())

            manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(
                UNVERIFIED_IDENTITY,
                manifest_data["package"]["source_identity"],
            )
            with zipfile.ZipFile(archive) as package:
                self.assertIn(
                    "agentic-change-audit/PACKAGE-MANIFEST.json",
                    package.namelist(),
                )
                self.assertNotIn(".github/workflows/package.yml", package.namelist())

    def test_build_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            first = self.run_build(project, "dist-a")
            second = self.run_build(project, "dist-b")
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual(0, second.returncode, second.stderr)

            for left, right in zip(
                self.paths(project, "dist-a"),
                self.paths(project, "dist-b"),
                strict=True,
            ):
                self.assertEqual(
                    hashlib.sha256(left.read_bytes()).hexdigest(),
                    hashlib.sha256(right.read_bytes()).hexdigest(),
                )
                self.assertEqual(left.read_bytes(), right.read_bytes())

    def test_missing_allowlisted_file_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            (project / "docs/example.md").unlink()
            result = self.run_build(project)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("missing", result.stderr.lower())

    def test_source_symlink_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            target = project / "real-license"
            target.write_text("license\n", encoding="utf-8")
            (project / "LICENSE").unlink()
            try:
                (project / "LICENSE").symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            result = self.run_build(project)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("symlink", result.stderr.lower())

    def test_extra_archive_entry_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            self.assertEqual(0, self.run_build(project).returncode)
            archive, _, _ = self.paths(project)
            with zipfile.ZipFile(archive, "a", compression=zipfile.ZIP_STORED) as package:
                package.writestr("agentic-change-audit/unexpected.txt", b"unexpected")

            _, _, checksums = self.paths(project)
            lines = checksums.read_text(encoding="utf-8").splitlines()
            lines[0] = (
                f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}"
            )
            checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = self.run_verify(project)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("entries mismatch", result.stderr.lower())

    def test_modified_archive_fails_checksum(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            self.assertEqual(0, self.run_build(project).returncode)
            archive, _, _ = self.paths(project)
            archive.write_bytes(archive.read_bytes() + b"tampered")
            result = self.run_verify(project)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("sha-256", result.stderr.lower())

    def test_internal_manifest_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            self.assertEqual(0, self.run_build(project).returncode)
            archive, _, checksums = self.paths(project)

            rebuilt = archive.with_suffix(".rebuilt.zip")
            with zipfile.ZipFile(archive, "r") as source, zipfile.ZipFile(
                rebuilt, "w"
            ) as destination:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename.endswith("PACKAGE-MANIFEST.json"):
                        data = b"{}\n"
                    destination.writestr(info, data)
            rebuilt.replace(archive)

            lines = checksums.read_text(encoding="utf-8").splitlines()
            archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            lines[0] = f"{archive_digest}  {archive.name}"
            checksums.write_text("\n".join(lines) + "\n", encoding="utf-8")

            result = self.run_verify(project)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("not byte-identical", result.stderr.lower())

    def test_source_ref_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            self.assertEqual(0, self.run_build(project).returncode)
            result = self.run_verify(project, source_ref=OTHER_SOURCE_REF)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("source_ref mismatch", result.stderr)

    def test_repository_distribution_allowlist_is_runtime_only(self):
        config = json.loads(
            (ROOT / "release/distribution-files.json").read_text(encoding="utf-8")
        )
        files = config["files"]
        self.assertEqual(22, len(files))
        self.assertEqual(files, sorted(files))
        self.assertIn("SKILL.md", files)
        self.assertIn("standard/output-schema.json", files)
        self.assertIn("templates/audit-result.md", files)
        for forbidden_prefix in (
            ".github/",
            "release/",
            "scripts/",
            "tests/",
        ):
            self.assertFalse(
                any(path.startswith(forbidden_prefix) for path in files),
                forbidden_prefix,
            )
        self.assertNotIn("requirements-validation.txt", files)

    def test_release_document_pairs_and_cross_links(self):
        pairs = [
            (
                "release/README.md",
                "release/README.ja.md",
                "[日本語](README.ja.md)",
                "[English](README.md)",
            ),
            (
                "release/RELEASE_CHECKLIST.md",
                "release/RELEASE_CHECKLIST.ja.md",
                "[日本語](RELEASE_CHECKLIST.ja.md)",
                "[English](RELEASE_CHECKLIST.md)",
            ),
            (
                "release/RELEASE_NOTES_TEMPLATE.md",
                "release/RELEASE_NOTES_TEMPLATE.ja.md",
                "[日本語](RELEASE_NOTES_TEMPLATE.ja.md)",
                "[English](RELEASE_NOTES_TEMPLATE.md)",
            ),
        ]
        for english, japanese, english_link, japanese_link in pairs:
            english_path = ROOT / english
            japanese_path = ROOT / japanese
            self.assertTrue(english_path.is_file(), english)
            self.assertTrue(japanese_path.is_file(), japanese)
            self.assertIn(english_link, english_path.read_text(encoding="utf-8"))
            self.assertIn(japanese_link, japanese_path.read_text(encoding="utf-8"))

    def test_verified_git_build_succeeds_for_clean_head(self):
        with tempfile.TemporaryDirectory() as temp:
            project, head = self.make_git_project(temp)
            built = self.run_build(
                project,
                source_ref=head,
                verified=True,
            )
            self.assertEqual(0, built.returncode, built.stderr)
            verified = self.run_verify(
                project,
                source_ref=head,
                source_identity=VERIFIED_IDENTITY,
            )
            self.assertEqual(0, verified.returncode, verified.stderr)

    def test_verified_git_build_rejects_wrong_head(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_git_project(temp)
            result = self.run_build(
                project,
                source_ref="0" * 40,
                verified=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("does not match git head", result.stderr.lower())

    def test_verified_git_build_rejects_dirty_runtime_file(self):
        with tempfile.TemporaryDirectory() as temp:
            project, head = self.make_git_project(temp)
            (project / "README.md").write_text("dirty\n", encoding="utf-8")
            result = self.run_build(project, source_ref=head, verified=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("differs", result.stderr.lower())

    def test_verified_git_build_rejects_untracked_allowlisted_file(self):
        with tempfile.TemporaryDirectory() as temp:
            project, head = self.make_git_project(
                temp,
                leave_runtime_untracked=True,
            )
            result = self.run_build(project, source_ref=head, verified=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("git source identity check failed", result.stderr.lower())

    def test_unverified_fixture_requires_explicit_verifier_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            self.assertEqual(0, self.run_build(project).returncode)
            result = self.run_verify(
                project,
                source_identity=VERIFIED_IDENTITY,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("source_identity mismatch", result.stderr)

    def test_unicode_semver_digits_fail_builder_and_verifier(self):
        with tempfile.TemporaryDirectory() as temp:
            project, _ = self.make_project(temp)
            invalid_version = "1١.0.0"
            built = self.run_build(project, version=invalid_version)
            self.assertNotEqual(0, built.returncode)
            self.assertIn("ascii semver", built.stderr.lower())

            self.assertEqual(0, self.run_build(project).returncode)
            verified = self.run_verify(project, version=invalid_version)
            self.assertNotEqual(0, verified.returncode)
            self.assertIn("ascii semver", verified.stderr.lower())

    def test_partial_publish_failure_removes_entire_output_set(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "dist"
            output_dir.mkdir()
            output_bytes = {
                "package.zip": b"new zip",
                "package.manifest.json": b"new manifest",
                "package.SHA256SUMS": b"new checksums",
            }
            for name in output_bytes:
                (output_dir / name).write_bytes(b"old")

            original_replace = build_module.os.replace
            calls = 0

            def fail_on_third_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("injected replacement failure")
                return original_replace(source, target)

            with mock.patch.object(
                build_module.os,
                "replace",
                side_effect=fail_on_third_replace,
            ):
                with self.assertRaises(OSError):
                    build_module.publish_output_set(output_dir, output_bytes)

            for name in output_bytes:
                self.assertFalse((output_dir / name).exists(), name)

    def test_release_docs_distinguish_transport_zip_and_verified_source(self):
        english_readme = (ROOT / "release/README.md").read_text(encoding="utf-8")
        japanese_readme = (ROOT / "release/README.ja.md").read_text(encoding="utf-8")
        english_checklist = (ROOT / "release/RELEASE_CHECKLIST.md").read_text(
            encoding="utf-8"
        )
        japanese_checklist = (ROOT / "release/RELEASE_CHECKLIST.ja.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("outer transport ZIP", english_readme)
        self.assertIn("never a GitHub Release asset", english_checklist)
        self.assertIn("verified_git_clean", english_readme)
        self.assertIn("外側のtransport ZIP", japanese_readme)
        self.assertIn("GitHub Release assetには使用しない", japanese_checklist)
        self.assertIn("verified_git_clean", japanese_readme)


if __name__ == "__main__":
    unittest.main()
