---
name: minecraft-debugger
description: Diagnose and fix observed Minecraft Java defects, including broken or blurred screens, rendering and interaction problems, compiler/Gradle failures, Mixins, startup crashes, and networking. Use the original failing behavior and exact-version evidence to test the cause.
---

# Minecraft debugger

Fix the observed failure. A plausible explanation is a hypothesis until evidence distinguishes it from alternatives.

## Choose the shortest diagnostic path

1. Get the reproduction and only the missing evidence that changes the next decision. For a visual defect, inspect the visible result and rendering path; logs can be clean. For a crash, preserve the useful exception chain and recent changes. Reuse known environment facts.
2. State the leading hypothesis and one observation that would disprove it. Inspect the responsible local code and exact-version Minecraft behavior before editing. Do not change several unrelated causes at once.
3. Make the smallest supported repair. Reproduce the original failure, using the same screen, action, settings, or command. A build answers compilation questions; a launch answers startup questions; neither proves a visual or gameplay repair.
4. Continue only when fresh evidence suggests a useful next repair. If the same failure persists twice, revisit the cause using stronger evidence. If a tool is unavailable, retry only after changing something relevant to that failure. Do not turn unavailable visual tooling into repeated setup work.

## Select the relevant branch

- **Blurred, hidden, misplaced, or unresponsive GUI:** read [screen diagnosis](../minecraft-java-developer/references/rendering.md#blurred-or-hidden-screens). Trace background/blur, custom content, parent rendering, widgets, clipping, and input coordinates. Changing GUI scale or global blur settings is a diagnostic comparison, not proof the mod was repaired. Leave user settings unchanged after a diagnostic comparison.
- **World overlay/ESP:** check camera transform, event phase, depth policy, buffer submission, bounded scan results, and world-change cleanup. Confirm the overlay remains correct while moving the camera and after toggling; no render crash is insufficient.
- **Compiler or migration:** identify the failing symbol, import, namespace, dependency, and active version. Repair the first failing layer: toolchain → mappings → Fabric/vanilla API → Mixin → runtime behavior. Read [migration](../minecraft-java-developer/references/migration.md) only as needed.
- **Gradle/Java/dependencies:** separate wrapper/JVM incompatibility, configuration, dependency resolution, and source failures. A network failure does not prove a version is wrong. Check the executing JVM separately from the mod's Java target.
- **Mixin:** preserve target, descriptor, injector, `@At`, ordinal/count, remap/refmap, and side evidence when present. Compare the local annotation with the current target; inspect bytecode only when necessary. Repair the disproved assumption, then exercise application at runtime if that was the failure.
- **Networking:** use [networking](../minecraft-java-developer/references/networking.md). Separate custom payloads from vanilla packets, directional registry/codec from receiver registration, logical destination from callback thread, and local prediction from server acceptance. A vague Netty exception does not establish a payload bug.
- **Server plugin:** establish the actual platform and version, descriptor/enable failure, event or command registration, permissions and callback thread. Use the [server specialty](../minecraft-server-developer/SKILL.md) only for the implicated domain detail. A vanilla networking problem or unexplained ban is not evidence of anti-cheat involvement.
- **Startup/side:** trace the cause chain, init order, physical/logical side, and client-only class reachability. The mod that triggers a failure may not own its cause.

`minecode.analyze_build_failure` and `minecode.analyze_runtime_failure` are optional pattern-based log aids. They do not inspect a screenshot or prove a cause. Use source/mapping tools only for a concrete unresolved question; do not discover optional providers on every defect.

## Finish honestly

Report the symptom, supported cause or remaining hypothesis, change, and result of the original reproduction. If observation is blocked, say “patched; original behavior unverified,” identify the blocker, and provide one specific check. Do not report “fixed” based solely on compilation, launch, or an unrelated improvement.
