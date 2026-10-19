"""Optional, explicitly configured stdio providers; no installer or agent runner."""
import asyncio
import json
import os
from pathlib import Path
from typing import Literal
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from pydantic import Field, field_validator
from .executables import resolve_executable
from .models import ResultModel
from .diagnostics import bounded_log
from .output_safety import sanitize, sanitize_data

CAPABILITIES = {
    'minecraft-dev-mcp': {
        'source_lookup': 'get_minecraft_source', 'source_search': 'search_minecraft_code',
        'mapping_translation': 'find_mapping', 'version_comparison': 'compare_versions',
        'jar_analysis': 'analyze_mod_jar', 'mixin_validation': 'analyze_mixin',
        'access_widener_validation': 'validate_access_widener',
        'access_transformer_validation': 'validate_access_transformer',
        'registry_inspection': 'get_registry_data',
    },
    'mcpfabric': {'game_status': 'get_status', 'player_state': 'get_player'},
}
FALLBACKS = {
    'source_lookup': 'Inspect locally available project/dependency source with targeted file tools.',
    'source_search': 'Search local project source or version-qualified cached archives with MineCode reference retrieval.',
    'mixin_validation': 'Use local source inspection, build and bounded runClient; no equivalent static validator.',
    'game_status': 'Inspect fresh runClient logs; this is not equivalent to structured game observation.',
}


class ProviderConfig(ResultModel):
    id: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{0,79}$')
    command: str = Field(min_length=1, max_length=2048)
    args: list[str] = Field(default_factory=list, max_length=32)
    env: dict[str, str] = Field(default_factory=dict, max_length=32)
    env_names: list[str] = Field(default_factory=list, max_length=32)
    cwd: str | None = None
    capabilities: dict[str, str] = Field(default_factory=dict, max_length=32)
    health_capability: str | None = None

    @field_validator('capabilities')
    @classmethod
    def validate_capabilities(cls, values):
        import re
        if any(not re.fullmatch(r'[a-zA-Z0-9_.-]{1,80}', x) for pair in values.items() for x in pair):
            raise ValueError('Capability and tool names must be short identifiers')
        return values


class ProviderHealth(ResultModel):
    provider: str
    installed: bool | None = None
    reachable: bool = False
    version: str | None = None
    status: Literal['healthy', 'degraded', 'unavailable'] = 'unavailable'
    capabilities: list[str] = Field(default_factory=list)
    message: str = ''
    schema_excerpt: str = ''
    schema_truncated: bool = False


class ProviderResult(ResultModel):
    provider: str | None = None
    capability: str
    success: bool = False
    status: Literal['completed', 'unavailable', 'failed', 'timed_out'] = 'unavailable'
    text: str = ''
    truncated: bool = False
    fallback: str = ''
    untrusted: Literal[True] = True


def bounded_result(result, limit=8000):
    # Only text/structured data enters agent context; never inline image/base64 payloads.
    if result.structured_content is not None:
        data, omitted = sanitize_data(result.structured_content)
        clean = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        text = '\n'.join(block.text for block in result.content if block.type == 'text')
        bounded, omitted = bounded_log(text)
        clean = sanitize(bounded)
    return clean[:limit], omitted or len(clean) > limit


