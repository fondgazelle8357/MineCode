# Supporting Minecraft development workflow

Use the [developer skill](../SKILL.md) as the entry point. Resolve the current question, implement, and finish; no reference is a mandatory stage.

Select the relevant [ordinary mod](../SKILL.md), [client](../../minecraft-client-developer/SKILL.md) or [server](../../minecraft-server-developer/SKILL.md) specialty. Do not load all three. Read only the task's relevant guide:

- [New Fabric projects and compatible foundations](new-project.md)
- [Screens, rendering, ESP, and input](rendering.md)
- [Existing architecture and Mixins](integration.md)
- [Networking](networking.md)
- [Movement, rotations, inventory, and combat](movement-inventory.md)
- [Stateful automation and shared ownership](automation.md)
- [Version migrations](migration.md)

## Reporting verification

These labels describe scoped evidence, not a ladder or mandatory stages:

| Label | Evidence |
| --- | --- |
| CODED | Implementation exists; execution has not been established. |
| BUILT | Identified build completed successfully. |
| LOCAL RUNTIME TESTED | Named local scenario exercised; specify integrated server or other setup and outcome. |
| DEDICATED VANILLA SERVER TESTED | Scenario exercised against a separate vanilla server process; specify version and outcome. |
| BEHAVIOR VERIFIED | Defined acceptance criteria observed satisfied in the named environment. |
| MULTIPLAYER SUITABILITY UNVERIFIED | Evidence insufficient for the claimed multiplayer environment or behavior. |
| PERMITTED SERVER TESTED | Tested on an identified server where behavior was permitted; record configuration and outcome separately. |

Tested does not mean passed. Attach revision/artifact, version, scenario, environment, observation method and limitations to consequential claims. A loopback dedicated server is a separate process, not evidence of real-world latency/loss. Mocks do not replace live game evidence. Visual success requires inspecting the screen. A patch is an attempted fix until the original failure is reproduced and observed resolved under comparable conditions. Missing mandatory release evidence leaves a gate pending.
