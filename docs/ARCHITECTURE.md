# How MineCode works

MineCode is a local specialization layer for an existing coding agent. The host interprets requests, selects instructions and tools, edits code, handles Git and enforces its own permissions. MineCode supplies Minecraft-specific guidance and evidence. It has no model, planner, background learning loop or Minecraft client framework.

## A request through the system

**Request → host agent → relevant skill → optional precise evidence → implementation → appropriate verification → result.**

These are responsibilities, not a mandatory pipeline. “Rename this known setting” may need only the owning file and an edit. “Port this Mixin to 1.21.11” needs the current target descriptor, mapping namespace and exact game implementation. A profile, provider probe, build and game launch are not prerequisites for every task.

The [architecture visual](assets/architecture.svg) places MineCode beside the agent's implementation path. The agent consults it; MineCode does not take over the project. Different project types receive different guidance.

## Skills and discovery

A **skill** is a named folder of instructions with optional references. An **MCP tool** is callable Python behavior with an input/output schema. Skills explain what evidence matters; tools obtain or classify it. Neither guarantees the model follows the instructions correctly.

Setup copies six skills into `.agents/skills` for Codex or `.claude/skills` for Claude. Supporting hosts see names/descriptions and choose relevant bodies. References are loaded on demand. Installing without explicitly mentioning MineCode can still lead to automatic selection; there is no runtime router that forces selection. A new session and trusted project configuration may be needed. [Official skill activation model](https://developers.openai.com/plugins/concepts/skills).

| Skill | Responsibility | Should stay out of |
| --- | --- | --- |
| minecraft-java-developer | Ordinary mod registration, resources, shared state; common version/mapping/side rules | Client frameworks for simple content |
| minecraft-client-developer | HUDs, screens, input, existing utility-client architecture | Ordinary content and server plugins |
| minecraft-server-developer | Plugin/server platform, permissions, lifecycle and scheduling | Fabric client assumptions |
| minecraft-project-inspector | Resolve consequential unknowns in unfamiliar projects | Empty workspaces and already known metadata |
| minecraft-debugger | Evidence-led investigation of an observed defect | Mandatory diagnosis of healthy code |
| minecraft-understand-anticheat | Explicit validation explanations or directly implicated false positives | Generic movement, unexplained bans, bypass or evasion |

Shared references stay under the Java developer skill so existing installed paths remain valid. A screen in a content mod can use rendering guidance without loading module architecture.

## Local runtime and its fourteen tools

One Python process serves MCP over stdio for one fixed project root. [server.py](../src/minecode_runtime/server.py) binds typed calls to small runtime modules. It does not edit Minecraft source automatically.

| Tools | What they actually do |
| --- | --- |
| detect_project; get_project_profile | Read bounded local declarations, markers, roots, entrypoints and available local source artifacts. The profile includes detection. |
| run_gradle; build_project; run_client | Run permitted trusted wrapper tasks, collect bounded results/JAR candidates, or attempt a time-limited Fabric client launch. The host can already execute builds. |
| analyze_build_failure; analyze_runtime_failure | Classify supplied logs with Minecraft-specific patterns, uncertainty and best-effort redaction of model-visible fields. Review before sharing. Neither observes the screen or proves root cause. |
| search_sources | Rank bundled repository metadata offline. |
| search_reference_code | Search version-qualified local archives, then explicitly selected repositories when needed. |
| search_developer_knowledge | Rank docs/Javadocs and optionally fetch their text. |
| get_reference_context | Expand one result from the same snapshot; bounded lines and characters. |
| search_gameplay_techniques | Explain static terms/aliases with provenance, without executing gameplay. |
| provider_status; call_provider | Inspect/call an explicitly configured external capability. Optional, separately trusted processes. |

See [full contracts](../mcp/README.md). Fourteen is the present compatibility surface, not a product target. Build wrappers overlap host functionality; they remain for existing integrations, not as required steps. Providers have weak historical reliability and stay off by default.

## Environment and source identity

[inspection.py](../src/minecode_runtime/inspection.py) reads conventional Gradle literals, root properties, conventional version catalogs and Fabric descriptors without evaluating scripts. Conflicting or computed versions remain null. It separates declared Java compilation target from the unverified JVM running Gradle. Fabric `environment: client` differs from common mod initialization.

Conventional `src/main/resources/plugin.yml` and `paper-plugin.yml` are server-plugin markers. They do not prove resolved server version, installed Paper build, Folia compatibility or valid YAML semantics. A mixed Fabric/plugin workspace gets a warning to select the affected module. Maven/plugin dependency resolution and general Forge/NeoForge inspection are not implemented. The host must read those builds; MineCode must not substitute Fabric guesses.

[local_sources.py](../src/minecode_runtime/local_sources.py) looks in bounded, version-qualified Loom/Gradle cache locations. It keeps Minecraft version, mappings version, namespace and artifact identity together. It neither downloads missing game sources automatically nor translates Yarn names to Mojang names. Unknown namespace evidence remains supporting evidence.

Exact source matters for render callbacks, Mixin descriptors, packet codecs and side/lifecycle APIs. Matching a game version alone does not establish matching mappings. A popular client can teach ownership patterns but cannot establish the target API.

## Retrieval without an index service

The bundle contains repository/document metadata and a small glossary, not third-party source trees. [registry.py](../src/minecode_runtime/registry.py) uses task terms, declared compatibility, trust and a small score. Ordinary versioned questions prioritize applicability before text-match volume; migration/history questions can compare versions. There is no vector database or automatic repository-wide ingestion.

Local exact matches take priority before applying the result limit. If they fill the limit, remote repositories are skipped unless refresh is requested. Repository retrieval requires 1–3 selected IDs. Documentation retrieval considers at most three relevant candidates; known Minecraft mismatches are not fetched automatically for ordinary versioned queries. Caveats remain in results.

Remote snapshots are cached and pinned for the session. Expanded results refer to that snapshot. Local archives are checked for changes before expansion. Context expansion is limited to 101 lines / 8,000 characters. Large archives, entries and documents have bounds. Cache data is disposable, not permanent project memory. [Retrieval details](RETRIEVAL.md).

Registry compatibility describes reviewed metadata; a later fetched upstream branch may have moved. Inspect returned revision and actual build declarations before treating a mutable source as version proof. Registry reuse flags do not grant a third-party license.

## Permissions, dependencies and privacy

| Boundary | Default and meaning |
| --- | --- |
| Local inspection and diagnostics | Available; returned evidence enters host context |
| Gradle execution | Off; enable only for trusted wrapper/build scripts |
| Gradle network option | Off means `--offline`, not a network sandbox; wrapper/custom code can still network |
| Reference network | Separate opt-in; selected public HTTPS sources and disposable cache |
| Provider execution | Separate opt-in/configuration; external process can access files/network |

Python 3.11+, MCP SDK, Pydantic and PyYAML are runtime dependencies. Git is needed for remote repository retrieval. JDK/Gradle belong to the project; providers may have other runtimes. MineCode has no model API dependency. Host policies still apply. Best-effort redaction is not a guarantee; profiles intentionally contain the selected root, and raw build output can contain paths. Review reports before publishing.
