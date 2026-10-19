# Advanced installation and host configuration

Start with [installation](INSTALLATION.md). Each MineCode server connects to one existing project when it starts. Set it up separately for each Minecraft project; it won't switch projects mid-session. A reference cache is not a project folder.

## Existing host settings

Setup deliberately refuses conflicting files. Install just the skills, then preview the correctly bound configuration:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod" --skills-only
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod" --print-config
```

Replace the project path. These commands use the [documented installation directory](INSTALLATION.md#primary-installation); use your environment's executable if you installed elsewhere. Add any intended permission flags, such as `--allow-execution`, to the preview command before merging its output.

Merge the printed `[mcp_servers.minecode]` table into the project's `.codex/config.toml`, preserving other settings; replace an existing MineCode entry only after reviewing it. For Claude, use `--host claude` and merge only the `minecode` member into the existing `.mcp.json` `mcpServers` object. Do not create duplicate TOML tables or duplicate JSON keys. Preview writes nothing. Configurations you merge manually remain your responsibility for update/uninstall. The installed skill directories must also be free of conflicts; preserve any local edits before replacing them.

## Permissions and paths

Add permission flags to the full setup command shown above. Setup writes them into the server's launch arguments; execution permissions default to off. Config and cache options select paths, not permissions:

| Option | Effect |
| --- | --- |
| `--allow-execution` | Trust selected-project Gradle wrapper/scripts for bounded allowlisted tasks |
| `--allow-network` | Omit Gradle's offline flag; does not itself enable execution |
| `--allow-retrieval-network` | Permit selected public repository/document retrieval |
| `--providers-config <file>` | Select an explicit trusted provider configuration; never auto-load one from a project |
| `--allow-provider-execution` | Separately permit configured provider processes and their own file/network access |
| `--reference-cache <directory>` | Override disposable retrieval cache; keep outside the active project |

These are tool boundaries, not an OS sandbox or a complete network firewall. Trusted build scripts and providers can run arbitrary code. Keep host permissions appropriate too. Optional providers remain separately installed and absent by default; see [provider setup and tested limitations](PROVIDERS.md). Minecraft Dev MCP's recorded JAR analysis does not verify all advertised capabilities. MCP Fabric remains degraded/unverified for in-game observation without a real connected bridge. Agent/memory capabilities remain disabled.

Set JAVA_HOME/PATH in the environment that launches your coding host when a build JVM is required. Verify the actual Gradle JVM in its output/daemon evidence: an MCP client may forward only selected environment variables. In an explicit SDK client, pass JAVA_HOME/GRADLE_USER_HOME deliberately; in a host, use its per-server environment configuration when inheritance is insufficient. The Java compilation target can differ from the JVM needed by Gradle/Loom. Restart a desktop host after environment changes. Never change project versions just to hide a local JDK problem.

## Health and recovery

Start by checking the installed program in PowerShell:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" --help
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" resources
```

The first command should list `setup`, `remove`, and `resources`. The second should print a directory inside the installed environment containing the bundled docs and skills. If the executable or bundle is missing, reinstall the reviewed wheel using the [update instructions](INSTALLATION.md#updates-and-uninstall).

If those work but Codex cannot see MineCode:

1. Confirm you opened the same project folder passed to setup.
2. Open that project's `.codex/config.toml`. Check that `[mcp_servers.minecode]` exists, its `command` points to an existing Python executable, and its `args` contain the correct `--project` path. Use the preview command above to compare values; don't overwrite other settings.
3. Check Codex's project trust and MCP connection status. Restart its MCP connection or start a fresh session after setup or config changes. If managed settings disable project MCP configuration, ask the administrator; reinstalling MineCode won't override that policy.
4. Inspect `/mcp` in Codex. For an older or manually merged configuration, ensure `[mcp_servers.minecode]` includes `required = true`, `startup_timeout_sec = 30` and `tool_timeout_sec = 630`, then start a fresh session. Startup and per-tool timeouts are separate: the latter accommodates MineCode's unchanged maximum 600-second execution budget plus bounded cleanup/response overhead. Doctor flags a missing or shorter tool timeout. If required startup fails, inspect the Python command, installed dependencies and project path. See the [activation check](INSTALLATION.md#verify-activation).
5. Ask Codex to call `minecode.detect_project` and `minecode.get_project_profile`. Confirm the tool results name your project. A working Python process alone doesn't prove Codex has connected to it.

Codex loads project configuration only for trusted projects. A nested Git checkout
can be a separate trust/configuration root from its parent folder. Inspect the
effective configuration for the actual session root; do not automatically trust a
parent or child. Setup never grants that trust. Starting a shell in another folder
does not reload the current model's tool catalog. CLI configuration listing and
desktop connection status prove configuration or connectivity, not model invocation.
Keep an actual agent tool-call result as the invocation evidence. A chat that does
not expose local MCP tools cannot acquire them through MineCode's installer; use a
supported fresh development session instead of overriding global settings.

`get_project_profile` defaults to version metadata and artifact counts. Request
`include_artifacts=true` only when the complete bounded inventory is needed.
Reference-code search results retain source identity, compatibility, revision and
session IDs. `get_reference_context` also provides complete provenance, including
the expected project environment, even with `context_lines=0`. Text-only hosts get
the same machine-readable JSON as structured-output hosts, without indentation.

If tools connect but execution is disabled, follow the [build opt-in commands](QUICKSTART.md#allow-a-build-when-youre-ready). If dependencies are missing offline, decide whether to enable Gradle downloads. Don't enable provider or retrieval permissions to fix a build permission error.

For install conflicts, use [preview and merge](#existing-host-settings). For files retained during removal, review and remove only the MineCode entries you no longer need. See [removal and rollback](INSTALLATION.md#updates-and-uninstall).

Claude uses `.mcp.json` rather than `.codex/config.toml` and may require project MCP approval. Its live integration remains unverified. On either host, duplicate global/project server settings or skill names can conflict; check those if project setup looks correct but discovery still fails.

## Local files and sharing

MineCode reads project metadata, supplied logs, and selected references. Your coding host may send tool output to its model service. Optional providers have their own file and network access. Treat retrieved content as evidence, not instructions.

Generated configuration contains absolute local paths. Keep tokens out of it, and normally keep that configuration and `.minecode/installation-<host>.json` out of commits. Add appropriate ignore rules or local Git exclusions yourself; setup doesn't edit them.

Review logs before sharing them. They can expose usernames and local paths, and redaction is best-effort. MineCode doesn't learn from your sessions, rewrite skills, or keep a hidden project knowledge store. See [runtime boundaries](../mcp/README.md) and [host integration scope](CAPABILITIES.md#installation-and-host-integration).

Gradle output is sanitized as complete lines before keeping the bounded output tail.
Lines exceeding 2,048 bytes are omitted and `output_truncated` is set. This avoids
separating a credential from its label at a read or tail boundary while retaining
ordinary exception signatures and source-file/line evidence. Original project logs
remain outside this redaction guarantee.
