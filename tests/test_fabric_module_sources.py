"""Synthetic cache fixtures for direct Fabric module source discovery."""
import unittest
from mcp import Client
from minecode_runtime.gradle import Runtime
from minecode_runtime.local_sources import _fabric_module_sources
from minecode_runtime.retrieval import Retrieval
from minecode_runtime.server import create_server
import test_retrieval as fixtures


class FabricModuleDiscoveryTests(unittest.TestCase):
    setUp = fixtures.LocalArtifactTests.setUp
    tearDown = fixtures.LocalArtifactTests.tearDown
    archive = staticmethod(fixtures.LocalArtifactTests.archive)

    def pom(self, dependencies, digest='receipt', prefix='', version='0.119.5+1.21.5'):
        path = (self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                / 'fabric-api' / version / digest / f'fabric-api-{version}.pom')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prefix + '<project xmlns="http://maven.apache.org/POM/4.0.0">'
                        '<groupId>net.fabricmc.fabric-api</groupId><artifactId>fabric-api</artifactId>'
                        f'<version>{version}</version><dependencies>{dependencies}</dependencies></project>')
        return path

    def dependency(self, module='fabric-rendering-v1', version='1.2.3+abc', extra=''):
        return ('<dependency><groupId>net.fabricmc.fabric-api</groupId>'
                f'<artifactId>{module}</artifactId><version>{version}</version>{extra}</dependency>')

    def jar(self, module='fabric-rendering-v1', version='1.2.3+abc'):
        return self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                            / module / version / 'digest' / f'{module}-{version}-sources.jar',
                            {'example/OverlayHook.java': 'public class OverlayHook { void draw() {} }'})

    def discover(self):
        return _fabric_module_sources(self.gradle_home, '0.119.5+1.21.5', '1.21.5', 'mojang-official', None)

    def test_search_and_context_follow_pinned_dependency_with_unknown_namespace(self):
        self.pom(self.dependency())
        expected = self.jar()
        self.jar(version='9.9.9+wrong')
        artifacts = self.discover()
        self.assertEqual([item.path for item in artifacts], [str(expected.resolve())])
        self.assertEqual(artifacts[0].artifact_version, '1.2.3+abc')
        self.assertIsNone(artifacts[0].namespace)
        self.assertEqual(artifacts[0].compatibility,
                         {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'unknown'})
        engine = Retrieval(self.project, cache_root=self.root / 'references', sources={})
        result = engine.search_reference_code('OverlayHook').results[0]
        self.assertEqual(result.provenance['selection'], 'supporting-local')
        self.assertIn('cached', result.provenance['identity_evidence']['dependency'])
        self.assertIn('void draw()', engine.get_reference_context(result.result_id, 3).results[0].excerpt)

    def test_missing_mojang_implementation_does_not_return_lifecycle_fragments(self):
        """Reproduce the real 1.21.11 campfire lookup without game source redistribution."""
        import asyncio
        import hashlib
        from minecode_runtime.inspection import inspect

        api, version = '0.141.6+1.21.11', '2.6.15+4ebb5c083e'
        (self.project / 'gradle.properties').write_text(
            f'minecraft_version=1.21.11\nfabric_version={api}\n')
        build = self.project / 'build.gradle'
        build.write_text(build.read_text().replace('"net.fabricmc:yarn:$yarn_mappings:v2"',
                                                  'loom.officialMojangMappings()'))
        self.pom(self.dependency('fabric-lifecycle-events-v1', version), version=api)
        path = 'api/client/event/lifecycle/v1/ClientBlockEntityEvents.java'
        jar = self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                           / 'fabric-lifecycle-events-v1' / version / 'digest'
                           / f'fabric-lifecycle-events-v1-{version}-sources.jar',
                           {path: 'public class ClientBlockEntityEvents {\n'
                            ' // Called when a BlockEntity is loaded into a ClientWorld.\n}'})
        # A named compiled JAR is not a source archive or a search hit.
        self.archive(self.project / '.gradle/loom-cache/minecraftMaven/net/minecraft'
                     / 'minecraft-merged-fixture/1.21.11-loom.mappings.1_21_11.layered+hash.2198-v2'
                     / 'minecraft-merged-1.21.11-loom.mappings.1_21_11.layered+hash.2198-v2.jar',
                     {'net/minecraft/world/level/block/entity/CampfireBlockEntity.class': b'\xca\xfe\xba\xbe'})
        profile = inspect(self.project)
        self.assertEqual(profile.mappings_type, 'mojang-official')
        self.assertEqual([a.kind for a in profile.local_reference_artifacts], ['fabric-api-sources'])

        async def check():
            async with Client(create_server(Runtime(self.project))) as client:
                response = await client.call_tool('minecode.search_reference_code',
                                                  {'query': 'CampfireBlockEntity loadAdditional', 'max_results': 2})
                self.assertFalse(response.is_error)
                packet = response.structured_content
                self.assertEqual(packet['results'], [])
                warnings = ' '.join(packet['warnings'])
                for expected in ('No literal identifier match', 'No local Minecraft source archive',
                                 '1.21.11', 'mojang-official', 'mapped Minecraft JAR', 'javap'):
                    self.assertIn(expected, warnings)
                self.assertFalse(packet['truncated'])
                # The real event API and ordinary descriptive searches still work.
                for query in ('ClientBlockEntityEvents', 'block entity loaded'):
                    response = await client.call_tool('minecode.search_reference_code', {'query': query})
                    hit = response.structured_content['results'][0]
                    self.assertEqual(hit['path'], path)
                    self.assertEqual(hit['revision'], 'sha256:' + hashlib.sha256(jar.read_bytes()).hexdigest())
                    self.assertIsNone(hit['provenance']['namespace'])
                    self.assertEqual(hit['compatibility'],
                                     {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'unknown'})
        asyncio.run(check())

    def test_modules_after_first_twelve_are_searchable(self):
        self.pom(''.join(self.dependency(f'fabric-module-{i:02}') for i in range(16)))
        for i in range(16):
            self.jar(f'fabric-module-{i:02}')
        self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                     / 'fabric-module-15/1.2.3+abc/digest/fabric-module-15-1.2.3+abc-sources.jar',
                     {'LateModule.java': 'class LateModule {}'})
        engine = Retrieval(self.project, cache_root=self.root / 'references', sources={})
        from minecode_runtime.inspection import inspect
        self.assertEqual(len(inspect(self.project).local_reference_artifacts), 16)
        self.assertIn('LateModule.java', engine.search_reference_code('LateModule').results[0].path)

    def test_lifecycle_identifiers_beat_mapping_noise_through_mcp(self):
        """Original small fixtures shaped after the independently inspected 1.21.11 APIs.

        Full published archives are checked separately; these are not complete
        upstream sources or an oracle for callback/game behavior.
        """
        import asyncio
        api = '0.141.6+1.21.11'
        versions = {'fabric-networking-api-v1': '5.1.6+6b6d71a53e',
                    'fabric-lifecycle-events-v1': '2.6.15+4ebb5c083e'}
        (self.project / 'gradle.properties').write_text(
            f'minecraft_version=1.21.11\nyarn_mappings=1.21.11+build.3\nfabric_version={api}\n')
        self.pom(''.join(self.dependency(module, version) for module, version in versions.items()), version=api)
        # Separate members from the class declaration, as in the real sources.
        entries = {
            'api/client/networking/v1/ClientPlayConnectionEvents.java':
                'class ClientPlayConnectionEvents {\n' + '// connection event\n' * 20
                + 'Event<Disconnect> DISCONNECT;\ncallback.onPlayDisconnect(handler, client);\n}',
            'api/client/event/lifecycle/v1/ClientTickEvents.java':
                'class ClientTickEvents {\n' + '// client tick event\n' * 20
                + 'Event<EndTick> END_CLIENT_TICK;\ncallback.onEndTick(client);\n}',
            'mixin/networking/ConnectionMixin.java':
                'class ConnectionMixin {\n' + '// connection\n' * 20
                + '@Inject(method = "channelInactive", at = @At("HEAD"))\n'
                + 'extension.getAddon().handleDisconnect();\n}',
            'api/client/networking/v1/C2SPlayChannelEvents.java':
                '// client channel inactive event connection\n' * 100,
            'mixin/recipe/ConnectionMixin.java':
                'class ConnectionMixin { void channelInactiveSuffix() {} }',
        }
        jars = {module: self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                                    / module / version / 'digest' / f'{module}-{version}-sources.jar',
                                    {path: text for path, text in entries.items()
                                     if ('lifecycle/' in path) == (module == 'fabric-lifecycle-events-v1')})
                for module, version in versions.items()}
        self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc/yarn'
                     / '1.21.11+build.3/digest/yarn-1.21.11+build.3-v2.jar',
                     {'mappings/mappings.tiny': 'client play connection events disconnect\n' * 100
                      + 'client tick events end\n' * 100
                      + 'channelInactive\n'})
        engine = Retrieval(self.project, cache_root=self.root / 'references', sources={'remote': fixtures.source('remote')})

        async def check():
            async with Client(create_server(Runtime(self.project), engine)) as client:
                for query, path, member, implementation in [
                    ('ClientPlayConnectionEvents DISCONNECT', 'api/client/networking/v1/ClientPlayConnectionEvents.java',
                     'Event<Disconnect> DISCONNECT', 'callback.onPlayDisconnect(handler, client)'),
                    ('ClientTickEvents END_CLIENT_TICK', 'api/client/event/lifecycle/v1/ClientTickEvents.java',
                     'Event<EndTick> END_CLIENT_TICK', 'callback.onEndTick(client)'),
                    ('ConnectionMixin channelInactive', 'mixin/networking/ConnectionMixin.java',
                     '@Inject(method = "channelInactive"', 'extension.getAddon().handleDisconnect()'),
                    ('channelInactive', 'mixin/networking/ConnectionMixin.java',
                     '@Inject(method = "channelInactive"', 'extension.getAddon().handleDisconnect()'),
                ]:
                    with self.subTest(query=query):
                        response = await client.call_tool('minecode.search_reference_code',
                                                          {'query': query, 'max_results': 1})
                        self.assertFalse(response.is_error)
                        hit = response.structured_content['results'][0]
                        self.assertEqual(hit['path'], path)
                        self.assertIn(member, hit['excerpt'])
                        self.assertEqual(hit['compatibility'],
                                         {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'unknown'})
                        self.assertIsNone(hit['provenance']['namespace'])
                        self.assertEqual(hit['provenance']['selection'], 'supporting-local')
                        module = 'fabric-lifecycle-events-v1' if 'lifecycle/' in path else 'fabric-networking-api-v1'
                        self.assertEqual(hit['provenance']['artifact_identity']['artifact_version'], versions[module])
                        self.assertIn(f'fabric-api:{api} POM', hit['provenance']['identity_evidence']['dependency'])
                        expanded = await client.call_tool('minecode.get_reference_context',
                                                          {'result_id': hit['result_id'], 'context_lines': 5})
                        context = expanded.structured_content['results'][0]
                        self.assertIn(implementation, context['excerpt'])
                        import hashlib
                        self.assertEqual(context['revision'], 'sha256:' + hashlib.sha256(jars[module].read_bytes()).hexdigest())
                        self.assertEqual(context['revision'], hit['revision'])
                # Mapping evidence remains available, and an explicit repository
                # cannot evict the pinned implementation at a one-result limit.
                response = await client.call_tool('minecode.search_reference_code',
                                                  {'query': 'channelInactive', 'max_results': 10})
                self.assertIn('mappings/mappings.tiny', [hit['path'] for hit in response.structured_content['results']])
                response = await client.call_tool('minecode.search_reference_code',
                                                  {'query': 'channelInactive', 'max_results': 1, 'source_ids': ['remote']})
                self.assertEqual(response.structured_content['results'][0]['path'], 'mixin/networking/ConnectionMixin.java')
                self.assertTrue(any('not fetched' in warning for warning in response.structured_content['warnings']))
        asyncio.run(check())

    def test_owner_member_queries_reach_mapping_records_and_inherited_declarations(self):
        """Original miniature sources; the real archive answers are verified separately."""
        import asyncio
        import hashlib
        api, module = '0.141.6+1.21.11', '5.1.6+6b6d71a53e'
        (self.project / 'gradle.properties').write_text(
            f'minecraft_version=1.21.11\nyarn_mappings=1.21.11+build.3\nfabric_version={api}\n')
        self.pom(self.dependency('fabric-networking-api-v1', module), version=api)
        entries = {
            'net/ClientPlayNetworking.java': 'class ClientPlayNetworking {\n'
                ' // render client inGameHud example\n void example() { client.inGameHud.render(); }\n}',
            'net/AbstractNetworkAddon.java': 'package net;\npublic abstract class AbstractNetworkAddon {\n'
                ' public final void handleDisconnect() {\n  notifyDisconnected();\n }\n}',
            'net/AbstractChanneledNetworkAddon.java': 'package net;\n'
                'abstract class AbstractChanneledNetworkAddon<H> extends AbstractNetworkAddon {}',
            'net/client/ClientCommonNetworkAddon.java': 'package net.client;\n'
                'import net.AbstractChanneledNetworkAddon;\n'
                'abstract class ClientCommonNetworkAddon<H, T extends Handler> extends AbstractChanneledNetworkAddon<H> {}',
            'net/client/ClientPlayNetworkAddon.java': 'package net.client;\n'
                'final class ClientPlayNetworkAddon extends ClientCommonNetworkAddon<Payload<?>, Handler> {}',
            'unrelated/AbstractNetworkAddon.java': 'package unrelated;\n'
                'class AbstractNetworkAddon { public void handleDisconnect() {} }',
        }
        jar = self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                           / 'fabric-networking-api-v1' / module / 'digest' / f'fabric-networking-api-v1-{module}-sources.jar', entries)
        mapping = self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc/yarn'
                               / '1.21.11+build.3/digest/yarn-1.21.11+build.3-v2.jar',
                               {'mappings/mappings.tiny': 'tiny\t2\t0\tintermediary\tnamed\n'
                                'c\tnet/minecraft/class_310\tnet/minecraft/client/MinecraftClient\n'
                                '\tc\tInGameHud render documentation is not this class member\n'
                                '\tm\t()V\tmethod_1\trender\n'
                                'c\tnet/minecraft/class_329\tnet/minecraft/client/gui/hud/InGameHud\n'
                                '\tf\tI\tfield_1\tother\n'
                                '\tm\t(Lnet/minecraft/class_332;Lnet/minecraft/class_9779;)V\tmethod_1753\trender\n'
                                'c\tnet/minecraft/class_999\tnet/minecraft/Other\n'
                                '\tm\t()V\tmethod_2\trender\n'})
        engine = Retrieval(self.project, cache_root=self.root / 'references', sources={})

        async def check():
            async with Client(create_server(Runtime(self.project), engine)) as client:
                for query, path, member, archive in [
                    ('InGameHud render', 'mappings/mappings.tiny', 'method_1753', mapping),
                    ('ClientPlayNetworkAddon handleDisconnect', 'net/AbstractNetworkAddon.java', 'void handleDisconnect()', jar),
                ]:
                    for limit in (1, 3):
                        with self.subTest(query=query, limit=limit):
                            response = await client.call_tool('minecode.search_reference_code', {'query': query, 'max_results': limit})
                            hit = response.structured_content['results'][0]
                            self.assertEqual(hit['path'], path)
                            self.assertIn(member, hit['excerpt'])
                            self.assertEqual(hit['revision'], 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest())
                            context = await client.call_tool('minecode.get_reference_context', {'result_id': hit['result_id'], 'context_lines': 2})
                            self.assertIn(member, context.structured_content['results'][0]['excerpt'])
                            if path.endswith('.tiny'):
                                self.assertEqual(hit['provenance']['mapping_owner']['named'], 'net/minecraft/client/gui/hud/InGameHud')
                                self.assertEqual(hit['compatibility'], {'minecraft': 'exact', 'mappings': 'exact'})
                            else:
                                self.assertIsNone(hit['provenance']['namespace'])
                                self.assertEqual(hit['compatibility'], {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'unknown'})
        asyncio.run(check())

    def test_generic_receiver_declaration_beats_javadoc_and_unregister_neighbor(self):
        import asyncio
        api, version = '0.141.6+1.21.11', '5.1.6+6b6d71a53e'
        (self.project / 'gradle.properties').write_text(
            f'minecraft_version=1.21.11\nyarn_mappings=1.21.11+build.3\nfabric_version={api}\n')
        self.pom(self.dependency('fabric-networking-api-v1', version), version=api)
        path = 'api/client/networking/v1/ClientPlayNetworking.java'
        self.archive(self.gradle_home / 'caches/modules-2/files-2.1/net.fabricmc.fabric-api'
                     / 'fabric-networking-api-v1' / version / 'digest' / f'fabric-networking-api-v1-{version}-sources.jar',
                     {path: 'public class ClientPlayNetworking {\n'
                      ' public static <T extends Payload> boolean registerGlobalReceiver(Id<T> type, Handler<T> handler) {\n'
                      '  return Registry.registerGlobalReceiver(type.id(), handler);\n }\n'
                      ' /**\n  * @see ClientPlayNetworking#registerGlobalReceiver(Id, Handler)\n  */\n'
                      ' public static Handler<?> unregisterGlobalReceiver(Id type) { return Registry.unregister(type); }\n}'})

        async def check():
            async with Client(create_server(Runtime(self.project))) as client:
                response = await client.call_tool('minecode.search_reference_code',
                                                  {'query': 'ClientPlayNetworking registerGlobalReceiver', 'max_results': 1})
                hit = response.structured_content['results'][0]
                self.assertEqual((hit['path'], hit['start_line']), (path, 2))
                self.assertIn('<T extends Payload> boolean registerGlobalReceiver', hit['excerpt'])
                context = await client.call_tool('minecode.get_reference_context',
                                                 {'result_id': hit['result_id'], 'context_lines': 2})
                self.assertIn('return Registry.registerGlobalReceiver', context.structured_content['results'][0]['excerpt'])
                self.assertIsNone(hit['provenance']['namespace'])
                self.assertEqual(hit['compatibility'], {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'unknown'})
        asyncio.run(check())

    def test_inheritance_does_not_guess_missing_imports_cross_packages_or_members(self):
        from minecode_runtime.local_sources import matches, snapshot
        from minecode_runtime.models import LocalReferenceArtifact
        entries = {
            'a/Child.java': 'package a;\nclass Child extends Missing {}',
            'b/Missing.java': 'package b;\nclass Missing {\n public void handleDisconnect() {}\n}',
            'a/Parent.java': 'package a;\nclass Parent {\n // handleDisconnect is undocumented here\n}',
            'a/KnownChild.java': 'package a;\nclass KnownChild extends Parent {}',
            'a/Override.java': 'package a;\nclass Override extends b.Missing {\n public void handleDisconnect() {}\n}',
            'cycle/A.java': 'package cycle;\nclass A extends B {}',
            'cycle/B.java': 'package cycle;\nclass B extends A {}',
        }
        jar = self.archive(self.root / 'negative-sources.jar', entries)
        data = snapshot(LocalReferenceArtifact(artifact_id='negative', kind='minecraft-sources', path=str(jar), scope='project'))
        for owner in ('Child', 'KnownChild', 'A'):
            with self.subTest(owner=owner):
                rows = matches(data, {owner.lower(), 'handledisconnect'}, identifiers={owner, 'handleDisconnect'})
                self.assertTrue(all(coverage <= 1 for _, _, _, coverage in rows))
        rows = sorted(matches(data, {'override', 'handledisconnect'}, identifiers={'Override', 'handleDisconnect'}),
                      key=lambda row: (-row[3], -row[0]))
        self.assertEqual(rows[0][1], 'a/Override.java')

    def test_pinned_fabric_does_not_promote_mismatched_or_unqualified_sources(self):
        from unittest.mock import patch
        from minecode_runtime.models import LocalReferenceArtifact
        artifacts = [LocalReferenceArtifact(
            artifact_id=name, kind='fabric-api-sources', path=str(self.root / (name + '.jar')),
            scope='gradle-user', minecraft_version='1.21.5',
            compatibility=compatibility,
        ) for name, compatibility in [
            ('pinned', {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'unknown'}),
            ('other-api', {'minecraft': 'exact', 'fabric_api': 'mismatch', 'mappings': 'unknown'}),
            ('other-game', {'minecraft': 'mismatch', 'fabric_api': 'exact', 'mappings': 'unknown'}),
            ('unknown-api', {'minecraft': 'exact', 'fabric_api': 'unknown', 'mappings': 'unknown'}),
            ('wrong-mappings', {'minecraft': 'exact', 'fabric_api': 'exact', 'mappings': 'mismatch'}),
        ]]
        engine = Retrieval(self.project, cache_root=self.root / 'references', sources={})
        with patch('minecode_runtime.retrieval.inspect') as profile, \
             patch('minecode_runtime.retrieval.local_snapshot', side_effect=lambda a: {
                 'kind': 'local-archive', 'revision': 'fixture', 'retrieved_at': 'fixture', 'id': a.artifact_id}), \
             patch('minecode_runtime.retrieval.local_matches', side_effect=lambda s, t, **kw:
                   [(1, 'Example.java', 1, 1)] if s['id'] == 'pinned' else [(500, 'Example.java', 1, 100)]), \
             patch('minecode_runtime.retrieval.local_read', return_value='class Example {}'):
            profile.return_value.local_reference_limitations = []
            profile.return_value.local_reference_artifacts = artifacts
            result = engine.search_reference_code('Example', max_results=1)
        self.assertEqual(result.results[0].source_id, 'pinned')
        self.assertTrue(result.truncated)

    def test_missing_or_malformed_or_entity_metadata_does_not_guess(self):
        self.jar()
        self.assertEqual(self.discover(), [])
        path = self.pom(self.dependency())
        path.write_text('<broken')
        self.assertEqual(self.discover(), [])
        self.pom(self.dependency(), prefix='<!DOCTYPE project [<!ENTITY x "test">]>')
        self.assertEqual(self.discover(), [])
        path.write_text('x' * 256_001)
        self.assertEqual(self.discover(), [])

    def test_unresolved_unsafe_and_non_runtime_dependencies_are_excluded(self):
        self.jar()
        for version, extra in [('${module.version}', ''), ('../escape', ''), ('[1,2)', ''),
                               ('1.2.3+abc', '<scope>test</scope>'),
                               ('1.2.3+abc', '<optional>true</optional>'),
                               ('1.2.3+abc', '<classifier>other</classifier>')]:
            with self.subTest(version=version, extra=extra):
                self.pom(self.dependency(version=version, extra=extra))
                self.assertEqual(self.discover(), [])

    def test_conflicting_poms_do_not_choose_a_version(self):
        self.pom(self.dependency())
        self.pom(self.dependency(version='2.0.0'), digest='second')
        self.jar()
        self.jar(version='2.0.0')
        self.assertEqual(self.discover(), [])

    def test_parent_identity_and_limits(self):
        self.jar()
        path = self.pom(self.dependency())
        path.write_text(path.read_text().replace('<version>0.119.5+1.21.5', '<version>0.100.0+1.20.1'))
        self.assertEqual(self.discover(), [])
        self.pom(''.join(self.dependency(f'fabric-module-{i}') for i in range(65)))
        self.assertEqual(self.discover(), [])

    def test_symlinked_metadata_is_not_followed(self):
        path = self.pom(self.dependency())
        external = self.root / 'external.pom'
        external.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(external)
        except OSError:
            self.skipTest('Symlink creation unavailable')
        self.jar()
        self.assertEqual(self.discover(), [])
