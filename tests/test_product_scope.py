"""Independent project shapes and retrieval applicability boundaries."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from minecode_runtime.inspection import inspect
from minecode_runtime.retrieval import Retrieval
from minecode_runtime.models import LocalReferenceArtifact


class ProductScopeTests(unittest.TestCase):
    def test_server_descriptors_do_not_imply_fabric_or_resolved_game_version(self):
        for descriptor in ("plugin.yml", "paper-plugin.yml"):
            with self.subTest(descriptor=descriptor), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                resources = root / "plugin/src/main/resources"
                resources.mkdir(parents=True)
                (resources / descriptor).write_text("name: Example\nmain: example.Plugin\napi-version: '1.21'\nfolia-supported: true\n")
                result = inspect(root)
                self.assertEqual(result.detection.project_type, "server-plugin")
                self.assertTrue(result.detection.minecraft_detected)
                self.assertFalse(result.detection.fabric_detected)
                self.assertIsNone(result.minecraft_version)
                self.assertIsNone(result.likely_run_client_task)
                self.assertTrue(any("Folia" in warning for warning in result.warnings))

    def test_unrelated_plugin_file_is_not_a_minecraft_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plugin.yml").write_text("name: unrelated-tool\n")
            self.assertFalse(inspect(root).detection.minecraft_detected)

    def test_common_fabric_mod_and_mixed_workspace_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resources = root / "src/main/resources"
            resources.mkdir(parents=True)
            (resources / "fabric.mod.json").write_text('{"id":"example","environment":"*","entrypoints":{"main":["example.Content"]}}')
            self.assertEqual(inspect(root).detection.project_type, "fabric-mod")
            (resources / "plugin.yml").write_text("name: Example\n")
            result = inspect(root)
            self.assertEqual(result.detection.project_type, "minecraft")
            self.assertTrue(any("affected module" in warning for warning in result.warnings))

    def test_lexical_volume_cannot_evict_exact_local_evidence_before_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            artifacts = [LocalReferenceArtifact(
                artifact_id=name, kind="minecraft-sources", path=str(root / (name + ".jar")),
                scope="project", minecraft_version="1.21.1",
                compatibility={"minecraft": "exact", "mappings": mapping},
            ) for name, mapping in (("exact", "exact"), ("unknown", "unknown"))]
            engine = Retrieval(project, cache_root=root / "cache", sources={})
            with patch("minecode_runtime.retrieval.inspect") as profile, \
                 patch("minecode_runtime.retrieval.local_snapshot", side_effect=lambda a: {"kind": "local-archive", "revision": "fixture", "retrieved_at": "fixture", "id": a.artifact_id}), \
                 patch("minecode_runtime.retrieval.local_matches", side_effect=lambda s, t, **kw: [(1 if s["id"] == "exact" else 500, "Example.java", 1, 1 if s["id"] == "exact" else 100)]), \
                 patch("minecode_runtime.retrieval.local_read", return_value="class Example {}"):
                profile.return_value.local_reference_limitations = []
                profile.return_value.local_reference_artifacts = artifacts
                result = engine.search_reference_code("Example", max_results=1)
            self.assertEqual(result.results[0].source_id, "exact")
            self.assertTrue(result.truncated)
