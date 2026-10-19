"""Protect user configuration and verify the host binding contract."""
import json
from pathlib import Path
import re
import sys
import tempfile
import tomllib
import unittest
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from minecode_runtime.installation import SKILLS, configuration, remove_host, setup_host


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minecode installation ")
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)

    def test_both_host_configs_bind_installed_python_and_selected_project(self):
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                content = configuration(host, self.root, [])
                config = tomllib.loads(content) if host == "codex" else json.loads(content)
                server = config["mcp_servers" if host == "codex" else "mcpServers"]["minecode"]
                self.assertEqual(server["command"], str(Path(sys.executable).absolute()))
                self.assertEqual(server["args"], ["-m", "minecode_runtime", "--project", str(self.root)])
                self.assertNotIn("allow-", content)
                if host == "codex":
                    self.assertIs(server["required"], True)
                    self.assertEqual(server["startup_timeout_sec"], 30)
                    self.assertEqual(server["tool_timeout_sec"], 630)
                    self.assertNotIn("mcp_optional_startup_grace_ms", config)

    def test_install_update_remove_leaves_unrelated_files(self):
        installed = setup_host(self.root, "codex", [])
        unrelated = self.root / ".agents" / "skills" / "user.txt"
        unrelated.write_text("user content")
        setup_host(self.root, "codex", ["--allow-execution"])
        config = tomllib.loads((self.root / ".codex" / "config.toml").read_text())
        self.assertIn("--allow-execution", config["mcp_servers"]["minecode"]["args"])
        removed, retained = remove_host(self.root, "codex")
        self.assertEqual(set(removed), set(installed))
        self.assertTrue(all(not (self.root / name).exists() for name in removed))
        self.assertEqual(retained, [])
        self.assertEqual(unrelated.read_text(), "user content")

    def test_existing_config_collision_changes_nothing_and_skills_only_is_available(self):
        config = self.root / ".mcp.json"
        config.write_text('{"mcpServers":{"other":{}}}')
        with self.assertRaisesRegex(ValueError, "Preserving"):
            setup_host(self.root, "claude", [])
        self.assertFalse((self.root / ".claude").exists())
        installed = setup_host(self.root, "claude", [], skills_only=True)
        self.assertEqual(json.loads(config.read_text()), {"mcpServers": {"other": {}}})
        self.assertEqual(set(remove_host(self.root, "claude")[0]), set(installed))
        self.assertTrue(config.exists())

    def test_user_edits_survive_update_and_uninstall(self):
        installed = setup_host(self.root, "codex", [])
        config = self.root / ".codex" / "config.toml"
        config.write_text(config.read_text() + '\n[other]\nvalue = "keep"\n')
        with self.assertRaisesRegex(ValueError, "Preserving"):
            setup_host(self.root, "codex", [])
        removed, retained = remove_host(self.root, "codex")
        self.assertEqual(set(removed), set(installed) - {".codex/config.toml"})
        self.assertEqual(retained, [".codex/config.toml"])
        self.assertIn("keep", config.read_text())

    def test_manifest_cannot_delete_arbitrary_project_file(self):
        setup_host(self.root, "codex", [])
        manifest = self.root / ".minecode" / "installation-codex.json"
        data = json.loads(manifest.read_text())
        data["files"]["../outside.txt"] = "anything"
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Invalid installation manifest"):
            remove_host(self.root, "codex")

    def test_symlink_destination_rejected_before_mutation(self):
        external = self.root / "elsewhere"
        external.mkdir()
        try:
            (self.root / ".agents").symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks is not available to this Windows user")
        with self.assertRaisesRegex(ValueError, "linked installation path"):
            setup_host(self.root, "codex", [])
        self.assertEqual(list(external.iterdir()), [])

    def test_hosts_can_be_removed_independently(self):
        setup_host(self.root, "codex", [])
        setup_host(self.root, "claude", [])
        remove_host(self.root, "codex")
        self.assertTrue((self.root / ".mcp.json").exists())
        self.assertTrue((self.root / ".claude/skills/minecraft-debugger/SKILL.md").exists())

    def test_unicode_project_paths_produce_valid_toml(self):
        root = self.root / "My mod \U0001f30d"
        result = tomllib.loads(configuration("codex", root, []))
        self.assertEqual(result["mcp_servers"]["minecode"]["args"][-1], str(root))

    def test_nonobject_manifest_is_actionable_error(self):
        (self.root / ".minecode").mkdir()
        (self.root / ".minecode/installation-codex.json").write_text("[]")
        with self.assertRaisesRegex(ValueError, "Invalid installation manifest"):
            setup_host(self.root, "codex", [])

    def test_parent_file_collision_is_preflighted(self):
        (self.root / ".codex").write_text("user file")
        with self.assertRaisesRegex(ValueError, "not a directory"):
            setup_host(self.root, "codex", [])
        self.assertFalse((self.root / ".agents").exists())

    def test_three_skill_install_upgrades_to_specialties_for_both_hosts(self):
        legacy = ("minecraft-java-developer", "minecraft-project-inspector", "minecraft-debugger")
        for host, directory in (("codex", ".agents/skills"), ("claude", ".claude/skills")):
            with self.subTest(host=host):
                with patch("minecode_runtime.installation.SKILLS", legacy):
                    old = setup_host(self.root, host, [], skills_only=True)
                unrelated = self.root / directory / "user.md"
                unrelated.write_text("user content")
                installed = setup_host(self.root, host, [], skills_only=True)
                self.assertTrue(set(old) < set(installed))
                for skill in SKILLS:
                    self.assertTrue((self.root / directory / skill / "SKILL.md").is_file())
                    for document in (self.root / directory / skill).rglob('*.md'):
                        for raw in re.findall(r'\[[^\]]*\]\(([^)]+)\)', document.read_text(encoding='utf-8')):
                            parsed = urlsplit(raw)
                            if parsed.scheme or parsed.netloc or not parsed.path:
                                continue
                            target = (document.parent / unquote(parsed.path)).resolve()
                            self.assertTrue(target.is_relative_to(self.root / directory), (skill, raw))
                            self.assertTrue(target.is_file(), (skill, raw))
                removed, retained = remove_host(self.root, host)
                self.assertEqual(set(installed), set(removed))
                self.assertEqual(retained, [])
                self.assertEqual(unrelated.read_text(), "user content")

    def test_new_specialty_collision_preserves_existing_install_before_any_write(self):
        legacy = ("minecraft-java-developer", "minecraft-project-inspector", "minecraft-debugger")
        with patch("minecode_runtime.installation.SKILLS", legacy):
            setup_host(self.root, "codex", [], skills_only=True)
        collision = self.root / ".agents/skills/minecraft-server-developer/SKILL.md"
        collision.parent.mkdir(parents=True)
        collision.write_text("user's existing server skill")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with self.assertRaisesRegex(ValueError, "Preserving existing/modified file"):
            setup_host(self.root, "codex", [], skills_only=True)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_retired_and_renamed_resources_for_both_hosts(self):
        from minecode_runtime.installation import payloads
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                setup_host(self.root, host, [])
                current = payloads(host, self.root, [], False)
                old = next(name for name in current if name.endswith("/references/workflow.md"))
                new = old.replace("workflow.md", "renamed.md")
                future = dict(current)
                future[new] = future.pop(old)
                with patch("minecode_runtime.installation.payloads", return_value=future):
                    setup_host(self.root, host, [])
                    self.assertFalse((self.root / old).exists())
                    self.assertTrue((self.root / new).exists())
                    removed, retained = remove_host(self.root, host)
                    self.assertIn(new, removed)
                    self.assertEqual(retained, [])

    def test_modified_retired_resource_survives_update_and_remove(self):
        from minecode_runtime.installation import payloads
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                setup_host(self.root, host, [])
                future = payloads(host, self.root, [], False)
                old = next(name for name in future if name.endswith("/references/workflow.md"))
                future.pop(old)
                (self.root / old).write_text("user edits", encoding="utf-8")
                with patch("minecode_runtime.installation.payloads", return_value=future):
                    setup_host(self.root, host, [])
                    _, retained = remove_host(self.root, host)
                    self.assertEqual(retained, [old])
                    self.assertEqual((self.root / old).read_text(), "user edits")

    def test_retired_resource_removal_recovers_after_manifest_write_interruption(self):
        from minecode_runtime.installation import payloads, write_manifest
        setup_host(self.root, "codex", [])
        future = payloads("codex", self.root, [], False)
        old = next(name for name in future if name.endswith("/references/workflow.md"))
        future.pop(old)
        def interrupt_after_retirement(root, host, files):
            if old not in files:
                raise OSError("simulated interruption")
            write_manifest(root, host, files)
        with patch("minecode_runtime.installation.payloads", return_value=future):
            with patch("minecode_runtime.installation.write_manifest", side_effect=interrupt_after_retirement):
                with self.assertRaisesRegex(OSError, "simulated"):
                    setup_host(self.root, "codex", [])
            setup_host(self.root, "codex", [])
            self.assertEqual(remove_host(self.root, "codex")[1], [])

    def test_historical_allowlist_rejects_forged_sibling_and_bad_hash(self):
        from minecode_runtime.installation import digest
        for forged in (".agents/skills/minecraft-java-developer/references/private.md",
                       ".agents/skills/minecraft-java-developer/../user.md"):
            with self.subTest(forged=forged):
                setup_host(self.root, "codex", [])
                manifest = self.root / ".minecode/installation-codex.json"
                original = manifest.read_bytes()
                data = json.loads(original)
                data["files"][forged] = digest(b"user content")
                manifest.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "Invalid installation manifest"):
                    remove_host(self.root, "codex")
                manifest.write_bytes(original)
        data = json.loads(manifest.read_bytes())
        data["files"][next(iter(data["files"]))] = "not-a-hash"
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "Invalid installation manifest"):
            setup_host(self.root, "codex", [])

    def test_retired_resource_is_preflighted_before_any_update(self):
        from minecode_runtime.installation import payloads
        setup_host(self.root, "codex", [])
        future = payloads("codex", self.root, [], False)
        old = next(name for name in future if name.endswith("/references/workflow.md"))
        future.pop(old)
        path = self.root / old
        path.unlink()
        external = self.root / "private.txt"
        external.write_text("preserve")
        try:
            path.symlink_to(external)
        except OSError:
            self.skipTest("Creating symlinks is not available to this Windows user")
        with patch("minecode_runtime.installation.payloads", return_value=future):
            with self.assertRaisesRegex(ValueError, "linked installation path"):
                setup_host(self.root, "codex", [])
        self.assertEqual(external.read_text(), "preserve")

    def test_direct_remove_accepts_retired_resources_for_both_hosts(self):
        from minecode_runtime.installation import payloads
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                installed = setup_host(self.root, host, [])
                future = payloads(host, self.root, [], False)
                old = next(name for name in future if name.endswith("/references/workflow.md"))
                future.pop(old)
                with patch("minecode_runtime.installation.payloads", return_value=future):
                    removed, retained = remove_host(self.root, host)
                    self.assertEqual(set(removed), set(installed))
                    self.assertEqual(retained, [])
                    self.assertFalse((self.root / old).exists())
