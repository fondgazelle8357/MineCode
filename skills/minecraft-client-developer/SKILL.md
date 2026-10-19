---
name: minecraft-client-developer
description: Develop Minecraft Java client features such as HUDs, screens, overlays, keybinds and utility-client modules. Use for explicitly client-side work; a regular content mod or server plugin does not imply client module architecture. Use minecraft-debugger for an observed failure.
---

# Minecraft client developer

Implement the requested player experience in the current Minecraft version, loader and mappings. Reuse known environment facts; inspect only missing facts that change the work. MineCode adds client-specific knowledge, while the host handles general coding and design. No mandatory profile, search, build or launch sequence.

## Recognize full client versus small overlay

When the user says **traditional client**, **regular client**, **classic ClickGUI**, or asks for a multi-category modular client, read [Classic ClickGUI and product acceptance](references/classic-clickgui.md) **before** architecture or UI design. Those requests default to compact movable category panels with module toggles and expandable settings, **not** large fullscreen dashboards, practice-note screens or persistent HUDs. Preserve named categories and required active behavior. A substantial multi-category client justifies a proportionate module manager; the "small standalone HUD" advice below applies only to genuinely small HUD requests.

Before building a large client, write down the actual requested feature contract and mode-specific module matrix. Separate GUI, HUD, informative aids and active gameplay modules, including features requiring server-rule verification. Do not quietly reinterpret ban safety or uncertain rules as permission to replace a full client with a HUD-only training aid. Never promise server approval or universal anti-cheat compatibility. Only count requested outcomes as completed after relevant UI and gameplay verification.

For an existing client, trace the nearest feature through registration, enable/disable, settings persistence and the relevant event path. Extend those owners instead of adding a second event bus or module manager. For a small standalone HUD or keybind mod, use a small entrypoint and supported hook; a client framework must earn its existence. Empty Fabric workspaces can use [new projects](../minecraft-java-developer/references/new-project.md).

## Select the relevant detail

| Work | Reference |
| --- | --- |
| Traditional multi-category ClickGUI or full modular client | [Classic ClickGUI and product acceptance](references/classic-clickgui.md), then rendering/integration as needed |
| Screen, HUD, overlay, ESP or input | [Rendering and screens](../minecraft-java-developer/references/rendering.md) |
| Existing module integration or Mixin | [Integration](../minecraft-java-developer/references/integration.md) |
| Movement, rotations, inventory or combat | [Movement and inventory](../minecraft-java-developer/references/movement-inventory.md), applicable section only |
| Multi-step actions or temporary/competing control | [Stateful automation](../minecraft-java-developer/references/automation.md) |
| Payload or vanilla packet question | [Networking](../minecraft-java-developer/references/networking.md) |
| Version port | [Migration](../minecraft-java-developer/references/migration.md) |

These references retain stable shared paths for upgrades. Read only what the task needs. A simple display does not need automation guidance. Client work, movement and packet handling do not automatically justify anti-cheat research.

## Player experience and correctness

Turn the request into observable outcomes. Customizable ESP includes choosing targets, bounded scanning and an intentional depth policy. A usable screen includes readable controls, coherent layout, correct input coordinates and useful ranges. For a new client or substantial redesign, derive branding, layout and colors from this request unless preservation is requested; reusing sound infrastructure need not reproduce the old visual identity.

Keep rendering work bounded and separate scanning from drawing. Keep client-only classes in the correct source set and initialization path. Multi-step actions must distinguish local prediction, sent requests and observed outcomes, and relinquish temporary state on cancellation, manual interference and session changes as applicable.

For substantial generation, check requested features run, controls affect behavior, settings persist, enable/disable cleans up and commands/binds are discoverable. Do not advertise placeholders. Claim appearance or gameplay success only after observing the requested interaction; a title screen or successful build is insufficient. If visual tools fail, retry only after a relevant change, then give one specific manual check. For an observed bug, use the debugger rather than treating a plausible patch as a confirmed repair.