class Providers:
    def __init__(self, configs=(), *, allow_execution=False, client_factory=Client):
        self.configs = {c.id: c for c in configs}
        if len(self.configs) != len(configs) or len(configs) > 8:
            raise ValueError('Use at most eight distinct providers')
        self.allow_execution = allow_execution
        self.client_factory = client_factory
        self.lock = asyncio.Lock()

    @classmethod
    def from_file(cls, path: Path | None, *, allow_execution=False):
        if path is None:
            return cls(allow_execution=allow_execution)
        if path.stat().st_size > 65536:
            raise ValueError('Provider configuration exceeds 64 KiB')
        raw = json.loads(path.read_text(encoding='utf-8'))
        if set(raw) != {'providers'} or not isinstance(raw['providers'], list):
            raise ValueError('Expected a providers list')
        return cls([ProviderConfig.model_validate(c) for c in raw['providers']], allow_execution=allow_execution)

    def mapping(self, config):
        return config.capabilities or CAPABILITIES.get(config.id, {})

    def resolved_config(self, config: ProviderConfig) -> ProviderConfig | None:
        command = resolve_executable(config.command, blocked_dirs=(Path.cwd(), config.cwd))
        return config.model_copy(update={'command': command}) if command is not None else None

    def client(self, config, timeout):
        config = self.resolved_config(config)
        if config is None:
            raise FileNotFoundError('Configured provider executable is missing')
        env = {name: os.environ[name] for name in config.env_names if name in os.environ}
        env.update(config.env)
        if config.id == 'mcpfabric':
            # The upstream agent/memory/goals subsystem is outside MineCode's scope.
            env.update(MCPFABRIC_AGENT='false', MCPFABRIC_TRANSPORT='stdio')
        params = StdioServerParameters(command=config.command, args=config.args, env=env, cwd=config.cwd)
        return self.client_factory(params, read_timeout_seconds=timeout)

    async def catalog(self, client):
        found, cursor = {}, None
        for _ in range(3):
            page = await client.list_tools(cursor=cursor)
            for tool in page.tools:
                if len(found) >= 100:
                    return found
                found[tool.name] = tool
            cursor = page.next_cursor
            if not cursor:
                break
        return found

    async def health(self, provider, capability=None):
        result = ProviderHealth(provider=provider)
        config = self.configs.get(provider)
        if config is None:
            result.message = 'Not configured; installation state unknown. Native workflow remains available.'
            return result
        config = self.resolved_config(config)
        result.installed = config is not None
        if not result.installed or not self.allow_execution:
            result.message = 'Executable missing.' if not result.installed else 'Provider launch requires --allow-provider-execution.'
            return result
        assert config is not None
        try:
            async with self.lock, asyncio.timeout(20):
                async with self.client(config, 15) as client:
                    result.reachable = True
                    result.version = client.server_info.version[:100] if client.server_info else None
                    tools = await self.catalog(client)
                    mapping = self.mapping(config)
                    result.capabilities = sorted(c for c, t in mapping.items() if t in tools)
                    result.status = 'healthy' if result.capabilities else 'degraded'
                    result.message = 'MCP handshake and selected tool discovery succeeded; capabilities are advertised, not behavior-verified.'
                    probe = config.health_capability or ('game_status' if config.id == 'mcpfabric' else None)
                    if probe and probe not in result.capabilities:
                        result.status = 'degraded'
                        result.message = 'MCP reachable, but the configured backend health capability is missing.'
                    if probe and probe in result.capabilities:
                        check = await client.call_tool(mapping[probe], {})
                        if check.is_error:
                            result.status = 'degraded'
                            result.message = 'MCP reachable, but backend health call failed; game/credentials may be unavailable.'
                    if capability in result.capabilities:
                        schema = json.dumps(tools[mapping[capability]].input_schema)
                        result.schema_excerpt, result.schema_truncated = schema[:8000], len(schema) > 8000
        except Exception as exc:
            result.status = 'degraded' if result.reachable else 'unavailable'
            result.message = 'Provider probe failed (' + type(exc).__name__ + '); check local installation/configuration. Details omitted to protect credentials.'
        return result

    async def call(self, capability, arguments, provider=None, timeout_seconds=60):
        if not 1 <= timeout_seconds <= 120 or len(json.dumps(arguments)) > 16000:
            raise ValueError('Provider calls require 1–120 seconds and at most 16,000 argument characters')
        result = ProviderResult(capability=capability, fallback=FALLBACKS.get(capability, 'No equivalent native capability; report unavailable and inspect local evidence.'))
        candidates = [c for c in self.configs.values() if capability in self.mapping(c) and (provider is None or c.id == provider)]
        if not self.allow_execution or not candidates:
            result.text = 'Optional capability not configured or provider execution disabled.'
            return result
        # Deterministic configured order; do not retry another provider after a potentially expensive call.
        available = []
        for candidate in candidates:
            resolved = self.resolved_config(candidate)
            if resolved is not None:
                available.append(resolved)
        if not available:
            result.text = 'Configured provider executables are missing.'
            return result
        config = available[0]
        result.provider = config.id
        try:
            async with self.lock, asyncio.timeout(timeout_seconds):
                async with self.client(config, timeout_seconds) as client:
                    tools = await self.catalog(client)
                    name = self.mapping(config)[capability]
                    if name not in tools:
                        result.text = 'Configured capability is not advertised by this provider version.'
                        return result
                    response = await client.call_tool(name, arguments)
                    result.text, result.truncated = bounded_result(response)
                    result.success = not response.is_error
                    result.status = 'completed' if result.success else 'failed'
        except TimeoutError:
            result.status, result.text = 'timed_out', 'Provider call exceeded the time budget.'
        except Exception as exc:
            result.status, result.text = 'failed', 'Provider call failed (' + type(exc).__name__ + '); details omitted to protect credentials.'
        return result
