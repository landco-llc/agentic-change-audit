from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts/build-distribution.py"
VERIFY = ROOT / "scripts/verify-distribution.py"
SOURCE_REF = "0123456789abcdef0123456789abcdef01234567"
VERSION = "0.1.0-rc.1"


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

    def run_build(self, project: Path, output: str = "dist") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(BUILD),
                "--root",
                str(project),
                "--config",
                "release/distribution-files.json",
                "--version",
                VERSION,
                "--source-ref",
                SOURCE_REF,
                "--output-dir",
                output,
            ],
            text=True,
            capture_output=True,
        )

    def paths(self, project: Path, output: str = "dist") -> tuple[Path, Path, Path]:
        directory = project / output
        prefix = f"agentic-change-audit-{VERSION}"
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
    ) -> subprocess.CompletedProcess[str]:
        archive, manifest, checksums = self.paths(project, output)
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
                VERSION,
                "--expected-source-ref",
                source_ref,
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

            # Update the archive checksum so verification reaches the manifest comparison.
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
            result = self.run_verify(
                project,
                source_ref="fedcba9876543210fedcba9876543210fedcba98",
            )
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


if __name__ == "__main__":
    unittest.main()
