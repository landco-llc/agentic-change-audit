from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

MANIFEST_PATH = ROOT / "plugins/agentic-change-audit/.codex-plugin/plugin.json"
MARKETPLACE_PATH = ROOT / ".agents/plugins/marketplace.json"
PLUGIN_ROOT = ROOT / "plugins/agentic-change-audit"
SKILL_ROOT = PLUGIN_ROOT / "skills/agentic-change-audit"
SYNC_SCRIPT = ROOT / "scripts/sync-codex-plugin.py"
VALIDATE_PLUGIN_SCRIPT = ROOT / "scripts/validate-codex-plugin.py"
VALIDATE_SKILL_SCRIPT = ROOT / "scripts/validate-skill.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync_module = load_module("sync_codex_plugin", SYNC_SCRIPT)
validate_module = load_module("validate_codex_plugin", VALIDATE_PLUGIN_SCRIPT)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_source_repo(temp: str) -> Path:
    """Build an isolated repository containing only the 25 canonical Skill
    sources plus their distribution config, sufficient for sync script tests.
    """
    root = Path(temp) / "repo"
    root.mkdir()

    config_dest = root / sync_module.CONFIG_RELATIVE
    config_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / sync_module.CONFIG_RELATIVE, config_dest)

    sources = sync_module.load_source_list(ROOT)
    for relative in sources:
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, dst)

    return root


def build_plugin_repo(temp: str) -> Path:
    """Build a full isolated Plugin repository: canonical sources, a
    populated Skill mirror, the manifest, marketplace, READMEs, and the two
    scripts validate-codex-plugin.py invokes via subprocess.
    """
    root = build_source_repo(temp)

    for script_relative in (
        validate_module.SKILL_VALIDATOR_RELATIVE,
        validate_module.SYNC_SCRIPT_RELATIVE,
    ):
        dst = root / script_relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / script_relative, dst)

    marketplace_dest = root / validate_module.MARKETPLACE_RELATIVE
    marketplace_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MARKETPLACE_PATH, marketplace_dest)

    manifest_dest = root / validate_module.MANIFEST_RELATIVE
    manifest_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MANIFEST_PATH, manifest_dest)

    for name in validate_module.README_NAMES:
        dest = root / validate_module.PLUGIN_RELATIVE / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PLUGIN_ROOT / name, dest)

    sync_module.write_mirror(root, sync_module.load_source_list(root))
    sync_module.write_plugin_notice(root)
    return root


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(VALIDATE_PLUGIN_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
    )


