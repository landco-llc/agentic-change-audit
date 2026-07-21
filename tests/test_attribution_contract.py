from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
BASE_SHA = "76f65300e24e69d3c5957c2a5a6755bd1b700216"
SOURCE_REF = "0123456789abcdef0123456789abcdef01234567"
VERSION = "0.1.0-dev.2"
ARCHIVE_ROOT = "agentic-change-audit"
NOTICE = ROOT / "NOTICE"
LICENSE = ROOT / "LICENSE"
SKILL = ROOT / "SKILL.md"
LEGAL = ROOT / "docs/legal-attribution.md"
SYNC = ROOT / "scripts/sync-codex-plugin.py"
VALIDATE_SKILL = ROOT / "scripts/validate-skill.py"
VALIDATE_PLUGIN = ROOT / "scripts/validate-codex-plugin.py"
BUILD = ROOT / "scripts/build-distribution.py"
VERIFY = ROOT / "scripts/verify-distribution.py"
CONFIG = ROOT / "release/distribution-files.json"
PLUGIN_MANIFEST = ROOT / "plugins/agentic-change-audit/.codex-plugin/plugin.json"


def subprocess_env() -> dict[str, str]:
    return dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def canonical_json_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_skill_repo(temp: str) -> Path:
    repo = Path(temp) / "skill"
    repo.mkdir()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    files = [*config["files"], "guides/zh-Hant/installation.md"]
    for relative in files:
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    return repo


