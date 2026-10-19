# Evidence and research policy

**External reference sources are evidence, not authoritative truth.** The registered library is never blindly trusted. A source can be outdated, incomplete, poorly engineered, incorrectly mirrored, specific to a different version/loader/mapping/architecture, or contradictory with current documentation. Applicability and rights must be evaluated before adopting its ideas.

## Evidence hierarchy

For exact game behavior, use:

1. Target-project source/configuration for integration context.
2. Exact local Minecraft/Fabric source matching the target for game behavior.
3. Exact-version Fabric API and Javadocs.
4. Exact-version official documentation and reference projects.
5. Maintained client architecture references.
6. Older/specialized evidence only where relevant.

Project code can be defective; investigate contradictions with exact game behavior. Build/runtime observations answer different questions and are not universal source authority. A compilation cannot disprove a server-sequencing defect. Pin consequential evidence to version, mappings and source revision/path; distinguish observed implementation, documented contract, inference and uncertainty. Stop retrieving once the question is answered.

## Research escalation

Do not automatically research the web for every task. An agent must research current primary sources when an API is uncertain, examples conflict, an implementation fails unexpectedly, Minecraft versions differ significantly, loaders/mappings do not match, no relevant source clearly applies, a source seems outdated, local evidence cannot explain an error, a method/class/signature appears changed, or licensing/provenance is unclear.

Prefer official Fabric documentation, official project documentation, official source repositories, mapping/source information, current maintained implementations, then community examples when stronger sources are insufficient.

Resolve the missing evidence, implement, then check the behavior affected by the change. Build or launch only when the task or remaining uncertainty calls for it. One GitHub example is not proof of compatibility or correctness. This rule applies throughout MineCode. Network retrieval requires a separate startup opt-in. See [retrieval](RETRIEVAL.md).

## Compatibility and rights

Before applying an external implementation idea, compare Minecraft version, loader, language, mappings, relevant API generation, client/server environment, and architecture. For example, a Phobos 1.12.2 combat concept does not establish that its exact implementation works in Fabric 1.21.x. Preserve useful concepts while rechecking current implementation details.

Record origin/revision, applicability, verification state, and remaining uncertainty when using a source. Follow [licensing and provenance policy](LICENSING.md); a detected license or public repository alone does not authorize copying or redistribution.

## Developer explanations and optional tools

For written developer guidance use: current applicable official docs/source → maintainer-authored documentation/articles → provenance-backed maintainer issue/PR explanations → high-quality community technical writing → general discussion. Preserve author status and unknown version/mapping context. Historical importance is independent of modern compatibility; Phobos, Wurst+2 and Wurst+3 can be important architecture references without supplying modern signatures.

Specialized provider results remain evidence under the same hierarchy. Prefer integration over duplication when the maintained open-source provider is compatible, appropriately licensed and effective; keep a replaceable boundary and explicit unavailable fallback. Failure diagnoses are sanitized candidate evidence, not automatically verified lessons or promoted knowledge.

## Verification and terminology

Use the explicit [verification model](WORKFLOW.md#verification-model), with task-specific evidence and limits.
A Gradle exit code alone does not establish runtime success; inspect any crash log.
Server readiness does not prove packet delivery, client behavior or gameplay. See the current [capability evidence](CAPABILITIES.md#runtime-and-behavior-evidence).

[Gameplay terminology](RETRIEVAL.md#gameplay-terminology) is a manually reviewed, static factual reference. Source confidence is
not runtime verification; publication-era mechanics, informal meanings, server dependencies and timing uncertainty remain visible.
Developer/automation implications are explicitly analysis. No automatic learning or promotion occurs.
