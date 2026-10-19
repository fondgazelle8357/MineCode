"""Run existing unittest checks once and report only what they establish. No models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

QUICK = (
    "test_runtime.MCPTests",
    "test_installation",
    "test_packaging",
    "test_known_answers",
    "test_fabric_module_sources",
)


class Results(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed: set[str] = set()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.add(test.id())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full", action="store_true", help="Run the full existing CI suite instead of the short checks"
    )
    parser.add_argument("--report", type=Path, default=ROOT / ".local/verification.md")
    args = parser.parse_args()
    loader = unittest.TestLoader()
    suite = (
        loader.discover(str(ROOT / "tests"))
        if args.full
        else unittest.TestSuite(loader.loadTestsFromName(name) for name in QUICK)
    )
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=1, resultclass=Results).run(suite)
    connection_checks = {
        "test_runtime.MCPTests.test_tools_schema_and_calls",
        "test_runtime.MCPTests.test_actual_stdio_transport",
        "test_packaging.PackagingTests.test_every_shipped_skill_has_discoverable_yaml_frontmatter",
        "test_packaging.PackagingTests.test_selected_markdown_links_stay_inside_the_bundle",
        "test_installation.InstallationTests.test_install_update_remove_leaves_unrelated_files",
        "test_installation.InstallationTests.test_both_host_configs_bind_installed_python_and_selected_project",
        "test_installation.InstallationTests.test_three_skill_install_upgrades_to_specialties_for_both_hosts",
    }
    known_checks = {
        "test_known_answers.KnownAnswerTests.test_exact_version_mapping_answers_over_stdio",
        "test_known_answers.KnownAnswerTests.test_reproduced_mixin_failure_preserves_exact_selector",
    }
    connected = connection_checks <= result.passed
    correct = known_checks <= result.passed
    report = (
        "# MineCode verification\n\n"
        f"{datetime.now(timezone.utc).isoformat()} · {'full' if args.full else 'short'} suite · "
        f"{result.testsRun} tests · {time.monotonic() - started:.1f}s · model calls: 0\n\n"
        f"Suite: {'PASS' if result.wasSuccessful() else 'FAIL'} "
        f"({len(result.failures)} failures, {len(result.errors)} errors, {len(result.skipped)} skipped).\n\n"
        "| State | Evidence and limits |\n| --- | --- |\n"
        f"| {'CONNECTED' if connected else 'UNVERIFIED'} | "
        "14 MCP interfaces: input/output schemas and calls; stdio startup; six packaged skill headers, "
        "local links, and installer configuration. Source checkout scope; installed-wheel acceptance "
        "runs separately in existing CI. No host/model discovery claim. |\n"
        f"| {'TECHNICALLY CORRECT' if correct else 'UNVERIFIED'} | "
        "Pinned Yarn 1.20.4/build 3 and 1.21.11/build 3: method/class records, version selection, "
        "mapping provenance and expanded evidence over stdio; reproduced Mixin crash classification. "
        "Limited to these facts and this log. |\n"
        "| Manual checks | This suite does not start a coding agent or Minecraft. "
        "Review generated changes and check the behavior appropriate to your project. |\n"
        "| Outside this suite | Other Minecraft "
        "versions/APIs; live provider execution; real Gradle/Minecraft execution, rendering and gameplay. "
        "Blocked execution/unavailable providers count as interface responses only. |\n"
    )
    if not result.wasSuccessful():
        report += "\nFailed/error checks:\n" + "".join(
            f"- `{test.id()}`\n" for test, _ in result.failures + result.errors
        )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report, encoding="utf-8")
    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(report)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
