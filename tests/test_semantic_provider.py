"""Adapter/protocol tests; these do not assert real compiler symbol resolution."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import unittest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from minecode_runtime.semantic_provider import create_server, navigate, read_source
from minecode_runtime.providers import Providers, ProviderConfig
from minecode_runtime.lsp_client import LspClient

FIXTURE = Path(__file__).parent / 'fixtures' / 'semantic' / 'lsp_fixture.py'


class SemanticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.file = self.root / 'Example.kt'
        self.file.write_text('first', encoding='utf-8')

    def command(self, mode='normal'):
        return [sys.executable, str(FIXTURE.resolve()), mode]

    async def query(self, operations=None, mode='normal', **kwargs):
        return await navigate(self.root, self.command(mode), 'Example.kt', 0, 0,
                              operations or ['definition', 'references', 'implementation', 'incoming_calls', 'outgoing_calls'],
                              kwargs.get('max_results', 10), kwargs.get('timeout_seconds', 5))

    async def test_protocol_locations_calls_and_no_false_completeness(self):
        result = await self.query()
        self.assertTrue(all(item.status == 'completed' for item in result.results), result)
        self.assertIn('targetSelectionRange', result.results[0].items[0])
        self.assertIn('from', result.results[3].items[0]['call'])
        self.assertIn('to', result.results[4].items[0]['call'])
        self.assertFalse(result.complete)
        self.assertEqual(result.index_state, 'unknown')
        self.assertNotIn('DO_NOT_EXPOSE', result.model_dump_json())

    async def test_saved_edits_are_resent_and_hash_changes(self):
        first = await self.query(['incoming_calls'])
        self.file.write_text('second', encoding='utf-8')
        second = await self.query(['incoming_calls'])
        self.assertNotEqual(first.source_sha256, second.source_sha256)
        self.assertEqual(second.results[0].items[0]['symbol']['name'], 'second')

    async def test_unsupported_is_distinct_from_empty(self):
        result = await self.query(mode='unsupported')
        self.assertEqual(result.results[2].status, 'unsupported')
        self.assertEqual(result.results[0].status, 'completed')

    async def test_limits(self):
        result = await self.query(['references'], mode='many', max_results=2)
        self.assertEqual(len(result.results[0].items), 2)
        self.assertTrue(result.results[0].truncated)
        oversized = await self.query(mode='oversize')
        self.assertTrue(all(item.status == 'failed' for item in oversized.results))

    async def test_timeout_and_backend_errors(self):
        result = await self.query(mode='slow', timeout_seconds=1)
        self.assertTrue(all(item.status == 'timed_out' for item in result.results))
        failed = await self.query(mode='error')
        self.assertTrue(all(item.status == 'failed' for item in failed.results))
        self.assertNotIn('DO_NOT_EXPOSE', failed.model_dump_json())

    def test_path_and_utf16_boundaries(self):
        self.file.write_text('a\U0001f600b\n', encoding='utf-8')
        read_source(self.root, 'Example.kt', 0, 3)
        read_source(self.root, 'Example.kt', 1, 0)
        for line, column in [(0, 2), (0, 5), (-1, 0), (2, 0)]:
            with self.subTest(line=line, column=column), self.assertRaises(ValueError):
                read_source(self.root, 'Example.kt', line, column)
        with self.assertRaises(ValueError):
            read_source(self.root, str(FIXTURE.resolve()), 0, 0)

    async def test_existing_provider_integration_and_mcp_validation(self):
        server = create_server(self.root, self.command())
        config = ProviderConfig(id='semantic-code', command=sys.executable,
                                capabilities={'semantic_navigation': 'navigate_symbol'})
        providers = Providers([config], allow_execution=True, client_factory=lambda *a, **k: Client(server))
        result = await providers.call('semantic_navigation', {
            'file': 'Example.kt', 'line': 0, 'column': 0, 'operations': ['definition']})
        self.assertTrue(result.success, result)
        self.assertEqual(json.loads(result.text)['results'][0]['status'], 'completed')
        async with Client(server) as client:
            invalid = await client.call_tool('navigate_symbol', {
                'file': 'Example.kt', 'line': -1, 'column': 0, 'operations': ['definition']})
            self.assertTrue(invalid.is_error)

    async def test_actual_provider_stdio_entrypoint(self):
        params = StdioServerParameters(command=sys.executable, args=[
            '-m', 'minecode_runtime.semantic_provider', '--project', str(self.root),
            '--allow-backend-execution', '--', *self.command()])
        async with Client(params) as client:
            result = await client.call_tool('navigate_symbol', {
                'file': 'Example.kt', 'line': 0, 'column': 0, 'operations': ['references']})
            self.assertFalse(result.is_error, result)
            self.assertEqual(result.structured_content['results'][0]['status'], 'completed')

    async def test_missing_backend_returns_failed_evidence(self):
        result = await navigate(self.root, ['minecode-no-such-lsp-executable'], 'Example.kt',
                                0, 0, ['definition'], 10, 5)
        self.assertEqual(result.results[0].status, 'failed')
        self.assertFalse(result.complete)

    async def test_cancellation_during_shutdown_stops_backend(self):
        client = LspClient(self.root, self.command('slow_shutdown'))
        await client.__aenter__()
        try:
            cleanup = asyncio.create_task(client.__aexit__(None))
            await asyncio.sleep(0.1)
            cleanup.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await cleanup
            self.assertIsNotNone(client.process.returncode)
        finally:
            if client.process.returncode is None:
                await client.__aexit__(RuntimeError)
