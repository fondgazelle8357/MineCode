---
name: minecraft-java-developer
description: Build or change ordinary Minecraft Java mods, especially Fabric content, recipes, blocks, entities and shared game logic. Also supplies common version, mapping and side guidance. Use the client specialty for client features and the server specialty for plugins or server operations; use minecraft-debugger for an observed defect.
---

# Minecraft Java developer

Deliver the requested mod. MineCode supplies Minecraft facts and pitfalls; the host owns coding, design, Git, and permissions. Tools are optional aids, not stages to complete.

## Start with the actual task

- **Small edit, known project:** read the owner and relevant callers, change it, check only a real uncertainty, finish. No orientation report or provider discovery.
- **Unfamiliar code:** inspect one or two nearby features and their registration and lifecycle. Use one project profile only if consequential environment facts are missing; it already includes detection.
- **Empty Fabric workspace:** use [new projects](references/new-project.md). Honor the requested loader; Fabric instructions are not a replacement for a Forge/NeoForge project or a Paper plugin.
- **Minecraft uncertainty:** name the precise question, inspect local code or exact-version source, then stop researching once answered.

Identify the requested deliverable and its physical/logical side from the request and project. A mod with a screen is not automatically a utility client. A mod that runs on a server is not automatically a Bukkit plugin. A mixed project can need more than one specialty, only for the affected parts:

| Task | Select when relevant |
| --- | --- |
| Ordinary content, recipes, entities, saved game state | Stay here; [content mods](references/content-mods.md) |
| Client modules, HUD, overlays, input, client screens | [Client developer](../minecraft-client-developer/SKILL.md) |
| Paper/Purpur plugins, server-only mods, server operations | [Server developer](../minecraft-server-developer/SKILL.md) |
| Observed failure | [Debugger](../minecraft-debugger/SKILL.md) |

Do not load sibling skills or every reference as an onboarding ritual. A furnace menu can use the rendering reference directly without adopting client module architecture. No anti-cheat research follows merely from networking, movement, PvP or server work.

## Use the relevant evidence

[Integration and Mixins](references/integration.md), [networking](references/networking.md), and [migration](references/migration.md) are shared references. Load only the one that answers the current question. Match Minecraft version, loader/API and mappings; keep client-only classes unreachable from common/server initialization. Prefer the project's existing owner and supported hooks.

Translate the request into observable outcomes: an ore needs registration, resources and intended acquisition; saved state needs persistence; shared state needs appropriate synchronization. Do not substitute a client module/settings framework for ordinary game content.

## Finish

A requested usable JAR needs a relevant successful build and the actual distributable for that build configuration. Build once after a coherent change; do not chain clean/classes/build or launch for unrelated edits. Inspect visuals to claim visual success and reproduce a defect to claim it fixed. If observation is unavailable, state the specific unverified behavior and one concrete check.

Report what changed, what was actually checked, and remaining uncertainty. Compilation or startup alone does not establish gameplay correctness.
