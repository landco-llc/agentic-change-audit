"""Exercise fixed-source portable packaging without producing a release artifact."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
TOOL = "scripts/package-submission-plugin.py"
PLUGIN = "plugins/agentic-change-audit"
MIRROR = f"{PLUGIN}/skills/agentic-change-audit"
PORTABLE = "submission/codex-plugin/portable/plugin.json"
LISTING = "submission/codex-plugin/listing.json"
COMPATIBILITY = f"{PLUGIN}/.codex-plugin/plugin.json"
ZIP = "agentic-change-audit-plugin-0.1.0-rc.1.zip"
MANIFEST = "agentic-change-audit-plugin-0.1.0-rc.1.manifest.json"
SUMS = "agentic-change-audit-plugin-0.1.0-rc.1.SHA256SUMS"
SKILL_FILES = """
LICENSE
NOTICE
README.ja.md
README.md
SKILL.md
docs/legal-attribution.md
docs/product-definition.ja.md
docs/product-definition.md
guides/en/installation.md
guides/ja/installation.md
guides/zh-Hant/installation.md
standard/audit-invalidation.ja.md
standard/audit-invalidation.md
standard/change-audit-standard.ja.md
standard/change-audit-standard.md
standard/evidence-requirements.ja.md
standard/evidence-requirements.md
standard/human-check-boundary.ja.md
standard/human-check-boundary.md
standard/output-schema.json
standard/verdict-criteria.ja.md
standard/verdict-criteria.md
templates/audit-result.json
templates/audit-result.md
templates/focused-reaudit-result.md
""".split()
EXPECTED_FILES = {
    "agentic-change-audit/plugin.json": PORTABLE,
    "agentic-change-audit/NOTICE": f"{PLUGIN}/NOTICE",
    **{f"agentic-change-audit/skills/agentic-change-audit/{path}": f"{MIRROR}/{path}"
       for path in SKILL_FILES},
}
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(source: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=source, text=True, check=True, capture_output=True, env=ENV,
    ).stdout.strip()


def commit(source: Path) -> str:
    git(source, "add", "--all")
    git(source, "-c", "user.name=Portable Package Test", "-c",
        "user.email=package-test@example.invalid", "commit", "--no-gpg-sign", "-qm", "Fixture source")
    return git(source, "rev-parse", "HEAD")


def modify_json(path: Path, update) -> None:
    data = json.loads(path.read_bytes())
    update(data)
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")


def load_tool():
    spec = importlib.util.spec_from_file_location("package_submission_plugin_fixture", ROOT / TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PortableSubmissionDistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(workspace.cleanup)
        cls.fixed = Path(workspace.name) / "fixed"
        cls.fixed.mkdir()
        for relative in {TOOL, COMPATIBILITY, LISTING, "submission/codex-plugin/availability.json",
                         *EXPECTED_FILES.values(), *SKILL_FILES}:
            target = cls.fixed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())
        git(cls.fixed, "init", "--quiet", "--object-format=sha1")
        cls.source_ref = commit(cls.fixed)
        cls.tree = git(cls.fixed, "rev-parse", "HEAD^{tree}")

    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.private = Path(workspace.name)
        self.source = self.private / "repo"
        shutil.copytree(self.fixed, self.source)
        self.output = self.private / "output"

    def run_tool(self, command, *, source_ref=None, output=None, cwd=None, env=None):
        args = [sys.executable, "-B", str(self.source / TOOL), command, "--source-ref",
                self.source_ref if source_ref is None else source_ref]
        if command != "check-source":
            args += ["--output-dir", str(self.output if output is None else output)]
        return subprocess.run(args, cwd=self.source if cwd is None else cwd,
                              env=ENV if env is None else env, text=True, capture_output=True)

    def assert_passes(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(": PASS", result.stdout)

    def assert_fails(self, result, message=""):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ERROR:", result.stderr)
        self.assertIn(message, result.stderr)
        self.assertNotIn(": PASS", result.stdout)

    def amend_fixture(self):
        return commit(self.source)

    def test_source_check_materializes_nothing_and_reports_exact_tree(self):
        result = self.run_tool("check-source")
        self.assert_passes(result)
        self.assertIn(f"({self.source_ref}, tree {self.tree})", result.stdout)
        self.assertEqual(set(self.private.iterdir()), {self.source})
        self.assertEqual(git(self.source, "status", "--porcelain"), "")

    def test_repeat_outputs_and_independent_nonextracting_member_readback(self):
        alternate = self.private / "repeat"
        self.assert_passes(self.run_tool("build"))
        self.assert_passes(self.run_tool("build", output=alternate))
        self.assert_passes(self.run_tool("verify"))
        self.assert_passes(self.run_tool("verify", output=alternate))
        outputs = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.assertEqual(set(outputs), {ZIP, MANIFEST, SUMS})
        self.assertEqual(outputs, {path.name: path.read_bytes() for path in alternate.iterdir()})

        receipt = json.loads(outputs[MANIFEST])
        self.assertEqual(set(receipt), {
            "format_version", "package_name", "plugin_version", "skill_version",
            "source_repository", "source_commit", "source_tree", "zip_sha256", "members",
        })
        self.assertEqual(receipt["format_version"], 1)
        self.assertEqual(receipt["package_name"], "agentic-change-audit")
        self.assertEqual(receipt["plugin_version"], "0.1.0-rc.1")
        self.assertEqual(receipt["skill_version"], "0.1.0")
        self.assertEqual(receipt["source_repository"], "https://github.com/landco-llc/agentic-change-audit")
        self.assertEqual(receipt["source_commit"], self.source_ref)
        self.assertEqual(receipt["source_tree"], self.tree)
        self.assertEqual(receipt["zip_sha256"], sha256(outputs[ZIP]))
        self.assertEqual(outputs[SUMS].decode("ascii"), (
            f"{sha256(outputs[ZIP])}  {ZIP}\n{sha256(outputs[MANIFEST])}  {MANIFEST}\n"
        ))

        records = []
        with zipfile.ZipFile(io.BytesIO(outputs[ZIP])) as archive:
            self.assertEqual(archive.namelist(), sorted(EXPECTED_FILES))
            self.assertEqual(len(archive.infolist()), 27)
            self.assertEqual(archive.comment, b"")
            for member in archive.infolist():
                self.assertEqual(member.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(member.create_system, 3)
                self.assertEqual(member.external_attr >> 16, stat.S_IFREG | 0o644)
                self.assertEqual(member.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(member.flag_bits, 0)
                self.assertEqual(member.extra, b"")
                self.assertEqual(member.comment, b"")
                data = archive.read(member)
                self.assertEqual(data, (ROOT / EXPECTED_FILES[member.filename]).read_bytes())
                records.append({"path": member.filename, "size": len(data), "sha256": sha256(data)})
        self.assertEqual(receipt["members"], records)
        for path in SKILL_FILES:
            self.assertEqual((self.source / path).read_bytes(), (self.source / MIRROR / path).read_bytes())

    def test_portable_metadata_has_exact_openai_mapping_and_canonical_prompts(self):
        source = json.loads((self.source / PORTABLE).read_bytes())
        listing = json.loads((self.source / LISTING).read_bytes())
        codex = json.loads((self.source / COMPATIBILITY).read_bytes())
        self.assertEqual(source["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(set(source["extensions"]), {"com.openai"})
        self.assertEqual(set(source["extensions"]["com.openai"]), {"interface"})
        interface = source["extensions"]["com.openai"]["interface"]
        self.assertEqual(interface["defaultPrompt"], codex["interface"]["defaultPrompt"])
        self.assertTrue(all(prompt.isascii() and len(prompt) <= 128
                            for prompt in interface["defaultPrompt"]))
        self.assertEqual(interface["shortDescription"], "Evidence-first change audits")
        self.assertEqual(interface["longDescription"], listing["longDescription"])
        self.assertEqual(interface["websiteURL"], listing["websiteUrl"])
        self.assertEqual(interface["supportURL"], listing["supportUrl"])
        self.assertEqual(interface["privacyPolicyURL"], listing["privacyUrl"])
        self.assertEqual(interface["capabilities"], ["Read"])
        self.assertNotIn("skills", source)
        self.assertNotIn("termsURL", interface)

    def test_rejects_wrong_ref_root_and_inherited_git_overrides(self):
        for invalid in ("HEAD", self.source_ref[:12], self.source_ref.upper(), "0" * 40, self.tree):
            with self.subTest(ref=invalid):
                self.assert_fails(self.run_tool("build", source_ref=invalid), "Source ref")
        self.assert_fails(self.run_tool("check-source", cwd=self.source / "scripts"), "repository root")
        env = dict(ENV, GIT_DIR="/nonexistent", GIT_INDEX_FILE="/nonexistent")
        self.assert_passes(self.run_tool("check-source", env=env))
        self.assertFalse(self.output.exists())

    def test_rejects_dirty_and_staged_inputs_even_when_git_hides_them(self):
        value = self.source / PORTABLE
        value.write_bytes(value.read_bytes() + b"\n")
        git(self.source, "update-index", "--assume-unchanged", PORTABLE)
        self.assert_fails(self.run_tool("build"), "Working source differs")
        git(self.source, "update-index", "--no-assume-unchanged", PORTABLE)
        git(self.source, "add", PORTABLE)
        self.assert_fails(self.run_tool("build"), "index differs")
        self.assertFalse(self.output.exists())

    def test_rejects_untracked_ignored_bytes_and_case_aliases(self):
        hidden = self.source / MIRROR / "readme.md"
        hidden.write_text("Fixture", encoding="utf-8")
        exclude = self.source / ".git/info/exclude"
        exclude.write_text("readme.md\n", encoding="utf-8")
        self.assert_fails(self.run_tool("build"), "untracked files")
        exclude.unlink()
        new_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=new_ref), "source paths collide")
        self.assertFalse(self.output.exists())

    def test_rejects_git_symlink_executable_and_extra_skill_member(self):
        target = self.source / PORTABLE
        original = target.read_bytes()
        target.unlink()
        target.symlink_to("../listing.json")
        symlink_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=symlink_ref), "nonregular entry")
        target.unlink()
        target.write_bytes(original)
        target.chmod(0o755)
        mode_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=mode_ref), "nonexecutable blobs")
        target.chmod(0o644)
        (self.source / MIRROR / "EXTRA.md").write_text("Fixture", encoding="utf-8")
        extra_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=extra_ref), "exact package membership")
        self.assertFalse(self.output.exists())

    def test_rejects_missing_mirror_member_mismatch_and_skill_version_drift(self):
        mirror = self.source / MIRROR / "SKILL.md"
        canonical = self.source / "SKILL.md"
        original = mirror.read_bytes()
        mirror.unlink()
        missing_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=missing_ref), "Required package inputs")
        mirror.write_bytes(original + b"\n")
        mismatch_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=mismatch_ref), "match byte-for-byte")
        for path in (mirror, canonical):
            path.write_bytes(original.replace(b'"0.1.0"', b'"0.1.0-rc.1"'))
        version_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("build", source_ref=version_ref), "independent version")
        self.assertFalse(self.output.exists())

    def test_rejects_duplicate_or_forbidden_metadata_and_bad_versions(self):
        path = self.source / PORTABLE
        original = path.read_bytes()
        bad_values = (
            b'\xff',
            original.replace(b'  "version":', b'  "version": "0.1.0-rc.1",\n  "version":'),
            original.replace(b'"0.1.0-rc.1"', b'"0.1.0-dev.3"'),
            original.replace(b'"0.1.0-rc.1"', b'"0.1.0"'),
            original.replace(b'"0.1.0-rc.1"', b'"0.1.0-rc.10"'),
            original.replace(b'"Read"', b'"Write"'),
            original.replace(b'"extensions":', b'"skills": "./skills/",\n  "extensions":'),
            original.replace(b'"com.openai":', b'"com.example":'),
            original.replace(b'"interface":', b'"publication": {},\n      "interface":'),
            original.replace(b'https://github.com/', b'https://example.invalid/'),
        )
        for index, data in enumerate(bad_values):
            with self.subTest(case=index):
                path.write_bytes(data)
                fixture_ref = self.amend_fixture()
                self.assert_fails(self.run_tool("build", source_ref=fixture_ref))
        self.assertFalse(self.output.exists())

    def test_rejects_coupled_prompt_or_version_changes_and_modified_availability(self):
        source = self.source
        listing = source / LISTING
        manifest = source / PORTABLE
        codex = source / COMPATIBILITY
        listing_before, manifest_before, codex_before = (
            path.read_bytes() for path in (listing, manifest, codex)
        )
        for path, content in ((listing, listing_before), (manifest, manifest_before), (codex, codex_before)):
            path.write_bytes(content.replace(b"0.1.0-rc.1", b"0.1.0"))
        bad_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("check-source", source_ref=bad_ref))
        listing.write_bytes(listing_before)
        modify_json(codex, lambda value: value["interface"]["defaultPrompt"].append("Another prompt"))
        modify_json(manifest, lambda value:
                    value["extensions"]["com.openai"]["interface"]["defaultPrompt"].append("Another prompt"))
        bad_ref = self.amend_fixture()
        self.assert_fails(self.run_tool("check-source", source_ref=bad_ref))
        manifest.write_bytes(manifest_before)
        codex.write_bytes(codex_before)
        changed = source / "submission/codex-plugin/availability.json"
        changed.write_bytes(changed.read_bytes() + b"\n")
        self.assert_fails(self.run_tool("check-source", source_ref=self.amend_fixture()), "Availability")

    def test_rejects_missing_corrupt_and_cross_family_outputs_and_tampered_receipts(self):
        self.assert_fails(self.run_tool("verify"))
        self.assert_passes(self.run_tool("build"))
        path = self.output / ZIP
        original = path.read_bytes()
        variants = [b"", original[:-1], original[:32] + bytes([original[32] ^ 1]) + original[33:]]
        runtime = io.BytesIO()
        with zipfile.ZipFile(runtime, "w") as archive:
            archive.writestr("agentic-change-audit/SKILL.md", "Runtime fixture.")
            archive.writestr("agentic-change-audit/PACKAGE-MANIFEST.json", "{}")
        variants.append(runtime.getvalue())
        for index, data in enumerate(variants):
            with self.subTest(case=index):
                path.write_bytes(data)
                self.assert_fails(self.run_tool("verify"))
        path.write_bytes(original)
        receipt_path = self.output / MANIFEST
        receipt = json.loads(receipt_path.read_bytes())
        receipt["source_tree"] = "0" * 40
        receipt_bytes = (json.dumps(receipt, indent=2) + "\n").encode()
        receipt_path.write_bytes(receipt_bytes)
        (self.output / SUMS).write_text(
            f"{sha256(original)}  {ZIP}\n{sha256(receipt_bytes)}  {MANIFEST}\n", encoding="ascii"
        )
        self.assert_fails(self.run_tool("verify"), "Output differs")
        receipt_path.unlink()
        self.assert_fails(self.run_tool("verify"), "exactly three package files")

    def test_rejects_noncanonical_archives_without_using_member_paths(self):
        self.assert_passes(self.run_tool("build"))
        path = self.output / ZIP
        with zipfile.ZipFile(path) as original:
            members = [(item, original.read(item)) for item in original.infolist()]
        names = [
            "../NOTICE", "/NOTICE", "agentic-change-audit/../NOTICE",
            "agentic-change-audit//NOTICE", "agentic-change-audit/./NOTICE",
            "agentic-change-audit/ NOTICE", "agentic-change-audit\\NOTICE",
            "agentic-change-audit/notice", "agentic-change-audit/ＮＯＴＩＣＥ",
            "agentic-change-audit/NOTICE/fixture", "other-root/NOTICE",
            "agentic-change-audit/NOTICE",
        ]
        for name in names:
            with self.subTest(member=name):
                with zipfile.ZipFile(path, "w") as archive:
                    item = zipfile.ZipInfo(name)
                    if name == "agentic-change-audit/NOTICE":
                        archive.writestr(*members[0])
                    archive.writestr(item, b"X")
                self.assert_fails(self.run_tool("verify"))
        for mode in (stat.S_IFLNK | 0o777, stat.S_IFDIR | 0o755, stat.S_IFREG | 0o755):
            with self.subTest(mode=mode):
                with zipfile.ZipFile(path, "w") as archive:
                    for member, data in members:
                        if member.filename.endswith("/plugin.json"):
                            member.external_attr = mode << 16
                        archive.writestr(member, data)
                self.assert_fails(self.run_tool("verify"))
        self.assertEqual(set(self.private.iterdir()), {self.source, self.output})

    def test_rejects_existing_symlink_linked_or_nonregular_outputs(self):
        self.output.mkdir(mode=0o700)
        self.assert_fails(self.run_tool("build"))
        self.assertEqual(list(self.output.iterdir()), [])
        self.output.rmdir()
        victim = self.private / "untouched"
        victim.mkdir(mode=0o700)
        self.output.symlink_to(victim, target_is_directory=True)
        self.assert_fails(self.run_tool("build"))
        self.assert_fails(self.run_tool("verify"))
        via_link = self.private / "alias"
        via_link.symlink_to(victim, target_is_directory=True)
        self.assert_fails(self.run_tool("build", output=via_link / "target"))
        self.assertEqual(list(victim.iterdir()), [])
        self.output.unlink()
        self.assert_passes(self.run_tool("build"))
        out_zip = self.output / ZIP
        external = victim / "same-bytes"
        out_zip.rename(external)
        out_zip.symlink_to(external)
        self.assert_fails(self.run_tool("verify"))
        out_zip.unlink()
        os.link(external, out_zip)
        self.assert_fails(self.run_tool("verify"), "regular file")
        out_zip.unlink()
        os.mkfifo(out_zip)
        self.assert_fails(self.run_tool("verify"), "regular file")

    def test_size_and_entry_bounds_and_failure_cleanup(self):
        tool = load_tool()
        members = tuple((name, b"x") for name in sorted(EXPECTED_FILES))
        with self.assertRaisesRegex(tool.PackageError, "entry count"):
            tool.check_members(members * 186)
        with self.assertRaisesRegex(tool.PackageError, "entry count"):
            tool.check_members(members[:-1])
        with patch.object(tool, "MAX_EXPANDED_BYTES", 2):
            with self.assertRaisesRegex(tool.PackageError, "Expanded package"):
                tool.check_members(members)
        with patch.object(tool, "MAX_ENTRY_BYTES", 0):
            with self.assertRaisesRegex(tool.PackageError, "member exceeds"):
                tool.check_members(members)
        with patch.object(tool, "MAX_ZIP_BYTES", 40):
            with self.assertRaisesRegex(tool.PackageError, "ZIP exceeds"):
                tool.canonical_outputs(tool.Source(self.source_ref, self.tree, members))
        self.assert_passes(self.run_tool("build"))
        with (self.output / ZIP).open("ab") as archive:
            archive.truncate(100_000_001)
        self.assert_fails(self.run_tool("verify"), "bounded size")

        with tool.directory(None, self.private.parts[1:]) as parent_fd:
            with patch.object(tool, "check_outputs", side_effect=OSError("Fixture write failure")):
                with self.assertRaises(OSError):
                    tool.build_outputs(parent_fd, "failed-output", {"example": b"fixture"})
        self.assertFalse((self.private / "failed-output").exists())


if __name__ == "__main__":
    unittest.main()
