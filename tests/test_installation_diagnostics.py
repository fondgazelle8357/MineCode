"""An installed file/config is not evidence of MineCode MCP availability to a model turn."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from minecode_runtime.installation import configuration, setup_host
from minecode_runtime.installation_diagnostics import inspect_installation


class InstallationDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minecode doctor ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_missing_installation_does_not_write_to_project(self):
        before = list(self.root.rglob("*"))
        report = inspect_installation(self.root, "codex")
        self.assertEqual(report["status"], "missing")
        self.assertFalse(report["config_present"])
        self.assertEqual(report["host_model_turn"], "unverified")
        self.assertEqual(list(self.root.rglob("*")), before)

    def test_public_cli_dispatch_is_read_only_for_both_hosts(self):
        for host in ("codex", "claude"):
            with self.subTest(host=host):
                setup_host(self.root, host, [])
                before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                result = subprocess.run(
                    [sys.executable, "-B", "-m", "minecode_runtime", "doctor", "--host", host,
                     "--project", str(self.root)], capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["status"], "configured_unverified")
                self.assertEqual(report["project"], str(self.root))
                self.assertTrue(report["runtime_version"])
                self.assertEqual(before, {p.relative_to(self.root): p.read_bytes()
                                          for p in self.root.rglob("*") if p.is_file()})

    def test_public_cli_missing_project_is_actionable_error(self):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "minecode_runtime", "doctor", "--host", "codex",
             "--project", str(self.root / "missing")], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_manual_merge_does_not_require_ownership_of_host_config(self):
        for host, relative in (("codex", ".codex/config.toml"), ("claude", ".mcp.json")):
            with self.subTest(host=host):
                setup_host(self.root, host, [], skills_only=True)
                config = self.root / relative
                config.parent.mkdir(exist_ok=True)
                config.write_text(configuration(host, self.root, []), encoding="utf-8")
                report = inspect_installation(self.root, host)
                self.assertEqual(report["status"], "configured_unverified")
                self.assertEqual(report["ownership"]["config"], "unmanaged")

    def test_unrelated_host_settings_do_not_invalidate_runtime_config(self):
        setup_host(self.root, "codex", [])
        config = self.root / ".codex/config.toml"
        config.write_text(config.read_text() + '\n[other]\nvalue = "keep"\n')
        report = inspect_installation(self.root, "codex")
        self.assertEqual(report["status"], "configured_unverified")
        self.assertEqual(report["ownership"]["config"], "modified")

    def test_disabled_server_is_not_configured(self):
        setup_host(self.root, "codex", [])
        config = self.root / ".codex/config.toml"
        config.write_text(config.read_text() + "\nenabled = false\n")
        report = inspect_installation(self.root, "codex")
        self.assertEqual(report["status"], "incomplete_or_mismatched")
        self.assertIs(report["config_enabled"], False)
        self.assertEqual(report["host_trust"], "unverified")

    def test_wrong_python_or_project_is_reported(self):
        setup_host(self.root, "claude", [])
        config = self.root / ".mcp.json"
        data = json.loads(config.read_text())
        data["mcpServers"]["minecode"]["args"][3] = str(self.root / "other")
        config.write_text(json.dumps(data))
        report = inspect_installation(self.root, "claude")
        self.assertFalse(report["config_matches_runtime"])
        self.assertEqual(report["configured_project"], str(self.root / "other"))

    def test_malformed_config_reports_error_without_crashing(self):
        setup_host(self.root, "claude", [])
        config = self.root / ".mcp.json"
        for value in ("{", "[]", '{"mcpServers": null}', '{"mcpServers": {"minecode": false}}'):
            with self.subTest(value=value):
                config.write_text(value)
                report = inspect_installation(self.root, "claude")
                self.assertEqual(report["status"], "incomplete_or_mismatched")
                self.assertIsNotNone(report["config_error"])

    def test_skills_only_is_not_connected(self):
        setup_host(self.root, "codex", [], skills_only=True)
        result = inspect_installation(self.root, "codex")
        self.assertEqual(result["status"], "skills_only")
        self.assertGreater(result["skills"]["matching"], 0)
        self.assertEqual(result["mcp_transport"], "not_tested")
        self.assertEqual(result["host_model_turn"], "unverified")

    def test_configured_codex_still_requires_actual_model_tool_call(self):
        setup_host(self.root, "codex", [])
        result = inspect_installation(self.root, "codex")
        self.assertEqual(result["status"], "configured_unverified")
        self.assertTrue(result["config_matches_runtime"])
        self.assertEqual(result["skills"]["matching"], result["skills"]["expected"])
        self.assertEqual(result["host_model_turn"], "unverified")

        self.assertIn("get_project_profile", result["next"])

    def test_codex_doctor_rejects_missing_short_or_invalid_tool_timeout(self):
        setup_host(self.root, "codex", [])
        config = self.root / ".codex/config.toml"
        original = config.read_text()
        for replacement in ("", "tool_timeout_sec = 60", "tool_timeout_sec = true", 'tool_timeout_sec = "630"'):
            with self.subTest(replacement=replacement):
                config.write_text(original.replace("tool_timeout_sec = 630", replacement))
                report = inspect_installation(self.root, "codex")
                self.assertFalse(report["config_matches_runtime"])
                self.assertEqual(report["status"], "incomplete_or_mismatched")

    def test_configured_claude_is_not_host_verified(self):
        setup_host(self.root, "claude", [])
        result = inspect_installation(self.root, "claude")
        self.assertEqual(result["status"], "configured_unverified")
        self.assertEqual(result["host_model_turn"], "unverified")

    def test_missing_or_stale_config_is_not_connected(self):
        setup_host(self.root, "codex", [])
        config = self.root / ".codex/config.toml"
        config.write_text(config.read_text().replace("required = true", "required = false"))
        report = inspect_installation(self.root, "codex")
        self.assertEqual(report["status"], "incomplete_or_mismatched")
        self.assertFalse(report["config_matches_runtime"])

    def test_damaged_skill_is_reported_not_claimed_installed(self):
        setup_host(self.root, "codex", [])
        skill = self.root / ".agents/skills/minecraft-client-developer/SKILL.md"
        skill.write_text("not the installed skill")
        report = inspect_installation(self.root, "codex")
        self.assertEqual(report["status"], "incomplete_or_mismatched")
        self.assertIn(".agents/skills/minecraft-client-developer/SKILL.md", report["skills"]["outdated"])

    def test_manifest_damage_does_not_trigger_unsafe_repair(self):
        setup_host(self.root, "codex", [])
        manifest = self.root / ".minecode/installation-codex.json"
        manifest.write_text(json.dumps({"schema_version": 1, "host": "codex", "files": {"../secret": "invalid"}}))
        result = inspect_installation(self.root, "codex")
        self.assertEqual(result["status"], "incomplete_or_mismatched")
        self.assertIsNotNone(result["manifest_error"])

    def test_missing_original_config_not_reported_as_intentional_skills_only(self):
        setup_host(self.root, "codex", [])
        (self.root / ".codex/config.toml").unlink()
        result = inspect_installation(self.root, "codex")
        self.assertEqual(result["status"], "incomplete_or_mismatched")


if __name__ == "__main__":
    unittest.main()
