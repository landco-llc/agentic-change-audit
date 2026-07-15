from __future__ import annotations

import importlib.util
import json
import os
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


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class PluginManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json(MANIFEST_PATH)

    def test_plugin_manifest_contract(self):
        self.assertEqual("agentic-change-audit", self.manifest["name"])
        self.assertEqual("0.1.0-dev.1", self.manifest["version"])
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
        self.assertEqual(23, len(sources))
        problems = sync_module.check_mirror(ROOT, SKILL_ROOT, sources)
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
        result = subprocess.run(
            [PYTHON, str(VALIDATE_PLUGIN_SCRIPT), "--root", str(ROOT)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class SyncScriptMutationTests(unittest.TestCase):
    def make_temp_plugin_root(self, temp: str) -> Path:
        plugin_root = Path(temp) / "plugins" / "agentic-change-audit"
        skill_root = plugin_root / "skills" / "agentic-change-audit"
        sources = sync_module.load_source_list(ROOT)
        sync_module.write_mirror(ROOT, skill_root, sources)
        return plugin_root

    def test_sync_check_detects_changed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.make_temp_plugin_root(temp)
            skill_root = plugin_root / "skills" / "agentic-change-audit"
            sources = sync_module.load_source_list(ROOT)

            target = skill_root / "SKILL.md"
            target.write_bytes(target.read_bytes() + b"\ntampered\n")

            problems = sync_module.check_mirror(ROOT, skill_root, sources)
            self.assertIn("changed: SKILL.md", problems)

    def test_sync_check_detects_extra_file(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.make_temp_plugin_root(temp)
            skill_root = plugin_root / "skills" / "agentic-change-audit"
            sources = sync_module.load_source_list(ROOT)

            extra = skill_root / "EXTRA_UNEXPECTED.md"
            extra.write_text("unexpected\n", encoding="utf-8")

            problems = sync_module.check_mirror(ROOT, skill_root, sources)
            self.assertIn("extra: EXTRA_UNEXPECTED.md", problems)

    def test_sync_write_repairs_changed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.make_temp_plugin_root(temp)
            skill_root = plugin_root / "skills" / "agentic-change-audit"
            sources = sync_module.load_source_list(ROOT)

            target = skill_root / "SKILL.md"
            target.write_bytes(target.read_bytes() + b"\ntampered\n")
            self.assertNotEqual([], sync_module.check_mirror(ROOT, skill_root, sources))

            sync_module.write_mirror(ROOT, skill_root, sources)
            self.assertEqual([], sync_module.check_mirror(ROOT, skill_root, sources))

    def test_sync_write_removes_stale_file(self):
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.make_temp_plugin_root(temp)
            skill_root = plugin_root / "skills" / "agentic-change-audit"
            sources = sync_module.load_source_list(ROOT)

            extra = skill_root / "EXTRA_UNEXPECTED.md"
            extra.write_text("unexpected\n", encoding="utf-8")
            self.assertNotEqual([], sync_module.check_mirror(ROOT, skill_root, sources))

            sync_module.write_mirror(ROOT, skill_root, sources)
            self.assertFalse(extra.exists())
            self.assertEqual([], sync_module.check_mirror(ROOT, skill_root, sources))


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
