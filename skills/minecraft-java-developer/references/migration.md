# Version migrations

Treat a migration as layered repair, not a list of independent compiler errors:

1. Record the old and target Minecraft, Loader, Fabric API, Loom, mappings, Java, and Gradle environments from local configuration; leave computed or conflicting values unresolved.
2. Make the wrapper, Gradle JVM/toolchain, Loom, Loader, repositories, and dependency coordinates coherent before editing Java call sites.
3. Confirm the active mappings namespace. Never combine Yarn, Mojang-official, intermediary, or another namespace by familiarity.
4. Migrate explicit Fabric/Loader API failures using exact target-version primary docs or Javadocs. Then verify vanilla classes, members, fields, and descriptors against target-version source or mappings; change a symbol only when evidence establishes the replacement.
5. Migrate Mixins with the existing failure classification, checking target and descriptor before bytecode/injection point, then remapping/configuration and side.
6. Rebuild and diagnose the next fresh failure rather than continuing through stale output. Runtime-check initialization, Mixins, networking, rendering, and lifecycle behavior when the migration can fail after compilation.

Keep evidence roles distinct: local configuration and source establish the active project; Fabric migration documentation explains API transitions; Mixin documentation explains injection semantics; target-version Minecraft source/mappings establish vanilla identity and descriptors; reference clients show patterns, not compatibility. Prefer exact target-version evidence, label same-family or unknown-version material as supporting context, and use known-mismatched material only to study the old side of a migration delta.
