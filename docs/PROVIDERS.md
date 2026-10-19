# Optional providers

MineCode works without external providers. Configure one only when its specialized capability answers a real question. Providers are separate software with their own installation, licenses, dependencies and failure modes; no provider executable or game bridge is bundled.

## Available adapters

| Provider | Intended capability | Requirement |
| --- | --- | --- |
| [Minecraft Dev MCP](https://github.com/MCDxAI/minecraft-dev-mcp) | Minecraft-specific analysis operations exposed by the provider | Compatible separately installed server and working operation dependencies |
| [MCP Fabric](https://github.com/denfry/mcpfabric) | Operations requiring a Fabric game bridge | Compatible server, matching mod/game version and connected bridge |

The adapters expose only the existing allowlisted operations; they don't add a second agent or memory system. Exact provider metadata and reviewed revisions are in [integrations/providers.json](../integrations/providers.json).

## Configure explicitly

Use a trusted configuration outside the Minecraft project, for example:

```json
{
  "providers": [
    {
      "id": "minecraft-dev-mcp",
      "command": "/absolute/path/to/provider",
      "args": []
    }
  ]
}
```

Check the actual configuration structure in the [runtime reference](../mcp/README.md) and [provider metadata](../integrations/providers.json) before editing it. The executable and arguments must match the provider's own installation instructions.

Pass the trusted configuration and explicit permission when setting up MineCode:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod" --providers-config "C:\Config\minecode-providers.json" --allow-provider-execution
```

Use `--host claude` for Claude Code, or the corresponding installed executable on Linux/macOS. This doesn't enable Gradle execution or retrieval downloads. Existing settings can be merged using [config preview](ADVANCED_SETUP.md#existing-host-settings).

## Check the operation you need

`provider_status` distinguishes configuration and reported reachability. No configuration means availability is unknown/unavailable, not proof the software is absent. A successful handshake doesn't prove a mapping query, analysis call or game bridge is usable.

Provider operations can fail because of missing native dependencies, incompatible versions, downloads, timeouts or an absent game bridge. Record the actual error and fall back to local source/JAR inspection and exact-version documentation. Don't repeatedly retry a failing backend or treat its advertised capability list as verified behavior.

MCP Fabric must be connected to a compatible game bridge for in-game operations. Keep the bridge on loopback with authentication and only needed capabilities. MineCode disables its agent/memory functionality; the provider must honor that configuration.

## Permissions and rights

Provider processes can access files and network according to their own implementation. MineCode's opt-in isn't an OS sandbox. Review their code/configuration, avoid secrets in arguments and use host-level controls where appropriate.

Provider licenses don't relicense Minecraft data, downloaded sources or other dependencies. Returned content remains untrusted evidence with version and reuse limits. See [third-party notices](../THIRD_PARTY_NOTICES.md) and [evidence policy](EVIDENCE_POLICY.md).
