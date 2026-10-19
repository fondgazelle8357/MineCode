# New Fabric projects

Use only for an empty workspace or an explicit replacement of the build foundation.

1. Honor a requested Minecraft version and loader. If unspecified, choose a stable version with a known compatible toolchain and state the choice briefly; ask only if a missing compatibility requirement materially changes the result. Do not start project inspection in an empty directory.
2. Use an official template/generator configured for that Minecraft version. A version-named template branch can still update its Loom and wrapper: inspect its declared Loom, Gradle wrapper, and required Gradle JVM together before adopting it. The Java target of the mod does not establish the JVM needed to run Loom.
3. Prefer a compatible pinned template revision or a previously verified combination when available. Do not pull a moving latest build tool into an older game target without checking compatibility. If repairing an actual mismatch, change only the incompatible layer. Do not install a new JDK or downgrade several dependencies by reflex.
4. Set mod ID/package, resources and source sets for the requested physical/logical side. Register common gameplay/content through the common initializer; add a client initializer only for client work and server-specific hooks only where needed. Prefer supported Fabric hooks. Ordinary content needs registration and data/resources, not a client module framework. A small client feature can likewise stay small.
5. Implement the requested behavior, then build the artifact once. A separate blank-template build is useful only if unresolved build-foundation uncertainty would otherwise block substantial work. Inspect the actual Loom/build configuration to identify the distributable; sources, stale and development artifacts are not interchangeable with it.

Use current local evidence first. If it is insufficient, retrieve the specific official version/template evidence needed, then stop. This guide deliberately does not present one dependency tuple as universally current.

For a custom GUI or overlay, read [rendering](rendering.md) before choosing the screen/render path. Spend effort on the requested interaction and appearance, not extra settings or setup reports. Launch when it answers a real runtime question; for visual acceptance, inspect the feature itself.

For a suspiciously small JAR, identify its source revision and inspect compressed/uncompressed contributions, expected classes/resources, metadata, entrypoints, Mixin configs, access wideners and nested versus external dependencies. Compare contents with requested capabilities and install in a clean compatible instance where needed. Size alone establishes neither completeness nor a defect; never pad it. If the delivered artifact is unavailable, leave its completeness unresolved. The MineCode Python wheel is a different artifact from a generated Minecraft JAR.
