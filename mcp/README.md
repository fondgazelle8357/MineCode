# MineCode local runtime

MineCode runs locally and exposes fourteen tools from [src/minecode_runtime](../src/minecode_runtime). It uses Python 3.11+ and the official MCP Python SDK over stdio. Results have typed JSON schemas. Retrieval checks local evidence first; the runtime makes no model calls and needs no hosted service.

## Install and connect

For normal use, follow the [wheel installation and project setup](../docs/INSTALLATION.md) and [quickstart](../docs/QUICKSTART.md). The following editable installation is for MineCode contributors only, from the repository in PowerShell:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
~~~

The setup command generates host-specific configuration. The equivalent generic stdio example below is useful for manual integration. Installed Codex discovery/tool calls have been exercised; live Claude remains unverified. See the [current capability evidence](../docs/CAPABILITIES.md).

~~~json
{
  "mcpServers": {
    "minecode": {
      "command": "C:\\path\\to\\MineCode\\.venv\\Scripts\\python.exe",
      "args": ["-m", "minecode_runtime", "--project", "C:\\path\\to\\your\\trusted-project"]
    }
  }
}
~~~

The project must already exist. It is fixed for the server session; tools cannot select another root. Inspection/diagnosis work with execution disabled. To build or launch, add **--allow-execution** to the startup arguments only after trusting that project's wrapper and scripts. **--allow-network** explicitly omits Gradle's default **--offline** flag. Installation may download Python dependencies. Reference fetches require separate **--allow-retrieval-network** opt-in; **--reference-cache PATH** optionally selects a disposable cache outside the project. No model calls occur.

## Tool contracts

All results have JSON output schemas; nullable profile fields mean unknown. Inspection tools take no project/path argument.

| Tool | Inputs | Result |
| --- | --- | --- |
| minecode.detect_project | none | Root, Java/Gradle/Minecraft/Fabric and conventional server-plugin markers, probable type, descriptors, warnings |
| minecode.get_project_profile | optional `include_artifacts` (default false) | Declared versions/name/mod ID, roots/Mixins/entrypoints, likely tasks and local artifact counts. Set true for the full bounded inventory. Unknown values stay null. |
| minecode.run_gradle | task; timeout_seconds=120 | Success, state, exit code, summary, stdout/stderr tails, truncation, elapsed time, optional diagnosis |
| minecode.build_project | timeout_seconds=120 | Execution result and candidate build/libs JARs with changed-during-build flags; runtime_verified=false |
| minecode.run_client | timeout_seconds=120 | Task discovery, execution, conservative startup state; gameplay_verified=false |
| minecode.analyze_build_failure | output (up to 128,000 characters); optional environment | Failure category and migration layer, bounded compiler/Mixin/network-registration details, environment, next step, confidence |
| minecode.search_sources | query; optional environment/category filters; max_results=5 | Ranked registry metadata; no downloads |
| minecode.search_reference_code | query; optional 1–3 source_ids; max_results=5; refresh=false | Exact local version/mapping artifact hits first, then bounded cached repository hits, with provenance and result IDs |
| minecode.get_reference_context | result_id; context_lines=20 | Bounded expansion from the same revision |
| minecode.search_developer_knowledge | query; optional version/mappings/source IDs; fetch_content=true | Official docs/Javadocs or registered discussion evidence; unavailable content labeled registry-only |
| minecode.provider_status | provider; optional capability | Bounded health/schema result for one explicitly configured provider |
| minecode.call_provider | capability; arguments; optional provider/timeout | Bounded result from one trusted configured provider capability |
| minecode.analyze_runtime_failure | output; optional environment/source/repair | Sanitized bounded evidence, migration, Mixin and network-registration details, next step, confidence, explicit uncertainty |
| minecode.search_gameplay_techniques | query; max_results=3; optional category | Offline terminology/aliases with provenance and environment caveats |

Diagnostic tools omit individual log lines longer than 2,048 characters before regex processing and set `input_truncated=true`. Line numbering is preserved for remaining runtime evidence. Runtime redaction also bounds expanded environment, repair, and log text; omitted evidence cannot establish a cause. Inspect a narrower original excerpt locally if the relevant failure was on an omitted line.