def mutate_manifest(root: Path, mutator) -> None:
    manifest_path = root / validate_module.MANIFEST_RELATIVE
    manifest = load_json(manifest_path)
    mutator(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


class PluginManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(MANIFEST_PATH)

    def test_plugin_manifest_contract(self):
        self.assertEqual("agentic-change-audit", self.manifest["name"])
        self.assertEqual("0.1.0-dev.2", self.manifest["version"])
        self.assertEqual("Apache-2.0", self.manifest["license"])
        self.assertEqual("./skills/", self.manifest["skills"])
        self.assertEqual(["Read"], self.manifest["interface"]["capabilities"])
        self.assertTrue(self.manifest["author"]["name"])
        self.assertTrue(self.manifest["author"]["url"])
        self.assertTrue(self.manifest["homepage"])
        self.assertTrue(self.manifest["repository"])
        self.assertIsInstance(self.manifest["keywords"], list)
        self.assertGreater(len(self.manifest["keywords"]), 0)
        self.assertIsInstance(self.manifest["interface"]["defaultPrompt"], list)
        self.assertGreater(len(self.manifest["interface"]["defaultPrompt"]), 0)

    def test_plugin_manifest_has_no_stateful_components(self):
        serialized = json.dumps(self.manifest)
        for forbidden in ("mcpServers", "apps", "hooks"):
            self.assertNotIn(f'"{forbidden}"', serialized)
        for visual in ("icon", "icons", "logo", "logoUrl", "assets", "screenshots", "banner"):
            self.assertNotIn(f'"{visual}"', serialized)

        codex_plugin_dir = MANIFEST_PATH.parent
        entries = sorted(entry.name for entry in codex_plugin_dir.iterdir())
        self.assertEqual(["plugin.json"], entries)


class MarketplaceTests(unittest.TestCase):
    def test_marketplace_contract(self):
        marketplace = load_json(MARKETPLACE_PATH)
        self.assertEqual("landco-llc-open-source", marketplace["name"])
        self.assertEqual(
            "L&Co.LLC Open Source", marketplace["interface"]["displayName"]
        )
        self.assertEqual(1, len(marketplace["plugins"]))

        entry = marketplace["plugins"][0]
        self.assertEqual("agentic-change-audit", entry["name"])
        self.assertEqual("local", entry["source"]["source"])
        self.assertEqual("./plugins/agentic-change-audit", entry["source"]["path"])
        self.assertEqual("AVAILABLE", entry["policy"]["installation"])
        self.assertEqual("ON_INSTALL", entry["policy"]["authentication"])
        self.assertEqual("Productivity", entry["category"])


class PluginSkillMirrorTests(unittest.TestCase):
    def test_plugin_skill_mirror_is_exact(self):
        sources = sync_module.load_source_list(ROOT)
        self.assertEqual(25, len(sources))
        problems = sync_module.check_mirror(ROOT, sources)
        self.assertEqual([], problems)

    def test_plugin_skill_validator_passes(self):
        result = subprocess.run(
            [
                PYTHON,
                str(VALIDATE_SKILL_SCRIPT),
                str(SKILL_ROOT),
                "--expected-name",
                "agentic-change-audit",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class PluginValidatorTests(unittest.TestCase):
    def test_plugin_validator_passes(self):
        result = run_validator(ROOT)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class SyncScriptMutationTests(unittest.TestCase):
    def test_sync_check_detects_changed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            sources = sync_module.load_source_list(root)
            sync_module.write_mirror(root, sources)

            target = root / sync_module.PLUGIN_SKILL_RELATIVE / "SKILL.md"
            target.write_bytes(target.read_bytes() + b"\ntampered\n")

            problems = sync_module.check_mirror(root, sources)
            self.assertIn("changed: SKILL.md", problems)

    def test_sync_check_detects_extra_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            sources = sync_module.load_source_list(root)
            sync_module.write_mirror(root, sources)

            extra = root / sync_module.PLUGIN_SKILL_RELATIVE / "EXTRA_UNEXPECTED.md"
            extra.write_text("unexpected\n", encoding="utf-8")

            problems = sync_module.check_mirror(root, sources)
            self.assertIn("extra: EXTRA_UNEXPECTED.md", problems)

    def test_sync_write_repairs_changed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            sources = sync_module.load_source_list(root)
            sync_module.write_mirror(root, sources)

            target = root / sync_module.PLUGIN_SKILL_RELATIVE / "SKILL.md"
            target.write_bytes(target.read_bytes() + b"\ntampered\n")
            self.assertNotEqual([], sync_module.check_mirror(root, sources))

            sync_module.write_mirror(root, sources)
            self.assertEqual([], sync_module.check_mirror(root, sources))

    def test_sync_write_removes_stale_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            sources = sync_module.load_source_list(root)
            sync_module.write_mirror(root, sources)

            extra = root / sync_module.PLUGIN_SKILL_RELATIVE / "EXTRA_UNEXPECTED.md"
            extra.write_text("unexpected\n", encoding="utf-8")
            self.assertNotEqual([], sync_module.check_mirror(root, sources))

            sync_module.write_mirror(root, sources)
            self.assertFalse(extra.exists())
            self.assertEqual([], sync_module.check_mirror(root, sources))


class SyncBoundaryNegativeTests(unittest.TestCase):
    """Regression coverage for the PR #7 audit's Finding A (unsafe sync destination)."""

    def make_symlinked_skill_root(self, temp: str, root: Path) -> tuple[Path, Path]:
        sources = sync_module.load_source_list(root)
        sync_module.write_mirror(root, sources)
        skill_root = root / sync_module.PLUGIN_SKILL_RELATIVE

        decoy = Path(temp) / "decoy-target"
        decoy.mkdir()
        sentinel = decoy / "SENTINEL.txt"
        sentinel.write_text("decoy target sentinel\n", encoding="utf-8")

        shutil.rmtree(skill_root)
        try:
            skill_root.symlink_to(decoy, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation is unavailable on this platform.")

        return skill_root, sentinel

    def test_sync_cli_rejects_plugin_root_override(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            result = subprocess.run(
                [
                    PYTHON,
                    str(SYNC_SCRIPT),
                    "--check",
                    "--root",
                    str(root),
                    "--plugin-root",
                    str(Path(temp) / "elsewhere"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("--plugin-root", result.stderr)

    def test_sync_check_rejects_skill_root_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            skill_root, sentinel = self.make_symlinked_skill_root(temp, root)
            sources = sync_module.load_source_list(root)

            with self.assertRaises(ValueError) as ctx:
                sync_module.check_mirror(root, sources)
            self.assertIn("symlink", str(ctx.exception).lower())
            self.assertTrue(skill_root.is_symlink())
            self.assertEqual("decoy target sentinel\n", sentinel.read_text(encoding="utf-8"))

    def test_sync_write_rejects_skill_root_symlink_without_deleting_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            skill_root, sentinel = self.make_symlinked_skill_root(temp, root)
            sources = sync_module.load_source_list(root)

            with self.assertRaises(ValueError) as ctx:
                sync_module.write_mirror(root, sources)
            self.assertIn("symlink", str(ctx.exception).lower())
            self.assertTrue(skill_root.is_symlink())
            self.assertEqual("decoy target sentinel\n", sentinel.read_text(encoding="utf-8"))
            self.assertEqual(
                ["SENTINEL.txt"],
                sorted(p.name for p in sentinel.parent.iterdir()),
            )

    def test_sync_write_cannot_target_decoy_plugin_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_source_repo(temp)
            decoy_skill_root = (
                root / "plugins" / "decoy-plugin" / "skills" / "agentic-change-audit"
            )
            decoy_skill_root.mkdir(parents=True)
            sentinel = decoy_skill_root / "SENTINEL.txt"
            sentinel.write_text("decoy sentinel\n", encoding="utf-8")

            result = subprocess.run(
                [
                    PYTHON,
                    str(SYNC_SCRIPT),
                    "--write",
                    "--root",
                    str(root),
                    "--plugin-root",
                    str(root / "plugins" / "decoy-plugin"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("--plugin-root", result.stderr)
            self.assertEqual("decoy sentinel\n", sentinel.read_text(encoding="utf-8"))
            self.assertEqual(
                ["SENTINEL.txt"],
                sorted(p.name for p in decoy_skill_root.iterdir()),
            )
            self.assertFalse(
                (root / sync_module.PLUGIN_SKILL_RELATIVE).exists()
            )


class PluginValidatorNegativeTests(unittest.TestCase):
    """Regression coverage for the PR #7 audit's Finding B (validator false PASS)."""

    def test_plugin_validator_rejects_wrong_author_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(root, lambda m: m["author"].__setitem__("name", "Wrong Publisher"))
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("author.name", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_author_url(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(root, lambda m: m["author"].__setitem__("url", "https://example.invalid"))
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("author.url", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_homepage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(root, lambda m: m.__setitem__("homepage", "https://example.invalid"))
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("homepage", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(root, lambda m: m.__setitem__("repository", "https://example.invalid"))
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("repository", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_category(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(
                root, lambda m: m["interface"].__setitem__("category", "Wrong Category")
            )
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("interface.category", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_interface_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(
                root, lambda m: m["interface"].__setitem__("displayName", "Wrong Display Name")
            )
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("interface.displayName", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_keywords(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(root, lambda m: m.__setitem__("keywords", ["wrong-keyword"]))
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("keywords", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_wrong_default_prompts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(
                root,
                lambda m: m["interface"].__setitem__("defaultPrompt", ["Do something else."]),
            )
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("interface.defaultPrompt", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_unexpected_manifest_key(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            mutate_manifest(root, lambda m: m.__setitem__("extraField", "unexpected"))
            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("top-level", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_nested_mcp_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            nested = root / validate_module.PLUGIN_RELATIVE / "nested"
            nested.mkdir(parents=True, exist_ok=True)
            (nested / ".mcp.json").write_text("{}\n", encoding="utf-8")

            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(".mcp.json", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_nested_app_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            nested = root / validate_module.PLUGIN_RELATIVE / "docs" / "nested"
            nested.mkdir(parents=True, exist_ok=True)
            (nested / ".app.json").write_text("{}\n", encoding="utf-8")

            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn(".app.json", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_nested_hooks_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            nested_hooks = root / validate_module.PLUGIN_RELATIVE / "nested" / "hooks"
            nested_hooks.mkdir(parents=True, exist_ok=True)
            (nested_hooks / "pre-audit.json").write_text("{}\n", encoding="utf-8")

            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("hooks", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_unexpected_plugin_top_level_entry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)
            extra = root / validate_module.PLUGIN_RELATIVE / "EXTRA_TOP_LEVEL.md"
            extra.write_text("unexpected\n", encoding="utf-8")

            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("top-level entries mismatch", result.stderr)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)

    def test_plugin_validator_rejects_combined_wrong_identity_and_nested_mcp(self):
        """Reproduces the exact PR #7 audit Attack 3 scenario in one document."""
        with tempfile.TemporaryDirectory() as temp:
            root = build_plugin_repo(temp)

            def mutator(manifest):
                manifest["author"]["name"] = "Wrong Publisher"
                manifest["homepage"] = "https://example.invalid/wrong"
                manifest["repository"] = "https://example.invalid/wrong"
                manifest["interface"]["category"] = "Wrong Category"

            mutate_manifest(root, mutator)
            nested = root / validate_module.PLUGIN_RELATIVE / "nested"
            nested.mkdir(parents=True, exist_ok=True)
            (nested / ".mcp.json").write_text("{}\n", encoding="utf-8")

            result = run_validator(root)
            self.assertNotEqual(0, result.returncode)
            self.assertNotIn("Codex Plugin validation: PASS", result.stdout)
            for expected in (
                "author.name",
                "homepage",
                "repository",
                "interface.category",
                ".mcp.json",
            ):
                self.assertIn(expected, result.stderr)


class PluginSecurityBoundaryTests(unittest.TestCase):
    def test_no_symlinks_in_plugin(self):
        found_symlinks: list[str] = []
        for current_dir, dir_names, file_names in os.walk(PLUGIN_ROOT, followlinks=False):
            current = Path(current_dir)
            for name in dir_names + file_names:
                candidate = current / name
                if candidate.is_symlink():
                    found_symlinks.append(str(candidate))
        self.assertEqual([], found_symlinks)

    def test_documentation_mentions_development_boundary(self):
        candidates = [
            ROOT / "README.md",
            ROOT / "README.ja.md",
            ROOT / "guides/en/installation.md",
            ROOT / "guides/ja/installation.md",
            ROOT / "guides/zh-Hant/installation.md",
            PLUGIN_ROOT / "README.md",
            PLUGIN_ROOT / "README.ja.md",
            PLUGIN_ROOT / "README.zh-Hant.md",
        ]
        for path in candidates:
            self.assertTrue(path.is_file(), f"Missing documentation file: {path}")
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                "development",
                text.lower(),
                f"{path} must state the Plugin is a development preview.",
            )


if __name__ == "__main__":
    unittest.main()
