# Existing projects

Start at the subsystem that owns the requested behavior. Inspect relevant entrypoints and the project's registration, event, state persistence, command, resource, networking or Mixin conventions, plus client module/render/input owners only when relevant. Follow callers only far enough to understand ownership and lifecycle. Reuse recent environment evidence when it still describes the active module.

Resolve Minecraft version, loader/API generation, mappings, source set, or side only when those facts affect the change. Inspect more build metadata when values conflict, are computed, or remain consequentially unknown. Extend established abstractions and avoid a second event bus, manager, setting system, or unrelated refactor.

Unless a domain section requires stronger evidence, use local source and callers first, exact-version Minecraft/loader/platform evidence second, selected reference implementations third, and generic assumptions last. A reference project does not prove local ownership, target-version compatibility, or reuse permission.

Keep client-only references unreachable from common and dedicated-server initialization. For networking, confirm payload direction, codec/receiver registration order, server authority, and callback thread. For rendering and input, confirm the relevant lifecycle event, render context, state ownership, and existing settings/keybind behavior.

Prefer a supported public API or project event. When a Mixin is warranted, verify the exact-version target class and method descriptor, mappings namespace, injection point semantics, side, configuration, and relevant competing transformations. An annotation name alone does not establish correct behavior.

For a broken Mixin, preserve the selector evidence from the log and classify the failure before editing: target class/member missing, descriptor/overload or handler mismatch, injection point/count mismatch, explicit remap/refmap failure, side/config loading failure, or uncertain. Confirm the current project version, mappings, and side; compare the local annotation with the current target class/member and descriptor; inspect the actual target instructions only when the member still exists. Change the smallest disproved assumption—selector, descriptor/handler, `@At` target/ordinal/slice, remap setting, or config/side—not several at once. A missing selector does not prove a rename.

# Unfamiliar client integration

For an unfamiliar utility client, trace the paths that affect the requested feature:

1. Inspect one or two nearest existing features, including one with similar lifecycle or state needs when possible.
2. Trace how they are constructed, registered, categorized, enabled, disabled, and cleaned up.
3. Trace only the event, tick, render, input, packet, or Mixin path relevant to the requested behavior; inspect callers when ownership remains ambiguous.
4. Find the established setting definition, config serialization, persistence, and UI exposure used by those features.
5. Reuse the project owner for shared state—such as movement, rotation, inventory, targeting, packet, or screen coordination—instead of keeping competing feature-local state.

Keep consequential ownership uncertainty explicit. A matching filename, base-class name, annotation, or familiar term is not proof of registration, timing, persistence, or ownership. Implement through the observed path; do not add a second event bus, module registry, setting system, manager, rotation/packet layer, lifecycle bypass, or Mixin merely to avoid tracing the existing one.

Review only risks relevant to the feature: physical/logical side and player/world availability; event phase and render/input timing; packet direction, callback thread, and server authority; movement/rotation arbitration; inventory synchronization; disable/disconnect/world-change cleanup; and version-sensitive hooks or Mixin targets.
