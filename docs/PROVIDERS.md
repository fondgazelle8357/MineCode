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

## Optional semantic navigation

MineCode includes an experimental `minecode-semantic` MCP adapter for a separately
installed **stdio Language Server Protocol backend**. It adds position-based
definition, reference, implementation, incoming-call and outgoing-call queries.
It does not implement a compiler or infer semantic relationships from text matches.

Copy [semantic-provider.example.json](../integrations/semantic-provider.example.json)
to a trusted configuration location and replace the executable, project and backend
arguments. The `--stdio` argument is illustrative: use the selected backend's actual
launch command. Java and Kotlin backends can be separate provider entries with
different IDs and the same `semantic_navigation` capability; select the provider
explicitly when calling. The adapter does not install a backend or select one by
file extension. Use a native executable such as `java.exe` with its required JAR
arguments on Windows; `.bat` and `.cmd` launchers are rejected.

Enable MineCode's existing `--allow-provider-execution` switch. The adapter also
requires `--allow-backend-execution` in its startup arguments. This authorizes the
configured backend, which may import Gradle projects, run project code, write caches
and download dependencies independently of MineCode's Gradle/network switches.
Only configure trusted projects and backend executables.

Call `minecode.call_provider` with:

```json
{
  "provider": "semantic-code",
  "capability": "semantic_navigation",
  "timeout_seconds": 60,
  "arguments": {
    "file": "src/main/kotlin/me/fond/example/AttachmentService.kt",
    "line": 115,
    "column": 8,
    "operations": ["definition", "references", "implementation", "incoming_calls", "outgoing_calls"],
    "max_results": 10,
    "timeout_seconds": 40
  }
}
```

Coordinates are **zero-based UTF-16**, including returned LSP ranges. The selected
file must be a saved UTF-8 `.java` or `.kt` file inside the configured project,
at most 1 MiB. A SHA-256 identifies the selected file's bytes; it does not identify
a whole-project snapshot. Concurrent edits to other files are not tracked.

The adapter opens a fresh backend per batch because the existing provider bridge
opens a process per call. Batch related operations to share initialization work.
There is no persistent index service or automatic readiness detection: initialization
does not prove indexing is finished. Cold project imports may exceed the time budget.
Give the outer provider timeout room for backend execution and cleanup (for example
60 seconds outside, 40 inside; maximum inner budget is 100 seconds).

Results retain backend name/version when reported, locations or location links,
and call-hierarchy relationships. Opaque backend `data` is used internally and
omitted from output. Results are bounded to 50 items per operation and a shared
5,000-character evidence budget before the outer provider's 8,000-character limit.
Check both levels' truncation flags. Redaction can alter private paths/URIs.

`unsupported` means the backend did not advertise the operation. `failed` and
`timed_out` are distinct from an empty successful response. `complete` is always
false and `index_state` is `unknown`: LSP navigation alone cannot establish dependency
resolution, index completeness or absence of references. Dynamic capability
registration and backend-specific client extensions are not supported. Workspace
edit requests are refused. No mapping translation or decompilation is added.

Protocol tests use an original simulated backend and exercise actual subprocess
framing and MCP calls. They **do not verify Java/Kotlin overload resolution,
cross-language references, Gradle import or Minecraft semantics**. Those need a real
backend/project acceptance run before treating this integration as production-ready.
Reflection, Mixins, runtime registration and virtual dispatch can still require
source inspection and runtime evidence.

Protocol reference: [Language Server Protocol 3.17](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.17/specification/).

## Permissions and rights

Provider processes can access files and network according to their own implementation. MineCode's opt-in isn't an OS sandbox. Review their code/configuration, avoid secrets in arguments and use host-level controls where appropriate.

Provider licenses don't relicense Minecraft data, downloaded sources or other dependencies. Returned content remains untrusted evidence with version and reuse limits. See [third-party notices](../THIRD_PARTY_NOTICES.md) and [evidence policy](EVIDENCE_POLICY.md).
