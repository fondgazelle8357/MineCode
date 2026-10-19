"""Synthetic canaries verify output handling without using real credentials."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from minecode_runtime.gradle import capture
from minecode_runtime.output_safety import sanitize
from minecode_runtime.providers import bounded_result
from minecode_runtime.gradle import Runtime
from minecode_runtime.server import create_server
from mcp import Client


class OutputSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def build_diagnosis(self, output, environment=None):
        with tempfile.TemporaryDirectory() as directory:
            async with Client(create_server(Runtime(Path(directory)))) as client:
                result = await client.call_tool('minecode.analyze_build_failure',
                                               {'output': output, 'environment': environment})
                self.assertFalse(result.is_error, result.content)
                return result.structured_content

    async def test_build_diagnosis_redacts_every_model_visible_field(self):
        raw = (r'C:\Users\PRIVATE_CANARY\project\src\HudMixin.java:42: error: cannot find symbol '
               'token=TOKEN_CANARY password=PASSWORD_CANARY api_key=KEY_CANARY\n'
               'import net.fabricmc.fabric.api.client.networking.v1.ClientPlayNetworking;\n'
               'symbol: method registerGlobalReceiver\nlocation: class ClientPlayNetworking\n')
        result = await self.build_diagnosis(raw, {'java': '21 token=ENV_CANARY'})
        text = json.dumps(result)
        for value in ('PRIVATE_CANARY', 'TOKEN_CANARY', 'PASSWORD_CANARY', 'KEY_CANARY', 'ENV_CANARY'):
            self.assertNotIn(value, text)
        self.assertEqual(result['category'], 'fabric-api')
        self.assertEqual(result['affected_line'], 42)
        self.assertIn('src\\HudMixin.java', result['affected_file'])
        self.assertIn('registerGlobalReceiver', text)
        self.assertIn('[redacted]', text)

    async def test_build_diagnosis_preserves_mixin_selector_and_version_evidence(self):
        result = await self.build_diagnosis(
            "InvalidInjectionException: @Inject on draw could not find any targets matching "
            "'render(Lnet/minecraft/client/gui/DrawContext;F)V' in net.minecraft.client.gui.hud.InGameHud",
            {'minecraft': '1.21.11', 'mappings': 'yarn-1.21.11+build.3'})
        self.assertEqual(result['category'], 'mixin')
        self.assertEqual(result['mixin_failure'], 'target-not-found')
        self.assertIn('(Lnet/minecraft/client/gui/DrawContext;F)V', json.dumps(result['mixin_details']))
        self.assertEqual(result['environment']['minecraft'], '1.21.11')
        self.assertEqual(result['environment']['mappings'], 'yarn-1.21.11+build.3')

    async def test_build_diagnosis_redaction_keeps_environment_schema_bounds(self):
        result = await self.build_diagnosis('Example.java:7: error: cannot find symbol',
                                           {'java': 'token=x ' * 10})
        self.assertLessEqual(len(result['environment']['java']), 80)
        self.assertNotIn('token=x', json.dumps(result))
        self.assertEqual(result['affected_line'], 7)

    async def captured(self, content):
        stream = asyncio.StreamReader()
        stream.feed_data(content)
        stream.feed_eof()
        return await capture(stream)

    async def test_secret_label_split_across_reads_is_redacted(self):
        raw = b'ok\n' * 2728 + b'password=AUDIT_CANARY\nExample.java:12: error: cannot find symbol\n'
        text, truncated = await self.captured(raw)
        self.assertNotIn('AUDIT_CANARY', text)
        self.assertIn('[redacted]', text)
        self.assertIn('Example.java:12', text)
        self.assertFalse(truncated)

    async def test_oversized_line_is_omitted_without_exposing_its_tail(self):
        raw = b'password=' + b'x' * 150000 + b'AUDIT_CANARY\nCaused by: InvalidMixinException: missing\n'
        text, truncated = await self.captured(raw)
        self.assertTrue(truncated)
        self.assertNotIn('AUDIT_CANARY', text)
        self.assertIn('oversized log line omitted', text)
        self.assertIn('InvalidMixinException', text)

    async def test_unterminated_final_line_is_sanitized(self):
        text, truncated = await self.captured(b'Authorization: Bearer AUDIT_CANARY')
        self.assertNotIn('AUDIT_CANARY', text)
        self.assertFalse(truncated)

    async def test_tail_limit_preserves_sanitized_diagnostic_lines(self):
        raw = b'ordinary build progress\n' * 4000 + (
            b'api_key=AUDIT_CANARY\nC:\\Users\\PrivateUser\\project\\src\\Example.java:42: error\n')
        text, truncated = await self.captured(raw)
        self.assertTrue(truncated)
        self.assertLessEqual(len(text), 64000)
        self.assertNotIn('AUDIT_CANARY', text)
        self.assertNotIn('PrivateUser', text)
        self.assertIn(r'src\Example.java:42', text)

    def test_quoted_credentials_and_authorization_json(self):
        raw = json.dumps({'password': 'AUDIT CANARY spaced', 'Authorization': 'Bearer AUTH_CANARY',
                          'nested': {'api_key': 'ESCAPED"CANARY'}, 'class': 'net.minecraft.client.MinecraftClient'})
        text = sanitize(raw)
        for secret in ('AUDIT', 'AUTH_CANARY', 'ESCAPED'):
            self.assertNotIn(secret, text)
        self.assertIn('net.minecraft.client.MinecraftClient', text)
        self.assertEqual(json.loads(text)['password'], '[redacted]')

    def test_structured_provider_data_is_sanitized_before_truncation(self):
        result = SimpleNamespace(structured_content={
            'nested': {'password': 'AUDIT_CANARY', 'source': '/home/private/project/src/Example.java:12'},
            'failure': 'InvalidMixinException: target missing',
        })
        text, truncated = bounded_result(result)
        self.assertNotIn('AUDIT_CANARY', text)
        self.assertNotIn('/home/private', text)
        self.assertIn('src/Example.java:12', text)
        self.assertIn('InvalidMixinException', text)
        self.assertFalse(truncated)

    def test_long_provider_value_cannot_survive_without_its_label(self):
        result = SimpleNamespace(structured_content={'log': 'token=' + 'x' * 9000 + 'AUDIT_CANARY', 'error': 'MixinApplyError'})
        text, truncated = bounded_result(result)
        self.assertTrue(truncated)
        self.assertNotIn('AUDIT_CANARY', text)
        self.assertIn('MixinApplyError', text)
        result = SimpleNamespace(structured_content=None, content=[
            SimpleNamespace(type='text', text='password="AUDIT CANARY spaced"\nMixinApplyError')])
        text, _ = bounded_result(result, limit=36)
        self.assertNotIn('AUDIT', text)
        self.assertLessEqual(len(text), 36)

    def test_multiline_structured_logs_keep_useful_lines_up_to_output_limit(self):
        result = SimpleNamespace(structured_content={'log': 'Useful build progress\n' * 1000})
        text, truncated = bounded_result(result)
        self.assertTrue(truncated)
        self.assertEqual(len(text), 8000)
        self.assertIn('Useful build progress', text)

    def test_provider_game_state_is_not_confused_with_a_player_name(self):
        result = SimpleNamespace(structured_content={'player': {'health': 18, 'username': 'PRIVATE_CANARY'}})
        text, _ = bounded_result(result)
        self.assertNotIn('PRIVATE_CANARY', text)
        self.assertEqual(json.loads(text)['player']['health'], 18)


if __name__ == '__main__':
    unittest.main()
