---
name: minecraft-project-inspector
description: "Resolve missing Minecraft Java project context in unfamiliar codebases: version, loader, mappings, source sets, side, and behavior ownership. Use only when these facts affect the task; skip when already established or the workspace is empty."
---

# Minecraft project inspector

Find the minimum context that changes the implementation, then return to coding.

1. Reuse known environment facts for the active module. An empty workspace needs project creation, not inspection.
2. Read the relevant owner and one or two nearby features. Trace only the registration, lifecycle, settings, or shared controller needed for this change. Filenames alone do not prove ownership.
3. Resolve consequential unknowns: Minecraft/API version, loader, mappings, physical/logical side, source set, or Mixin target. Follow build variables to their definitions; leave computed or conflicting values unknown.
4. If the runtime's metadata inspection helps, use `minecode.get_project_profile` once. It includes detection; do not call both profile and detect, or repeat a profile without relevant configuration changes. Ordinary host file reads may be enough.
5. Stop once the owner, applicable API, and relevant side constraints are understood.

Use richer inspection for a migration, conflicting build declarations, or architecture that remains ambiguous. Distinguish the current declared version from the requested target, the compile target from the JVM running Gradle, and declared dependencies from resolved dependencies. Static metadata does not describe the whole client architecture.

Do not execute Gradle for orientation, discover providers by default, or download references to fill unused profile fields. Build state matters only when it affects the task or the user requests it.

Keep the result brief: relevant owner/convention, consequential environment facts, and unresolved blockers. Distinguish observed facts from likely conventions when the difference matters. Do not generate an ownership document or exhaustive project report unless asked.
