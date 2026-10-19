# Minecraft server operations

Use only for the requested administration task. The host handles shell access, credentials, deployment and permissions; MineCode supplies Minecraft-specific constraints. Do not build a managed server platform.

Identify the affected instance, server implementation/version, Java runtime, world paths and relevant plugins/mods from existing configuration or logs. A proxy, backend server and integrated server are different processes; do not apply backend fixes to a proxy by assumption.

- **Configuration:** use documentation for the installed build and identify whether the setting needs a restart or supported reload. Preserve comments and unrelated values. Do not recommend broad permission grants, disabling authentication or weakening checks as a generic troubleshooting step.
- **Backups/updates:** establish a consistent world/config/plugin-data snapshot using the server's supported save/quiesce procedure or a clean stop. A copy of changing world files is not demonstrated recovery. Preserve the old binary/config and test restoration in an isolated directory when recovery assurance is requested. Version downgrades can be incompatible with newer world data.
- **Performance:** distinguish client FPS, network latency and server tick time. Inspect a representative profile and workload before changing view distance, simulation distance, chunk generation or plugins. Average TPS alone can hide tick spikes; compare the same workload after the relevant change. Avoid cargo-cult JVM flags and unbounded profiling on production.
- **Deployment:** a local build does not authorize restarting a live server or replacing its world. Follow the user's actual deployment scope and the host's permissions. Report interruption and rollback requirements when relevant, not as a checklist for every edit.

Use the existing server tools and logs. A restart or error-free log alone does not establish the requested in-game outcome.
