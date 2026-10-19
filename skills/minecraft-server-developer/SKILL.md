---
name: minecraft-server-developer
description: Develop Minecraft Java Paper/Purpur plugins or server-only mods, and handle Minecraft server configuration, backups and performance diagnosis. Use the project's actual server platform; client features and ordinary content mods do not imply plugin architecture.
---

# Minecraft server developer

Resolve the actual deliverable: Bukkit/Paper plugin, Fabric or another loader's server mod, proxy plugin, or server operations. Reuse known version and platform facts. Follow the existing platform; do not convert a Fabric server mod into a plugin. Velocity and Folia have their own APIs and execution models, not automatic Paper compatibility.

Use one runtime and only the relevant guide. A known small edit needs no project report, repository search or server launch. For ordinary shared mod content, use [content mods](../minecraft-java-developer/references/content-mods.md). For maintenance, configuration, backups or lag diagnosis, read [server operations](references/operations.md).

## Plugin work

- Follow the existing descriptor and bootstrap model. Check the main entrypoint, declared API version, required/optional dependencies, command registration and permission defaults. Do not mix plugin.yml and paper-plugin.yml conventions or add metadata without verifying the target API. Handle console/non-player senders where applicable.
- Trace listener registration, event priority, cancellation semantics and cleanup. Respect other plugins' decisions unless the requested behavior explicitly overrides them. Monitor-only observations must not silently mutate events. Prefer public platform APIs over NMS; use exact-version internals only for a concrete missing capability.
- Keep blocking I/O off the game thread, but do not access arbitrary world/player state from an async callback. Schedule state access through the target platform's owning thread, and revalidate player/plugin/session state after a delayed result.
- On Folia, region and entity ownership replace the assumption of one global game thread. Use entity scheduling for entity work and region scheduling for location work; a global task does not grant access to every region. Do not claim Folia support just by setting the descriptor flag.
- Release listeners/tasks/resources on disable as the platform requires; prevent delayed work from reviving disabled state. Keep durable data separate from transient player/session references. Bound per-tick work and avoid forcing chunk loads for unrelated events.

## Server mods and validation

Use the loader's common/server hooks, authoritative state and side-safe dependencies. A server-only install promise requires checking whether vanilla clients can join. For custom payloads, use the shared [networking guide](../minecraft-java-developer/references/networking.md); do not impose client rotation/hotbar ownership on ordinary plugin events.

Check the behavior affected: command permissions, event cancellation, saved data, lifecycle or thread ownership. A plugin appearing in the plugin list proves loading, not its permissions or behavior. Anti-cheat research is relevant only when explicitly requested or directly implicated by diagnostic evidence; ordinary server work does not trigger it.

API references: [Paper scheduling](https://docs.papermc.io/paper/dev/scheduler/), [plugin descriptors](https://docs.papermc.io/paper/dev/plugin-yml/), [Paper/Folia ownership](https://docs.papermc.io/paper/dev/folia-support/). Reviewed 2026-10-12; verify API availability for the installed version.