def run_skill_validator(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            PYTHON,
            str(VALIDATE_SKILL),
            str(repo),
            "--expected-name",
            "agentic-change-audit",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


def make_sync_repo(temp: str) -> Path:
    repo = Path(temp) / "repo"
    repo.mkdir()
    config_destination = repo / "release/distribution-files.json"
    config_destination.parent.mkdir(parents=True)
    shutil.copy2(CONFIG, config_destination)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for relative in [*config["files"], "guides/zh-Hant/installation.md"]:
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    return repo


def run_sync(repo: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(SYNC), mode, "--root", str(repo)],
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


def make_distribution_project(temp: str) -> Path:
    project = Path(temp) / "project"
    (project / "release").mkdir(parents=True)
    files = [
        "LICENSE",
        "NOTICE",
        "SKILL.md",
        "docs/legal-attribution.md",
    ]
    config = {
        "schema_version": 1,
        "package_name": "agentic-change-audit",
        "archive_root": ARCHIVE_ROOT,
        "source_repository": "https://github.com/landco-llc/agentic-change-audit",
        "files": files,
    }
    (project / "release/distribution-files.json").write_bytes(
        canonical_json_bytes(config)
    )
    for relative in files:
        destination = project / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    return project


def distribution_paths(project: Path) -> tuple[Path, Path, Path]:
    prefix = f"agentic-change-audit-{VERSION}"
    output = project / "dist"
    return (
        output / f"{prefix}.zip",
        output / f"{prefix}.manifest.json",
        output / f"{prefix}.SHA256SUMS",
    )


def run_build(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            PYTHON,
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
            "dist",
            "--test-only-unverified-source",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


def run_verify(project: Path) -> subprocess.CompletedProcess[str]:
    archive, manifest, checksums = distribution_paths(project)
    return subprocess.run(
        [
            PYTHON,
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
            SOURCE_REF,
            "--expected-source-identity",
            "unverified_test_fixture",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


def refresh_checksums(project: Path) -> None:
    archive, manifest, checksums = distribution_paths(project)
    checksums.write_text(
        f"{sha256(archive.read_bytes())}  {archive.name}\n"
        f"{sha256(manifest.read_bytes())}  {manifest.name}\n",
        encoding="utf-8",
    )


def rewrite_archive(
    project: Path,
    *,
    remove: set[str] | None = None,
    rename: dict[str, str] | None = None,
    replace: dict[str, bytes] | None = None,
    duplicate: str | None = None,
    refresh: bool = True,
) -> None:
    archive, _, _ = distribution_paths(project)
    remove = remove or set()
    rename = rename or {}
    replace = replace or {}
    rebuilt = archive.with_name("rebuilt.zip")
    stored: list[tuple[zipfile.ZipInfo, bytes]] = []
    with zipfile.ZipFile(archive, "r") as source:
        for info in source.infolist():
            stored.append((copy.copy(info), source.read(info.filename)))
    with zipfile.ZipFile(rebuilt, "w", allowZip64=False) as destination:
        for info, data in stored:
            if info.filename in remove:
                continue
            original_name = info.filename
            info.filename = rename.get(original_name, original_name)
            destination.writestr(info, replace.get(original_name, data))
        if duplicate is not None:
            info, data = next(item for item in stored if item[0].filename == duplicate)
            destination.writestr(copy.copy(info), data)
    rebuilt.replace(archive)
    if refresh:
        refresh_checksums(project)


def write_manifest(project: Path, manifest_data: dict) -> bytes:
    _, manifest, _ = distribution_paths(project)
    data = canonical_json_bytes(manifest_data)
    manifest.write_bytes(data)
    internal = f"{ARCHIVE_ROOT}/PACKAGE-MANIFEST.json"
    rewrite_archive(project, replace={internal: data}, refresh=False)
    refresh_checksums(project)
    return data


def consistently_replace_file(project: Path, relative: str, data: bytes) -> None:
    _, manifest_path, _ = distribution_paths(project)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(item for item in manifest["files"] if item["path"] == relative)
    record["sha256"] = sha256(data)
    record["size"] = len(data)
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    rewrite_archive(
        project,
        replace={
            f"{ARCHIVE_ROOT}/{relative}": data,
            f"{ARCHIVE_ROOT}/PACKAGE-MANIFEST.json": manifest_bytes,
        },
        refresh=False,
    )
    refresh_checksums(project)


def make_plugin_repo(temp: str) -> Path:
    repo = Path(temp) / "repo"
    shutil.copytree(
        ROOT,
        repo,
        ignore=shutil.ignore_patterns(".git", "__pycache__"),
        symlinks=True,
    )
    return repo


def run_plugin_validator(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(repo / "scripts/validate-codex-plugin.py"), "--root", str(repo)],
        capture_output=True,
        text=True,
        check=False,
        env=subprocess_env(),
    )


class AttributionTestCase(unittest.TestCase):
    def assert_rejected(
        self, result: subprocess.CompletedProcess[str], pass_marker: str
    ) -> None:
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn(pass_marker, result.stdout)
        self.assertNotIn(pass_marker, result.stderr)

    def build_distribution(self, temp: str) -> Path:
        project = make_distribution_project(temp)
        built = run_build(project)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        return project


class NoticeByteContractTests(AttributionTestCase):
    def mutate_notice(self, temp: str, data: bytes) -> subprocess.CompletedProcess[str]:
        repo = make_skill_repo(temp)
        (repo / "NOTICE").write_bytes(data)
        return run_skill_validator(repo)

    def test_notice_01_exact_bytes_are_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_skill_validator(make_skill_repo(temp))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_notice_02_missing_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_skill_repo(temp)
            (repo / "NOTICE").unlink()
            self.assert_rejected(run_skill_validator(repo), "Skill validation: PASS")

    def test_notice_03_slug_as_legal_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            data = NOTICE.read_bytes().replace(b"L&Co.LLC", b"landco-llc")
            self.assert_rejected(self.mutate_notice(temp, data), "Skill validation: PASS")

    def test_notice_04_changed_copyright_year_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            data = NOTICE.read_bytes().replace(b"2026", b"2027")
            self.assert_rejected(self.mutate_notice(temp, data), "Skill validation: PASS")

    def test_notice_05_changed_source_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            data = NOTICE.read_bytes().replace(b"agentic-change-audit", b"wrong-source", 1)
            self.assert_rejected(self.mutate_notice(temp, data), "Skill validation: PASS")

    def test_notice_06_missing_final_newline_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assert_rejected(
                self.mutate_notice(temp, NOTICE.read_bytes().rstrip(b"\n")),
                "Skill validation: PASS",
            )

    def test_notice_07_utf8_bom_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assert_rejected(
                self.mutate_notice(temp, b"\xef\xbb\xbf" + NOTICE.read_bytes()),
                "Skill validation: PASS",
            )

    def test_notice_08_crlf_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assert_rejected(
                self.mutate_notice(temp, NOTICE.read_bytes().replace(b"\n", b"\r\n")),
                "Skill validation: PASS",
            )


class SkillAuthorContractTests(AttributionTestCase):
    def mutate_skill(self, temp: str, before: str, after: str) -> subprocess.CompletedProcess[str]:
        repo = make_skill_repo(temp)
        path = repo / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(before, text)
        path.write_text(text.replace(before, after, 1), encoding="utf-8")
        return run_skill_validator(repo)

    def test_skill_author_01_exact_legal_identity_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_skill_validator(make_skill_repo(temp))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_skill_author_02_github_slug_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(temp, "author: L&Co.LLC", "author: landco-llc")
            self.assert_rejected(result, "Skill validation: PASS")

    def test_skill_author_03_missing_author_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(temp, "  author: L&Co.LLC\n", "")
            self.assert_rejected(result, "Skill validation: PASS")

    def test_skill_author_04_spaced_company_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(temp, "author: L&Co.LLC", "author: L&Co. LLC")
            self.assert_rejected(result, "Skill validation: PASS")

    def test_skill_author_05_comma_company_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(temp, "author: L&Co.LLC", "author: L&Co., LLC")
            self.assert_rejected(result, "Skill validation: PASS")

    def test_skill_author_06_leading_space_in_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(
                temp, "author: L&Co.LLC", 'author: " L&Co.LLC"'
            )
            self.assert_rejected(result, "Skill validation: PASS")

    def test_skill_author_07_company_prefixed_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(
                temp,
                "name: agentic-change-audit",
                "name: landco-llc-agentic-change-audit",
            )
            self.assert_rejected(result, "Skill validation: PASS")

    def test_skill_author_08_company_prefixed_description_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            result = self.mutate_skill(
                temp,
                "description: Audit software changes",
                "description: L&Co.LLC Audit software changes",
            )
            self.assert_rejected(result, "Skill validation: PASS")


class PluginNoticeSyncContractTests(AttributionTestCase):
    def prepared(self, temp: str) -> Path:
        repo = make_sync_repo(temp)
        result = run_sync(repo, "--write")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return repo

    def test_plugin_sync_01_write_and_check_copy_both_notices(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            canonical = (repo / "NOTICE").read_bytes()
            self.assertEqual(canonical, (repo / "plugins/agentic-change-audit/NOTICE").read_bytes())
            self.assertEqual(
                canonical,
                (repo / "plugins/agentic-change-audit/skills/agentic-change-audit/NOTICE").read_bytes(),
            )
            checked = run_sync(repo, "--check")
            self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)

    def test_plugin_sync_02_missing_plugin_root_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            (repo / "plugins/agentic-change-audit/NOTICE").unlink()
            self.assert_rejected(run_sync(repo, "--check"), "Plugin Skill mirror (check): PASS")

    def test_plugin_sync_03_changed_plugin_root_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            (repo / "plugins/agentic-change-audit/NOTICE").write_text("changed\n", encoding="utf-8")
            self.assert_rejected(run_sync(repo, "--check"), "Plugin Skill mirror (check): PASS")

    def test_plugin_sync_04_changed_skill_mirror_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            path = repo / "plugins/agentic-change-audit/skills/agentic-change-audit/NOTICE"
            path.write_text("changed\n", encoding="utf-8")
            self.assert_rejected(run_sync(repo, "--check"), "Plugin Skill mirror (check): PASS")

    def test_plugin_sync_05_symlinked_canonical_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_sync_repo(temp)
            outside = Path(temp) / "outside-notice"
            outside.write_bytes(NOTICE.read_bytes())
            (repo / "NOTICE").unlink()
            try:
                (repo / "NOTICE").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_sync(repo, "--write"), "Plugin Skill mirror (write): PASS")

    def test_plugin_sync_06_symlinked_plugin_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            path = repo / "plugins/agentic-change-audit/NOTICE"
            path.unlink()
            try:
                path.symlink_to(repo / "NOTICE")
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_sync(repo, "--write"), "Plugin Skill mirror (write): PASS")

    def test_plugin_sync_07_symlinked_skill_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            path = repo / "plugins/agentic-change-audit/skills/agentic-change-audit/NOTICE"
            path.unlink()
            try:
                path.symlink_to(repo / "NOTICE")
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_sync(repo, "--write"), "Plugin Skill mirror (write): PASS")

    def test_plugin_sync_08_extra_notice_alias_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            (repo / "plugins/agentic-change-audit/NOTICE.txt").write_bytes(NOTICE.read_bytes())
            self.assert_rejected(run_sync(repo, "--check"), "Plugin Skill mirror (check): PASS")

    def test_plugin_sync_09_non_regular_plugin_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self.prepared(temp)
            path = repo / "plugins/agentic-change-audit/NOTICE"
            path.unlink()
            path.mkdir()
            self.assert_rejected(run_sync(repo, "--check"), "Plugin Skill mirror (check): PASS")

    def test_plugin_sync_10_plugin_root_escape_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_sync_repo(temp)
            plugin_parent = repo / "plugins"
            plugin_parent.mkdir()
            outside = Path(temp) / "outside-plugin"
            outside.mkdir()
            sentinel = outside / "sentinel.txt"
            sentinel.write_text("preserve\n", encoding="utf-8")
            try:
                (plugin_parent / "agentic-change-audit").symlink_to(
                    outside, target_is_directory=True
                )
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_sync(repo, "--write"), "Plugin Skill mirror (write): PASS")
            self.assertEqual("preserve\n", sentinel.read_text(encoding="utf-8"))


