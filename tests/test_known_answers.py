"""Independent Yarn facts over real stdio, with no models, builds or network."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

from mcp import Client
from mcp.client.stdio import StdioServerParameters

FIXTURES = Path(__file__).resolve().parent / 'fixtures'


def install_mapping_slice(gradle_home: Path, version: str) -> Path:
    """Put independently reviewed CC0 mapping records in a disposable cache."""
    source = FIXTURES / 'known-answers' / f'yarn-{version}.tiny'
    artifact = (gradle_home / 'caches/modules-2/files-2.1/net.fabricmc/yarn'
                / version / 'offline-slice' / f'yarn-{version}-v2.jar')
    artifact.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(artifact, 'w') as output:
        output.writestr('mappings/mappings.tiny', source.read_text(encoding='utf-8'))
    return artifact


class KnownAnswerTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_local_id_call_returns_actionable_error_and_recovers_over_stdio(self):
        with tempfile.TemporaryDirectory(prefix='minecode-id-recovery-') as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            (project / 'gradle.properties').write_text(
                'minecraft_version=1.21.11\nyarn_mappings=1.21.11+build.3\n', encoding='utf-8')
            (project / 'build.gradle').write_text(
                'minecraft "com.mojang:minecraft:$minecraft_version"\n'
                'mappings "net.fabricmc:yarn:$yarn_mappings:v2"\n', encoding='utf-8')
            install_mapping_slice(root / 'gradle-home', '1.21.11+build.3')
            params = StdioServerParameters(command=sys.executable, args=[
                '-m', 'minecode_runtime', '--project', str(project),
                '--reference-cache', str(root / 'reference-cache')],
                env={**os.environ, 'GRADLE_USER_HOME': str(root / 'gradle-home')})
            async with Client(params) as client:
                tools = {tool.name: tool for tool in (await client.list_tools()).tools}
                description = tools['minecode.search_reference_code'].input_schema['properties']['source_ids']['description']
                self.assertIn('registered repository IDs', description)
                self.assertIn('artifact_id', description)
                # Previously observed invalid-ID call, including the stale local ID.
                arguments = {'query': 'InGameHud render',
                             'source_ids': ['local-yarn-mappings-ed5f1f9f2f522e9f'], 'max_results': 3}
                rejected = await client.call_tool('minecode.search_reference_code', arguments)
                self.assertTrue(rejected.is_error)
                message = '\n'.join(block.text for block in rejected.content if block.type == 'text')
                self.assertIn('omit source_ids', message)
                self.assertIn('minecode.search_sources', message)
                self.assertIn('minecode.get_reference_context', message)
                # Follow the model-visible recovery instruction through the same server session.
                arguments.pop('source_ids')
                recovered = await client.call_tool('minecode.search_reference_code', arguments)
                self.assertFalse(recovered.is_error)
                hit = recovered.structured_content['results'][0]
                self.assertEqual(hit['compatibility'], {'minecraft': 'exact', 'mappings': 'exact'})
                self.assertEqual(hit['provenance']['artifact_identity']['mappings_version'], '1.21.11+build.3')
                expanded = await client.call_tool('minecode.get_reference_context', {'result_id': hit['result_id']})
                self.assertFalse(expanded.is_error)
                excerpt = expanded.structured_content['results'][0]['excerpt']
                self.assertIn('(Lnet/minecraft/class_332;Lnet/minecraft/class_9779;)V\tmethod_1753\trender', excerpt)
                self.assertIn('net/minecraft/client/render/RenderTickCounter', excerpt)

    async def test_exact_version_mapping_answers_over_stdio(self):
        # Oracle values are reviewed upstream facts, not produced by MineCode.
        answers = {
            '1.20.4': '(Lnet/minecraft/class_332;F)V',
            '1.21.11': '(Lnet/minecraft/class_332;Lnet/minecraft/class_9779;)V',
        }
        with tempfile.TemporaryDirectory(prefix='minecode-known-answers-') as directory:
            root = Path(directory)
            home = root / 'gradle-home'
            for minecraft in answers:
                install_mapping_slice(home, minecraft + '+build.3')
            for minecraft, descriptor in answers.items():
                with self.subTest(minecraft=minecraft):
                    project = root / minecraft
                    project.mkdir()
                    (project / 'gradle.properties').write_text(
                        f'minecraft_version={minecraft}\nyarn_mappings={minecraft}+build.3\n', encoding='utf-8')
                    (project / 'build.gradle').write_text(
                        "plugins { id 'fabric-loom' version '1.14.10' }\n"
                        'minecraft "com.mojang:minecraft:$minecraft_version"\n'
                        'mappings "net.fabricmc:yarn:$yarn_mappings:v2"\n', encoding='utf-8')
                    params = StdioServerParameters(
                        command=sys.executable,
                        args=['-m', 'minecode_runtime', '--project', str(project),
                              '--reference-cache', str(root / 'reference-cache')],
                        env={**os.environ, 'GRADLE_USER_HOME': str(home)},
                    )
                    async with Client(params) as client:
                        profile = await client.call_tool('minecode.get_project_profile', {})
                        self.assertFalse(profile.is_error)
                        self.assertEqual(profile.structured_content['minecraft_version'], minecraft)
                        search = await client.call_tool('minecode.search_reference_code', {'query': 'InGameHud render'})
                        self.assertFalse(search.is_error)
                        results = search.structured_content['results']
                        self.assertEqual(len(results), 1, results)
                        hit = results[0]
                        self.assertEqual(hit['path'], 'mappings/mappings.tiny')
                        self.assertEqual(hit['compatibility'], {'minecraft': 'exact', 'mappings': 'exact'})
                        identity = hit['provenance']['artifact_identity']
                        self.assertEqual(identity['minecraft_version'], minecraft)
                        self.assertEqual(identity['mappings_version'], minecraft + '+build.3')
                        expanded = await client.call_tool('minecode.get_reference_context',
                                                         {'result_id': hit['result_id'], 'context_lines': 20})
                        self.assertFalse(expanded.is_error)
                        context = expanded.structured_content['results'][0]
                        self.assertEqual(context['revision'], hit['revision'])
                        self.assertFalse(context['content_truncated'])
                        self.assertIn('c\tnet/minecraft/class_329\tnet/minecraft/client/gui/hud/InGameHud', context['excerpt'])
                        self.assertIn(f'\tm\t{descriptor}\tmethod_1753\trender', context['excerpt'])
                        self.assertIn('net/minecraft/client/gui/DrawContext', context['excerpt'])
                        other = next(value for version, value in answers.items() if version != minecraft)
                        self.assertNotIn(other, context['excerpt'])
                        if minecraft == '1.21.11':
                            self.assertIn('net/minecraft/client/render/RenderTickCounter', context['excerpt'])

    async def test_reproduced_mixin_failure_preserves_exact_selector(self):
        log = (FIXTURES / 'mixin-startup-crash.txt').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'project'
            project.mkdir()
            async with Client(StdioServerParameters(command=sys.executable, args=[
                '-m', 'minecode_runtime', '--project', str(project),
                '--reference-cache', str(Path(directory) / 'cache')],
            )) as client:
                result = await client.call_tool('minecode.analyze_runtime_failure', {
                    'output': log, 'environment': {'minecraft': '1.21.11', 'mappings': 'yarn-1.21.11+build.3'},
                })
                self.assertFalse(result.is_error)
                data = result.structured_content
                self.assertEqual(data['mixin_failure'], 'target-not-found')
                self.assertEqual(data['mixin_details']['target_member'], 'render')
                self.assertEqual(data['mixin_details']['descriptor'], '(Lnet/minecraft/client/gui/DrawContext;F)V')
                self.assertEqual(data['environment']['minecraft'], '1.21.11')
                self.assertEqual(data['confidence'], 'pattern-match')
                self.assertEqual(data['attempted_repair']['result'], 'not_attempted')


if __name__ == '__main__':
    unittest.main()
