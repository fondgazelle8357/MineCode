# Development workflow

Inspect before inventing. Find the code that already owns the behavior, check the project's version and mappings, then make the smallest change that solves the task. Research when evidence is missing—not as a ritual before every edit.

The coding agent does the reasoning and editing. MineCode's [developer instructions](../skills/minecraft-java-developer/references/workflow.md) tell it how to investigate Minecraft-specific questions, follow existing architecture, and check its work. Simple tasks should stay simple; builds and game launches belong where they answer a real question.

## Verification model

Use the scoped [verification labels](../skills/minecraft-java-developer/references/workflow.md#reporting-verification): CODED, BUILT, LOCAL RUNTIME TESTED, DEDICATED VANILLA SERVER TESTED, BEHAVIOR VERIFIED, MULTIPLAYER SUITABILITY UNVERIFIED and PERMITTED SERVER TESTED. Tested does not imply passed. Record artifact/revision, version, scenario, environment, observation method, outcome and limits. Build success and server readiness do not prove acceptance; a separate loopback server does not establish real network conditions.

For external research, read the [evidence policy](EVIDENCE_POLICY.md) and [retrieval guide](RETRIEVAL.md). [Optional providers](PROVIDERS.md) are only needed for their specialized operations. The [runtime reference](../mcp/README.md) defines tool limits, and the [capability scope](CAPABILITIES.md) shows what we've actually checked. MineCode doesn't turn a successful session into an automatically learned rule.