class DistributionAttributionContractTests(AttributionTestCase):
    def test_distribution_01_valid_package_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            result = run_verify(project)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_distribution_02_zip_omitting_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            rewrite_archive(project, remove={f"{ARCHIVE_ROOT}/NOTICE"})
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_03_duplicate_notice_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            rewrite_archive(project, duplicate=f"{ARCHIVE_ROOT}/NOTICE")
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_04_allowlist_omitting_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            path = project / "release/distribution-files.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["files"].remove("NOTICE")
            path.write_bytes(canonical_json_bytes(config))
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_05_manifest_omitting_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            _, manifest_path, _ = distribution_paths(project)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"] = [item for item in manifest["files"] if item["path"] != "NOTICE"]
            write_manifest(project, manifest)
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_06_manifest_notice_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            _, manifest_path, _ = distribution_paths(project)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = next(item for item in manifest["files"] if item["path"] == "NOTICE")
            record["sha256"] = "0" * 64
            write_manifest(project, manifest)
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_07_archive_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            archive, _, _ = distribution_paths(project)
            archive.write_bytes(archive.read_bytes() + b"tampered")
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_08_manifest_checksum_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            _, manifest, _ = distribution_paths(project)
            manifest.write_bytes(manifest.read_bytes() + b" ")
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_09_lowercase_notice_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            rewrite_archive(project, rename={f"{ARCHIVE_ROOT}/NOTICE": f"{ARCHIVE_ROOT}/notice"})
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_10_notice_txt_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            rewrite_archive(project, rename={f"{ARCHIVE_ROOT}/NOTICE": f"{ARCHIVE_ROOT}/NOTICE.txt"})
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_11_nested_only_notice_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            rewrite_archive(project, rename={f"{ARCHIVE_ROOT}/NOTICE": f"{ARCHIVE_ROOT}/docs/NOTICE"})
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_12_missing_legal_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            rewrite_archive(project, remove={f"{ARCHIVE_ROOT}/docs/legal-attribution.md"})
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_13_altered_legal_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            consistently_replace_file(project, "docs/legal-attribution.md", LEGAL.read_bytes() + b"changed\n")
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_14_slug_skill_author_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            data = SKILL.read_bytes().replace(b"author: L&Co.LLC", b"author: landco-llc")
            consistently_replace_file(project, "SKILL.md", data)
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_15_altered_license_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            consistently_replace_file(project, "LICENSE", LICENSE.read_bytes() + b"x")
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_16_changed_notice_source_url_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            data = NOTICE.read_bytes().replace(b"agentic-change-audit", b"wrong-source", 1)
            consistently_replace_file(project, "NOTICE", data)
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")

    def test_distribution_17_changed_notice_legal_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            project = self.build_distribution(temp)
            data = NOTICE.read_bytes().replace(b"L&Co.LLC", b"landco-llc")
            consistently_replace_file(project, "NOTICE", data)
            self.assert_rejected(run_verify(project), "Distribution verification: PASS")


