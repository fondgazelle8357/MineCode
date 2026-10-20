# Capabilities and limitations

MineCode combines six Minecraft skills with fourteen tools in a local MCP runtime. Its strongest focus is Fabric and Minecraft Java, with separate guidance for client and server-plugin work.

## What each part provides

| Capability | Scope |
| --- | --- |
| Skills | Version/mapping/side discipline, project integration, Minecraft lifecycle, debugging and appropriate verification |
| Project inspection | Bounded static detection of build declarations, loader, mappings, source roots and conventional plugin descriptors |
| Local retrieval | Recognized Gradle/Loom source archives and Yarn mapping records, with source identity, compatibility and archive hashes |
| Selected references | Curated repository/document discovery and bounded retrieval with provenance; downloads require opt-in |
| Diagnostics | Minecraft-specific classification of supplied build/runtime logs, with evidence, uncertainty and best-effort redaction |
| Build helpers | Allowlisted trusted Gradle-wrapper tasks and time-limited client launch when explicitly enabled |
| Optional providers | Adapters to separately installed tools; availability depends on each provider and backend |

## Installation and host integration

Setup generates project-local skills/configuration for Codex and Claude Code. Automated checks exercise both formats, installer updates/removal and direct MCP stdio requests. Codex has also been used interactively. Live Claude Code model sessions are not part of the automated checks; verify its connection in your own host after approval.

Other MCP hosts can run the same server but need their own skill discovery and configuration. Managed policy, project trust and session startup affect exposure. A matching configuration file does not prove the active model can call the tools.

## Retrieval and optional providers

Search is bounded and lexical. It can locate explicit class/member names, Tiny owner records and declarations along explicit same-archive superclass links. It isn't a Java semantic index. A matching identifier doesn't establish behavior or complete class/member ownership.

A **mapping record is not an implementation body**. Source lookup doesn't inspect compiled classes or automatically generate/decompile Minecraft source. If the required source archive isn't available, inspect the project's exact-version mapped Minecraft JAR using native tools, for example `javap`. Explicit identifier searches exclude zero-identifier fragment matches and report missing source evidence.

Version labels describe evidence actually available. Fabric API module versions are traced through the selected aggregate dependency; their source namespace can remain unknown. Unknown or mismatched mappings aren't translated into the project's namespace. Mutable upstream references still require checking the returned revision and declarations.

Providers are optional and separately installed. A reachable MCP process doesn't prove every specialized operation or an in-game bridge works. Use local artifacts and normal investigation if a provider fails. See [provider setup](PROVIDERS.md).

The experimental semantic navigation adapter can request definitions, references,
implementations and call hierarchy from an explicitly configured stdio language
server. It reports unsupported operations and unknown index completeness separately
from empty results. Its protocol/MCP tests use a simulator; real Java/Kotlin compiler
resolution and Minecraft project imports remain unverified. Backends are not bundled,
and cross-language support depends on the selected backend. See
[semantic setup and limits](PROVIDERS.md#optional-semantic-navigation).

## Runtime and behavior evidence

Offline tests cover tool schemas/calls, installation, bounded resource handling, diagnostic controls and pinned Minecraft mapping answers. Fabric source retrieval tests preserve version, mapping and source provenance.

Building, launching and observing gameplay are different checks. A successful build does not establish correct rendering, inventory behavior, networking or multiplayer compatibility. Diagnostics classify logs; `unknown` avoids an unsupported label but does not mean the exception was understood.

Static inspection cannot resolve every computed/custom Gradle configuration, JVM installation or platform. Forge/NeoForge, Folia scheduling and unfamiliar project structures require platform-specific evidence. No universal version or server compatibility is promised.

## Operating boundaries

MineCode doesn't call a model, train on your project, learn from sessions or maintain a hidden knowledge store. It doesn't supply a Minecraft client framework, guarantee automatic skill selection, validate generated code by itself or provide an OS sandbox.

The coding host handles edits, permissions and model access. Build scripts and providers are trusted executable code. Review source, check behavior and sanitize logs before sharing them.

[Tool contracts](../mcp/README.md)  |  [Evidence policy](EVIDENCE_POLICY.md)  |  [Installation](INSTALLATION.md)
