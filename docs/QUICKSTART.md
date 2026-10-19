# First Minecraft project with MineCode

Start with a Fabric project you already know how to build. Pick a small change you can see in game. Leave optional providers out of the first session.

## Verify what is installed

After running setup, use the same installed MineCode executable to diagnose that project's
integration without starting Codex:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" doctor --host codex --project "C:\Projects\MyMod"
```

The best possible *static* result is `configured_unverified`; it means the skills
and configuration match the installed runtime, **not** that your agent called MineCode.
`skills_only` is valid when you intentionally want guidance without MCP. To assess
the full integration, resolve `skills_only`, `missing` or `incomplete_or_mismatched`
first. The running-model result still needs to be observed separately in the host.

For a new project, create its folder, run setup for that folder, then open it in a
fresh host session. A running server stays bound to the root selected during setup.

## Inspect first

[Check the receipt, install the wheel, and run setup](INSTALLATION.md). Open the selected project in Codex, review its trust prompts, and start a fresh session. Ask:

> Use minecraft-project-inspector to inspect this project with MineCode. Tell me its Minecraft version, loader, mappings, Java requirements, and anything still unknown. Do not build or edit yet.

Check that MineCode tools were actually called, the reported project path is correct, and the versions match your build files. If tools are missing, follow [troubleshooting](ADVANCED_SETUP.md#health-and-recovery) before trying a feature. A confident answer from Codex alone doesn't prove MineCode is connected.

## Make one change

> Use minecraft-java-developer to implement [the behavior I want]. Follow the existing architecture and explain how we'll check the result.

For a failure instead, ask `minecraft-debugger` to investigate and give it the error plus reproduction steps. Keep the first task narrow enough to review its diff yourself.

## Allow a build when you're ready

Once you trust the project's wrapper and build scripts, close the current Codex session and rerun setup. Replace the project path:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod" --allow-execution
```

This leaves Gradle in offline mode. If it needs dependency downloads and you want to permit them, rerun with both flags:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod" --allow-execution --allow-network
```

For an installation at another path or on POSIX, use the executable location from [installation](INSTALLATION.md#primary-installation). If you merged your configuration manually, use [preview and merge](ADVANCED_SETUP.md#existing-host-settings) with the same flags. Restart the MCP connection or start a fresh Codex session after changing permissions. Codex approval alone doesn't enable MineCode's build tools.

These flags don't sandbox Gradle. The wrapper and build scripts are trusted code; offline mode isn't a network firewall. Reference downloads and provider processes have [separate permissions](ADVANCED_SETUP.md#permissions-and-paths).

## Check the result

Ask the agent to build and identify the resulting JAR. If the build fails, have it explain the relevant error before trying a fix. Stop repeated attempts that aren't producing new evidence.

Then test the change in game. Ask for a short report separating what was built, what actually started, and what behavior was checked. Include any step you performed yourself. A successful compile doesn't finish the task.

[Tested environments and limits](CAPABILITIES.md) · [Remove MineCode](INSTALLATION.md#updates-and-uninstall)

## Choose the relevant specialty

| Request | Entry point |
| --- | --- |
| Add an ore, recipe, machine or entity | `minecraft-java-developer` |
| Add a HUD, screen, overlay or client module | `minecraft-client-developer` |
| Add a Paper command or server-only feature; diagnose server performance | `minecraft-server-developer` |
| Resolve consequential unknown project facts | `minecraft-project-inspector` |
| Repair an observed defect | `minecraft-debugger` |
| Explain a named anti-cheat or investigate directly implicated false positives | `minecraft-understand-anticheat` |

Selection uses the host's skill discovery, not a second MineCode routing engine. Descriptions and instructions narrow relevance but do not guarantee perfect automatic selection. A normal mod with a menu may use the shared rendering guide without becoming a utility client. Server/plugin work uses the actual platform API; Fabric-oriented inspection may leave other platform facts unknown, in which case inspect the build and descriptor with host tools. No generic network, movement, ban or client task automatically triggers anti-cheat research.

Inspection above is a first-install connectivity check, not an obligatory step before every change. Once context is known, proceed directly to the task.
