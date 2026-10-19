"""Offline provider and Minecraft diagnosis contracts."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import yaml
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.server import MCPServer
from minecode_runtime.providers import Providers, ProviderConfig, bounded_result
from minecode_runtime.failure_evidence import diagnose, sanitize, FailureEnvironment, RepairEvidence
from minecode_runtime.registry import load_registry, rank, evidence
from minecode_runtime.gradle import Runtime
from minecode_runtime.server import create_server


class RegistryTests(unittest.TestCase):
    def test_registry_metadata_and_curated_sources(self):
        sources=load_registry()
        self.assertTrue({'sodium','viafabricplus','viaversion','owo-lib','cloth-config','mixinextras','mouse-tweaks','fabric-carpet'} <= sources.keys())
        for s in sources.values():
            self.assertIn('minecraft',s['environment'])
            self.assertFalse(s['code_reuse']['allowed'])
        self.assertEqual(sources['sodium']['license']['reported'],'PolyForm-Shield-1.0.0')
        self.assertEqual(sources['cloth-config']['license']['reported'],'LGPL-3.0-or-later')
        self.assertEqual(sources['owo-lib']['environment']['minecraft'],'1.21')
        self.assertEqual(sources['cloth-config']['environment']['mappings'],'mojang-official')
        self.assertIsNone(sources['mixinextras']['environment']['minecraft'])
        self.assertTrue({'fancymenu','vulcan-config','clean-phobos-1-9-0'}.isdisjoint(sources))

    def test_automation_reference_is_relevant_without_claiming_target_version(self):
        sources = load_registry()
        ranked = rank(sources, 'temporary inventory ownership arbitration cancellation')
        self.assertIn('liquidbounce', [item.source_id for item in ranked[:3]])
        item = evidence(sources['liquidbounce'])
        self.assertEqual(item.environment['minecraft'], '26.3')
        self.assertEqual(item.provenance['review']['revision'], '8c674cf33a61ea8f04f2a6f001a81894223b3ab0')
        self.assertFalse(item.code_reuse['generated_derivation_allowed'])
        self.assertNotIn('liquidbounce', [item.source_id for item in rank(sources, 'screen blur renderBackground')])
        self.assertNotIn('liquidbounce', [item.source_id for item in rank(
            sources, 'inventory ownership', minecraft_version='1.21.11', strict_version=True)])

    def test_exact_12111_api_identity_ranks_ahead_of_older_guidance(self):
        sources = load_registry()
        for query, expected in [('screen blur renderBackground', 'yarn-screen-12111'),
                                ('interaction syncSelectedSlot prediction', 'yarn-interaction-12111')]:
            with self.subTest(query=query):
                result = rank(sources, query, knowledge=True, minecraft_version='1.21.11')
                self.assertEqual(result[0].source_id, expected)
                self.assertEqual(result[0].environment['mappings'], 'yarn')
                self.assertEqual(result[0].environment['mappings_version'], '1.21.11+build.3')

    def test_yarn_family_does_not_claim_mapping_build_match(self):
        sources = load_registry()
        result = rank(sources, 'Screen render', knowledge=True, minecraft_version='1.21.11', mappings='yarn')[0]
        self.assertEqual(result.source_id, 'yarn-screen-12111')
        self.assertEqual(result.compatibility['mappings'], 'exact-declared')
        self.assertNotIn('mappings_version', result.compatibility)
        for version, expected in [('1.21.11+build.3', 'exact-declared'), ('1.21.11+build.2', 'mismatch')]:
            with self.subTest(version=version):
                item = rank({'screen': sources['yarn-screen-12111']}, 'Screen render', knowledge=True,
                            mappings='yarn', mappings_version=version)[0]
                self.assertEqual(item.compatibility['mappings_version'], expected)

    def test_legacy_yarn_label_is_normalized_without_mutating_registry(self):
        source = copy.deepcopy(load_registry()['yarn-screen-12111'])
        source['environment'] = {'minecraft': '1.21.11', 'mappings': 'yarn-1.21.11+build.3'}
        item = rank({'screen': source}, 'Screen render', knowledge=True, mappings='yarn-1.21.11+build.3')[0]
        self.assertEqual(item.compatibility['mappings'], 'exact-declared')
        self.assertEqual(item.compatibility['mappings_version'], 'exact-declared')
        self.assertEqual(source['environment']['mappings'], 'yarn-1.21.11+build.3')
        source['environment']['mappings'] = 'yarn'
        item = rank({'screen': source}, 'Screen render', knowledge=True, mappings='yarn',
                    mappings_version='1.21.11+build.3')[0]
        self.assertEqual(item.compatibility['mappings_version'], 'unknown')

    def test_duplicate_urls_rejected(self):
        root=Path(__file__).resolve().parents[1]/'references/sources'
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            data=yaml.safe_load((root/'sources.yaml').read_text(encoding='utf-8'))
            dup=copy.deepcopy(data['sources'][0]);dup['id']='alias';dup['url']=dup['canonical_url']=data['sources'][0]['canonical_url']+'.git/'
            data['sources'].append(dup)
            (p/'sources.yaml').write_text(yaml.safe_dump(data))
            (p/'developer-knowledge.json').write_text((root/'developer-knowledge.json').read_text(encoding='utf-8'),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Duplicate source URL'):load_registry(p)

    def test_quality_coverage_independent_of_compatibility(self):
        r=load_registry()
        selected=rank(r,'protocol translation packet version abstraction')
        self.assertIn('viaversion',[v.source_id for v in selected[:3]])
        self.assertTrue(any('coverage' in reason for item in selected for reason in item.reasons))

    def test_knowledge_trust_and_version(self):
        r=load_registry()
        self.assertEqual(evidence(r['mixinextras-wrap-operation']).trust,'maintainer-documentation')
        self.assertEqual(evidence(r['yarn-screen-1211']).trust,'primary')
        self.assertIn('fabric-hud-rendering',[s.source_id for s in rank(r,'hud rendering',knowledge=True)])
        results=rank(r,'release migration',knowledge=True,minecraft_version='26.3',strict_version=True)
        self.assertEqual(results[0].source_id,'fabric-release-263')


class FailureTests(unittest.TestCase):
    def test_mixin_context_and_repair_evidence(self):
        result=diagnose('Header\nCaused by: org.spongepowered.asm.mixin.throwables.InvalidMixinException: target missing',FailureEnvironment(minecraft='1.21',mappings='yarn'),repair=RepairEvidence(attempted='Update target signature',result='build_passed'))
        self.assertEqual(result.category,'mixin')
        self.assertEqual(result.mixin_failure,'unclassified')
        self.assertIn('line 2:',result.evidence[0])
        self.assertEqual(result.environment.minecraft,'1.21')
        self.assertEqual(result.attempted_repair.result,'build_passed')
        self.assertIn('minecraft 1.21',result.next_step)
        self.assertTrue(any('does not prove' in note for note in result.remaining_uncertainty))

    def test_mixin_version_migration_preserves_selector_and_environment(self):
        result=diagnose(
            'Caused by: InvalidInjectionException: @Inject annotation on renderHud could not find any targets matching '
            'renderHud(Lnet/minecraft/client/gui/DrawContext;F)V in net.minecraft.client.gui.hud.InGameHud',
            FailureEnvironment(minecraft='1.21.4',loader='fabric',mappings='yarn-1.21.4+build.8',side='client'))
        self.assertEqual(result.mixin_failure,'target-not-found')
        self.assertEqual(result.mixin_details['target_class'],'net.minecraft.client.gui.hud.InGameHud')
        self.assertEqual(result.mixin_details['target_member'],'renderHud')
        self.assertEqual(result.mixin_details['descriptor'],'(Lnet/minecraft/client/gui/DrawContext;F)V')
        for context in ('minecraft 1.21.4','loader fabric','mappings yarn-1.21.4+build.8','side client'):
            self.assertIn(context,result.next_step)
        self.assertIn('current-version target',result.next_step)
        self.assertNotIn('renamed to',result.root_cause_hypothesis)

    def test_networking_details_and_runtime_uncertainty(self):
        result=diagnose(
            'Caused by: java.lang.IllegalArgumentException: Cannot register handler as no payload type '
            'has been registered with name "example:update" for SERVERBOUND CONFIGURATION')
        self.assertEqual(result.category,'networking-registration')
        self.assertEqual(result.networking_failure,'payload-registration')
        self.assertEqual(result.networking_details,{
            'payload_id':'example:update','direction':'C2S','phase':'configuration'})
        self.assertTrue(any('does not prove payload delivery' in note
                            for note in result.remaining_uncertainty))

    def test_sanitization(self):
        raw='token=supersecret\nAuthorization: Bearer ABCDEF\nC:\\Users\\Alice\\project\\Foo.java:12: error: cannot find symbol\nusername=Alice\nConnected to 192.168.1.2:25565\nhttps://private.example.com/token\n[CHAT] Alice: confidential\n'
        clean=sanitize(raw)
        for secret in ('supersecret','ABCDEF','Alice','192.168.1.2','private.example.com','confidential'):
            self.assertNotIn(secret,clean)
        result=diagnose(raw)
        self.assertEqual(result.category,'compiler')
        self.assertEqual(result.migration_layer,'ordinary-java')
        self.assertNotIn('Alice',result.model_dump_json())
        self.assertNotIn('secret123',sanitize('--accessToken secret123 --username secret123'))
        self.assertNotIn('private@example.net',sanitize('private@example.net'))
        credentials='api_key=APISECRET password=PASSWORD secret=SECRET ghp_abcdefghijklmnopqrstuvwxyz123456 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature'
        for secret in ('APISECRET','PASSWORD','SECRET','ghp_abcdefghijklmnopqrstuvwxyz123456','eyJhbGciOiJIUzI1NiJ9'):
            self.assertNotIn(secret,sanitize(credentials))

    def test_sanitization_preserves_diagnostic_evidence(self):
        raw=(
            'Caused by: java.io.IOException: Failed to load some.package.net.SomeClass\n'
            'Mixin apply failed in example.dev.mixin.Handler at MixinExample.java:42\n'
            'Minecraft version 1.21.4.0 with mappings yarn-1.21.4+build.8\n'
            'tokenizer=MixinToken\n'
            'C:\\Users\\Alice\\project\\src\\main\\java\\example\\MixinExample.java:12\n'
            '/home/alice/project/src/main/java/example/Foo.java:34\n'
        )
        clean=sanitize(raw)
        for evidence in ('java.io.IOException','some.package.net.SomeClass','example.dev.mixin.Handler',
                         'MixinExample.java:42','1.21.4.0','yarn-1.21.4+build.8','tokenizer=MixinToken',
                         r'src\main\java\example\MixinExample.java:12','src/main/java/example/Foo.java:34'):
            self.assertIn(evidence,clean)
        self.assertNotIn(r'C:\Users\Alice',clean)
        self.assertNotIn('/home/alice',clean)
        self.assertEqual(sanitize('Connected to private.example.com:25565'), 'Connected to [host]')

    def test_integrated_provider_license_metadata(self):
        path=Path(__file__).resolve().parents[1]/'integrations/providers.json'
        providers=json.loads(path.read_text())['providers']
        self.assertEqual({p['id'] for p in providers},{'minecraft-dev-mcp','mcpfabric'})
        for provider in providers:
            self.assertEqual(provider['license'],'MIT')
            self.assertIn(provider['revision'],provider['license_url'])
            self.assertFalse(provider['code_copied'])

    def test_samples_bounds_and_unknown(self):
        for text,expected in [('java.lang.OutOfMemoryError: heap','memory'),('GLFW error: driver','graphics-startup'),('Cannot load class X in environment DEDICATED_SERVER','side-source-set'),('release version 25 not supported','java-version')]:
            self.assertEqual(diagnose(text).category,expected)
        unknown=diagnose('all fine')
        self.assertEqual(unknown.category,'unknown')
        self.assertEqual(unknown.confidence,'unknown')
        with self.assertRaises(ValueError):diagnose('x'*128001)
        result=diagnose('\n'.join(['Caused by: InvalidMixinException: missing']*500))
        self.assertLessEqual(len(result.evidence),6)


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.provider=MCPServer('OriginalFixture',version='0.1')
        @self.provider.tool(name='fixture_lookup')
        def lookup(query: str='x') -> str:
            return 'Original fixture '+query
        @self.provider.tool(name='fixture_failure')
        def failure() -> str:
            raise ValueError('No game bridge')
        self.config=ProviderConfig(id='replacement',command=sys.executable,capabilities={'source_lookup':'fixture_lookup'})
        self.providers=Providers([self.config],allow_execution=True,client_factory=lambda *a,**k:Client(self.provider))

    async def test_health_schema_and_replacement(self):
        result=await self.providers.health('replacement','source_lookup')
        self.assertTrue(result.installed and result.reachable)
        self.assertEqual(result.status,'healthy')
        self.assertEqual(result.capabilities,['source_lookup'])
        self.assertIn('query',json.loads(result.schema_excerpt)['properties'])
        call=await self.providers.call('source_lookup',{'query':'hello'})
        self.assertTrue(call.success)
        self.assertIn('hello',call.text)

    async def test_absent_disabled_missing_and_unknown_capability(self):
        self.assertIsNone((await Providers().health('minecraft-dev-mcp')).installed)
        self.assertEqual((await Providers([self.config]).health('replacement')).status,'unavailable')
        missing=self.config.model_copy(update={'command':'minecode-nonexistent-binary-123'})
        self.assertFalse((await Providers([missing],allow_execution=True).health('replacement')).installed)
        self.assertFalse((await self.providers.call('unconfigured',{})).success)
        self.assertFalse((await Providers([missing],allow_execution=True).call('source_lookup',{})).success)

    async def test_degraded_backend(self):
        cfg=self.config.model_copy(update={'health_capability':'status','capabilities':{'status':'fixture_failure'}})
        manager=Providers([cfg],allow_execution=True,client_factory=lambda *a,**k:Client(self.provider))
        h=await manager.health('replacement')
        self.assertTrue(h.reachable)
        self.assertEqual(h.status,'degraded')
        cfg.health_capability='not_advertised'
        self.assertEqual((await manager.health('replacement')).status,'degraded')

    async def test_bounded_output_and_arguments(self):
        result=await self.providers.call('source_lookup',{'query':'x'*12000})
        self.assertTrue(result.truncated)
        self.assertLessEqual(len(result.text),8000)
        self.assertIn('oversized log line omitted',result.text)
        with self.assertRaises(ValueError):await self.providers.call('source_lookup',{'query':'x'*16001})
        response=SimpleNamespace(structured_content=None,content=[SimpleNamespace(type='image',data='secret'),SimpleNamespace(type='text',text='safe')])
        self.assertEqual(bounded_result(response),('safe',False))

    async def test_provider_timeout(self):
        @self.provider.tool(name='slow')
        async def slow() -> str:
            await asyncio.sleep(3)
            return 'late'
        cfg=self.config.model_copy(update={'capabilities':{'slow':'slow'}})
        manager=Providers([cfg],allow_execution=True,client_factory=lambda *a,**k:Client(self.provider))
        self.assertEqual((await manager.call('slow',{},timeout_seconds=1)).status,'timed_out')

    async def test_missing_advertised_tool(self):
        self.config.capabilities={'absent':'not_advertised'}
        self.assertEqual((await self.providers.call('absent',{})).status,'unavailable')

    def test_config_validation(self):
        with self.assertRaises(ValueError):Providers([self.config,self.config])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'providers.json';p.write_text(json.dumps({'providers':[self.config.model_dump()]}))
            self.assertEqual(len(Providers.from_file(p).configs),1)
            p.write_text('x'*65537)
            with self.assertRaises(ValueError):Providers.from_file(p)

    def test_fabric_agent_disabled(self):
        captured=[]
        config=ProviderConfig(id='mcpfabric',command=sys.executable,env={'MCPFABRIC_AGENT':'true'})
        Providers([config],client_factory=lambda params,**kw:captured.append(params)).client(config,1)
        self.assertEqual(captured[0].env['MCPFABRIC_AGENT'],'false')

    @unittest.skipUnless(os.name == 'nt', 'Windows executable search regression')
    def test_provider_ignores_project_executable_during_path_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);project=root/'project';trusted=root/'trusted'
            project.mkdir();trusted.mkdir()
            fake=project/'provider.exe';expected=trusted/'provider.exe'
            fake.write_bytes(b'fake project executable')
            expected.write_bytes(b'controlled PATH executable')
            captured=[]
            config=ProviderConfig(id='replacement',command='provider',cwd=str(project))
            with patch.dict(os.environ,{'PATH':str(trusted),'PATHEXT':'.EXE'},clear=False):
                Providers([config],client_factory=lambda params,**kw:captured.append(params)).client(config,1)
        self.assertEqual(Path(captured[0].command),expected.resolve())
        self.assertNotEqual(Path(captured[0].command),fake.resolve())

    async def test_new_tools_real_mcp_schemas(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            async with Client(create_server(Runtime(root),providers=self.providers)) as c:
                tools={t.name:t for t in (await c.list_tools()).tools}
                calls=[('provider_status',{'provider':'replacement'}),('call_provider',{'capability':'source_lookup','arguments':{'query':'bounded'}}),('analyze_runtime_failure',{'output':'InvalidMixinException: missing'})]
                for name,args in calls:
                    result=await c.call_tool('minecode.'+name,args)
                    self.assertFalse(result.is_error,result.content)
                    Draft202012Validator(tools['minecode.'+name].output_schema).validate(result.structured_content)
            self.assertEqual(list(root.iterdir()),[])
