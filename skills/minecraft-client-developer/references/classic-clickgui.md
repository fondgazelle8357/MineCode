# Classic Minecraft ClickGUI: intent and acceptance

Read when the user asks for a **traditional / classic / regular Minecraft client**, **ClickGUI**, **hack-client-style client**, **Meteor-like or RusherHack-like panels**, or a full client with multiple module categories. These words describe a specific user-interface pattern, **not** a large HUD or a fullscreen settings dashboard. Use public interface conventions as reference, not third-party code or assets.

## Resolve what the user actually wants

The primary deliverable is an **in-game, compact, interactive module configuration GUI**. A small overlay may be an optional module, but is not a substitute for the GUI or for real feature behavior.

- Classic default: multiple **narrow, vertical, independently scrollable and preferably draggable category panels** placed over the still-visible Minecraft world. Category title at top; short, dense module rows beneath. Neutral dark backgrounds, restrained accent for enabled modules, Minecraft-scale typography. Avoid giant cards, large headings, full-width grids, wizard pages, and unnecessary onboarding or practice-note dashboards.
- If the request names categories, **preserve those categories exactly**. For example, five competitive groups might be Mace PvP, UHC, Sword, Crystal/Vanilla, Miscellaneous. Do not silently replace them with generic Combat/Render categories.
- An optional search/filter and a separate compact HUD editor may complement this GUI. Do not make a giant persistent on-screen HUD the primary experience.
- Distinguish an **actual gameplay module** (functional enable/disable behavior and meaningful settings) from an informational HUD element, a preset, a practice note, a placeholder, and a future feature. They are not interchangeable.
- If the user asks for a full client but names no specific modules, research the relevant domain and **propose a concrete module matrix and intended behavior before implementing**. Clarify unresolved rule/feature tradeoffs once rather than quietly downscoping to counters. If an individual feature is disallowed or inappropriate, say which one and preserve the remainder of the product request.

## Interaction contract

Baseline behavior unless a different UX is requested:

1. **Right Shift** opens the ClickGUI (user-rebindable); **Escape** closes. While the GUI is closed, it draws no fullscreen frame or menu. The world stays visible through the GUI background.
2. Each category is a labeled panel. **Left-click** a module row to toggle it; its visual enabled/disabled state must match *actual* module state. **Right-click** the row to expand or open *that module's* settings without switching to a separate full-screen wizard.
3. Settings use actual supported controls: boolean toggles, bounded sliders, enum choices, binds and contextual tooltips only where appropriate. Persist per-module state and settings across restart, and expose an intentional way to disable a module.
4. Panel headers support dragging and prevent panels from becoming unrecoverably offscreen. Each panel can collapse; its content scrolls without moving the whole window. Keep input ownership and press/release correct to prevent accidental toggles during drag or scroll. Search, if implemented, must preserve interaction semantics.
5. Layout works at common window sizes and GUI scales. **Five panels need not physically fit side-by-side at every GUI scale**: allow horizontal scrolling, sensible wrapping or a comparable compact reachability strategy rather than microscopic text or clipped controls. Preserve readable labels and exact click hitboxes.
6. Opening and closing the menu must not spuriously activate module keybinds or intercept chat input. Use real Minecraft screen focus, mouse coordinates and reinit/resize lifecycle. No duplicate background/blur pass.
7. Optional HUD elements are separately registered, independently enabled and **off by default unless requested**. They should not obstruct combat; no giant dashboard belongs on the gameplay screen.

## Architecture proportional to product scope

A single tiny HUD needs no framework. A requested **multi-category modular client** does justify a minimal central module registry/manager, typed settings and persistence, category metadata, consistent enable/disable lifecycle and a GUI bound directly to this state. Reuse an existing project's owners where available; avoid adding a second event bus or redundant managers. For a new client, build only the infrastructure needed by the actual modules and requested UX.

Use the exact game version, mappings, loader, fabric hooks and current render/input semantics. Keep GUI drawing and hit testing in the same GUI-scaled coordinate space. Treat repeated placeholder rows as **unfinished modules**, not completed functionality.

Do not interpret “won't get me banned” as a magic technical guarantee or as a requirement to turn the entire client into a HUD. Establish the named community's policy, separate rule compliance from anti-cheat outcomes, and offer allowed capabilities when appropriate. Authorized local anti-cheat tests are useful compatibility evidence, not universal server approval; do not perform detection-evasion work.

## Before saying "done"

For a substantial client, record a **feature-to-implementation checklist** with requested categories, actual modules, settings, observable game behavior and status (implemented / unverified / missing). Do not count mere menu text, module names or inventory counters as completion of active gameplay modules.

Verify with the actual running client, not only Gradle success:

- Open the GUI in-world; show that it is **compact category panels**, not a full-screen generic dashboard. Observe it at **two GUI scales** and one constrained window size.
- Toggle a real module on/off, open its settings, change a setting, drag/collapse/scroll a category, close/reopen, rebind where supported, restart and confirm persistence.
- Exercise module behavior in-game and verify cleanup on disable, world change or disconnect as applicable. Verify optional HUD stays off unless selected.
- For compatibility claims, join the authorized test server as a monitored player and exercise the declared scenario. A server reaching "Done" or a client compiling is **not** a compatibility pass.
- Report every failed or unobserved acceptance criterion explicitly. If the GUI was not actually seen, do not call it visually verified.

Interface-convention references (not copied implementations): [Meteor Client FAQ](https://meteorclient.com/faq), [LiquidBounce ClickGUI documentation](https://liquidbounce.net/docs/usage/clickgui/).