class LicenseAndPathContractTests(AttributionTestCase):
    def test_license_path_01_exact_base_license_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_skill_validator(make_skill_repo(temp))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(
                "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
                sha256(LICENSE.read_bytes()),
            )

    def test_license_path_02_missing_license_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_skill_repo(temp)
            (repo / "LICENSE").unlink()
            self.assert_rejected(run_skill_validator(repo), "Skill validation: PASS")

    def test_license_path_03_one_byte_license_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_skill_repo(temp)
            path = repo / "LICENSE"
            path.write_bytes(path.read_bytes() + b"x")
            self.assert_rejected(run_skill_validator(repo), "Skill validation: PASS")

    def test_license_path_04_symlinked_license_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_skill_repo(temp)
            outside = Path(temp) / "outside-license"
            outside.write_bytes(LICENSE.read_bytes())
            (repo / "LICENSE").unlink()
            try:
                (repo / "LICENSE").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_skill_validator(repo), "Skill validation: PASS")

    def test_license_path_05_builder_rejects_symlinked_license(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_distribution_project(temp)
            outside = Path(temp) / "outside-license"
            outside.write_bytes(LICENSE.read_bytes())
            (project / "LICENSE").unlink()
            try:
                (project / "LICENSE").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_build(project), "Distribution build: PASS")

    def test_license_path_06_builder_rejects_symlinked_notice(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_distribution_project(temp)
            outside = Path(temp) / "outside-notice"
            outside.write_bytes(NOTICE.read_bytes())
            (project / "NOTICE").unlink()
            try:
                (project / "NOTICE").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation is unavailable.")
            self.assert_rejected(run_build(project), "Distribution build: PASS")

    def test_license_path_07_builder_rejects_parent_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_distribution_project(temp)
            path = project / "release/distribution-files.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["files"] = sorted("../NOTICE" if item == "NOTICE" else item for item in config["files"])
            path.write_bytes(canonical_json_bytes(config))
            self.assert_rejected(run_build(project), "Distribution build: PASS")

    def test_license_path_08_builder_rejects_hidden_notice_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            project = make_distribution_project(temp)
            path = project / "release/distribution-files.json"
            config = json.loads(path.read_text(encoding="utf-8"))
            config["files"] = sorted(".NOTICE" if item == "NOTICE" else item for item in config["files"])
            path.write_bytes(canonical_json_bytes(config))
            self.assert_rejected(run_build(project), "Distribution build: PASS")


class VersionAndScopeContractTests(AttributionTestCase):
    def mutate_plugin_version(self, temp: str, version: str) -> subprocess.CompletedProcess[str]:
        repo = make_plugin_repo(temp)
        path = repo / "plugins/agentic-change-audit/.codex-plugin/plugin.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["version"] = version
        path.write_bytes(canonical_json_bytes(manifest))
        return run_plugin_validator(repo)

    def test_version_scope_01_exact_dev2_plugin_is_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            result = run_plugin_validator(make_plugin_repo(temp))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_version_scope_02_dev1_plugin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assert_rejected(
                self.mutate_plugin_version(temp, "0.1.0-dev.1"),
                "Codex Plugin validation: PASS",
            )

    def test_version_scope_03_dev3_plugin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assert_rejected(
                self.mutate_plugin_version(temp, "0.1.0-dev.3"),
                "Codex Plugin validation: PASS",
            )

    def test_version_scope_04_stable_plugin_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assert_rejected(
                self.mutate_plugin_version(temp, "0.1.0"),
                "Codex Plugin validation: PASS",
            )

    def test_version_scope_05_skill_version_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = make_skill_repo(temp)
            path = repo / "SKILL.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    'version: "0.1.0"', 'version: "0.1.1"', 1
                ),
                encoding="utf-8",
            )
            self.assert_rejected(run_skill_validator(repo), "Skill validation: PASS")

    def test_version_scope_06_prohibited_identity_files_match_base(self):
        for relative in (
            ".agents/plugins/marketplace.json",
            "submission/codex-plugin/listing.json",
            "submission/codex-plugin/starter-prompts.json",
        ):
            result = subprocess.run(
                ["git", "show", f"{BASE_SHA}:{relative}"],
                cwd=ROOT,
                capture_output=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr.decode("utf-8"))
            self.assertEqual(result.stdout, (ROOT / relative).read_bytes(), relative)


if __name__ == "__main__":
    unittest.main()