See [retrieval contracts, cache and security](../docs/RETRIEVAL.md). Registry data is bundled into wheel builds from the authoritative files. Public repository retrieval additionally requires Git on PATH. Network/cache tools have mutation/open-world annotations because they may write disposable snapshots. Providers are off by default and require `--providers-config PATH --allow-provider-execution`; provider, Gradle, and retrieval permissions remain separate.

Public tasks are build, classes, test, and runClient, optionally qualified (:client:build). No task flags, free-form arguments, shell commands, or arbitrary executable paths are accepted. Timeouts are integer seconds from 1 to 600. One project operation runs at a time.

run_client first checks Fabric/Loom markers, then uses the wrapper's tasks --all. It launches a listed root runClient task or a single unambiguous qualified task. Missing/ambiguous tasks do not launch. Discovery uses at most 60 seconds and counts against the requested time budget. The client runs in the foreground until exit or timeout; timeout attempts to stop the process tree. This is a bounded development session, not a persistent launcher. A successful task exit reports process_exited, not proof that Minecraft reached its menu. A timeout reports unverified_timeout, not successful startup.

## Boundaries and limitations

- Windows uses local gradlew.bat through fixed cmd tokens, with the selected directory supplied as cwd rather than interpolated into shell text. POSIX uses local gradlew directly. There is no global Gradle fallback.
- Gradle wrappers and build scripts execute trusted project code. They can modify files or start processes/network access beyond the project. This runtime is **not an OS sandbox**. Gradle --offline does not stop wrapper bootstrapping or custom plugin/script networking. Preinstall/cache dependencies for offline builds.
- Cancellation/timeouts attempt to stop the launched process tree (taskkill on Windows, a process group on POSIX). Deliberately detached project processes are outside this guarantee. No server can safely execute an untrusted wrapper solely by restricting task names.
- Metadata reads reject resolved paths outside the root, skip common generated/dependency folders, and limit inspection to 2,000 directories and 256 KiB per metadata file. Static parsing covers conventional literals, root `gradle.properties`, and conventional `gradle/libs.versions.toml`; it does not evaluate arbitrary Gradle, resolve dependencies, understand custom source sets, or act as an API/mapping resolver. Conflicting/computed values stay null. Descriptor version ranges are not installed versions.
- Artifact paths are candidates in conventional build/libs directories; existing/stale artifacts remain marked separately. Neither a successful build nor a candidate JAR establishes runtime/gameplay correctness.
- Diagnostic categories and migration layers are hypotheses from supplied text. Bounded output distinguishes build/toolchain, Minecraft mappings/vanilla symbols, Fabric/Loader APIs, existing Mixin subtypes, explicit Fabric networking registration/lifecycle failures, side/source-set problems, ordinary Java, and unknown cases while preserving useful evidence. Vague Netty/disconnect text remains unknown. No files are automatically repaired and no follow-up web research runs.
- Automated tests use original metadata and wrapper simulators. Selected real Fabric build, failure-repair, startup and localhost behavior evidence is summarized in [current capabilities](../docs/CAPABILITIES.md); broader Minecraft compatibility remains unverified.

See [evidence policy](../docs/EVIDENCE_POLICY.md) before applying external examples. SDK dependency: [official Python SDK](https://github.com/modelcontextprotocol/python-sdk), pinned to 2.3.0; no upstream code was copied. API/protocol references: [SDK server](https://py.sdk.modelcontextprotocol.io/api/mcp/server/) and [MCP tools](https://modelcontextprotocol.io/specification/latest/server/tools). MineCode's own code uses the [MIT License](../LICENSE).

## Current scope

Use the fourteen operations through the [shared workflow](../docs/WORKFLOW.md). The coding agent implements changes and decides which small fixes to attempt. Compilation, build, startup, installed-package and behavior evidence remain distinct.

The gameplay lookup is offline and static. Optional providers remain separately installed and explicitly enabled. Gradle execution is limited to the documented task allowlist. Execution, retrieval and provider opt-ins remain separate; there is no automatic learning or skill rewriting.

Server-plugin detection recognizes conventional `src/main/resources/plugin.yml` and `paper-plugin.yml` markers. It does not resolve Paper/Folia versions, parse plugin YAML semantics, or equate `api-version` with the installed Minecraft version. Mixed Fabric/plugin roots require module selection. Maven and custom platform inspection remain host work.
