"""Protect the portable, explicitly selected distribution surface."""

from pathlib import Path
import re
import tempfile
import unittest
import yaml
from urllib.parse import unquote, urlsplit

from release_resources import BUNDLE_FILES, SKILL_DIRECTORIES, bundle_sources, check_build_tree, runtime_data_sources


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS = {
    "project-notes",
    "evals",
    "test-projects",
    "context",
    "core",
    "examples",
    "hooks",
    "java-analysis",
    "minecraft-analysis",
}
PRIVATE_PATTERNS = {
    "windows-user-profile": re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
    "unix-user-profile": re.compile(r"/(?:home|Users)/[^/\s]+/"),
    "local-ai-workspace": re.compile(r"\.codex[\\/]\.chatgpt-projects|\.chatgpt-projects", re.IGNORECASE),
    "internal-project-id": re.compile(r"\bg-p-[a-f0-9]{8,}\b", re.IGNORECASE),
    "private-repository": re.compile(r"github\.com/[^/\s]+/[^/\s]*(?:private|internal)[^/\s]*", re.IGNORECASE),
    "internal-development-phase": re.compile(r"\bphase(?:\s+|_)\d+(?=\b|_)", re.IGNORECASE),
}
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def heading_ids(document: Path) -> set[str]:
    result = set()
    for line in document.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if not match:
            continue
        label = re.sub(r"[`*_~]", "", match.group(1).lower())
        label = re.sub(r"[^\w\- ]", "", label)
        result.add(re.sub(r"\s+", "-", label.strip()))
    return result


class PackagingTests(unittest.TestCase):
    def test_repeated_build_refuses_retired_resources_and_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            approved = package / 'data/bundle/README.md'
            approved.parent.mkdir(parents=True)
            approved.write_text('previous approved output')
            check_build_tree(ROOT, package)
            for name in ('data/bundle/private-note.txt', 'retired_module.py'):
                with self.subTest(name=name):
                    stale = package / name
                    stale.write_text('synthetic obsolete output')
                    with self.assertRaisesRegex(ValueError, 'Unexpected build output'):
                        check_build_tree(ROOT, package)
                    stale.unlink()

    def test_required_release_resources_are_selected(self):
        selected = {path.relative_to(ROOT).as_posix() for path in bundle_sources(ROOT)}
        for expected in (
            "skills/minecraft-debugger/SKILL.md",
            "skills/minecraft-java-developer/SKILL.md",
            "skills/minecraft-java-developer/references/workflow.md",
            "skills/minecraft-project-inspector/SKILL.md",
            "skills/minecraft-client-developer/SKILL.md",
            "skills/minecraft-server-developer/SKILL.md",
            "skills/minecraft-server-developer/references/operations.md",
            "skills/minecraft-understand-anticheat/SKILL.md",
            "skills/minecraft-understand-anticheat/references/grim.md",
            "skills/minecraft-java-developer/references/content-mods.md",
            "references/gameplay/techniques.json",
            "integrations/providers.json",
            "docs/INSTALLATION.md",
            "docs/QUICKSTART.md",
            "docs/ADVANCED_SETUP.md",
            "mcp/README.md",
            "THIRD_PARTY_NOTICES.md",
            "SECURITY.md",
        ):
            self.assertIn(expected, selected)

    def test_every_shipped_skill_has_discoverable_yaml_frontmatter(self):
        for directory in SKILL_DIRECTORIES:
            with self.subTest(skill=directory.name):
                text = (ROOT / directory / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                frontmatter = yaml.safe_load(text.split("---", 2)[1])
                self.assertEqual(frontmatter["name"], directory.name)
                self.assertIsInstance(frontmatter["description"], str)
                self.assertTrue(frontmatter["description"].strip())

    def test_development_history_cannot_enter_the_bundle(self):
        selected = {path.relative_to(ROOT).as_posix() for path in bundle_sources(ROOT)}
        offenders = sorted(
            name
            for name in selected
            if any(part in FORBIDDEN_PARTS for part in Path(name).parts) or Path(name).name.startswith("PHASE_")
        )
        self.assertEqual(offenders, [])

    def test_runtime_registries_have_one_packaged_authority(self):
        runtime = {path.name for path in runtime_data_sources(ROOT)}
        bundled = {path.relative_to(ROOT).as_posix() for path in bundle_sources(ROOT)}
        self.assertEqual(runtime, {"sources.yaml", "developer-knowledge.json"})
        self.assertFalse(any(name.startswith("references/sources/") for name in bundled))

    def test_selected_product_text_has_no_private_release_residue(self):
        affected: dict[str, list[str]] = {}
        release_sources = {*bundle_sources(ROOT), *runtime_data_sources(ROOT)}
        for path in release_sources:
            if path.suffix.lower() not in {".md", ".json", ".yaml", ".svg"}:
                continue
            text = path.read_text(encoding="utf-8")
            for category, pattern in PRIVATE_PATTERNS.items():
                if pattern.search(text):
                    affected.setdefault(category, []).append(path.relative_to(ROOT).as_posix())
        self.assertEqual(affected, {})

    def test_numbered_phase_pattern_preserves_technical_language(self):
        pattern = PRIVATE_PATTERNS["internal-development-phase"]
        for residue in ("Phase 4", "phase 12", "PHASE_5", "PHASE_2_5.md"):
            with self.subTest(residue=residue):
                self.assertIsNotNone(pattern.search(residue))
        for technical in ("render phase", "lifecycle phase", "play/configuration phase"):
            with self.subTest(technical=technical):
                self.assertIsNone(pattern.search(technical))

    def test_selected_markdown_links_stay_inside_the_bundle(self):
        selected_paths = bundle_sources(ROOT)
        selected = {path.resolve() for path in selected_paths}
        generated_targets = {path.resolve() for path in runtime_data_sources(ROOT)}
        module_root = (ROOT / "src" / "minecode_runtime").resolve()
        failures = []
        for document in (path for path in selected_paths if path.suffix == ".md"):
            for raw in LINK.findall(document.read_text(encoding="utf-8")):
                target = raw.strip().strip("<>").split(" ", 1)[0]
                parsed = urlsplit(target)
                if not target or parsed.scheme or parsed.netloc:
                    continue
                resolved = document.resolve() if not parsed.path else (document.parent / unquote(parsed.path)).resolve()
                if (
                    resolved not in selected
                    and resolved not in generated_targets
                    and not resolved.is_relative_to(module_root)
                ):
                    failures.append(f"{document.relative_to(ROOT).as_posix()} -> {raw}")
                    continue
                if (
                    parsed.fragment
                    and resolved.suffix.lower() == ".md"
                    and parsed.fragment not in heading_ids(resolved)
                ):
                    failures.append(f"{document.relative_to(ROOT).as_posix()} -> missing heading #{parsed.fragment}")
        self.assertEqual(failures, [])

    def test_manifest_is_an_explicit_file_allowlist(self):
        names = {path.as_posix() for path in BUNDLE_FILES}
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertNotIn("PROJECT_STATE.md", names)
        self.assertFalse(any("*" in name for name in names))
        self.assertTrue(manifest.startswith("exclude *\nrecursive-exclude * *\n"))
        self.assertIn("recursive-include src/minecode_runtime *.py", manifest)
        self.assertNotIn("graft ", manifest)
        self.assertNotIn("recursive-include tests", manifest)
        self.assertNotIn("include scripts", manifest)


if __name__ == "__main__":
    unittest.main()
