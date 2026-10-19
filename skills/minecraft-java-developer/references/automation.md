# Stateful gameplay and server authority

Read for multi-step automation or competing temporary control, not ordinary presentation or simple Auto Sprint. Reuse the project's mechanism; a small state machine or coroutine is sufficient. MineCode supplies constraints, not a scheduler framework.

## Define what can be known

Separate client presentation, prediction, requests transmitted, synchronization observations, and server-authoritative outcomes. A swing, local assignment, interaction return value, packet send, or elapsed delay does not prove acceptance. Even a later client world update can be indirect evidence: specify what it establishes and what remains unknown. Do not invent a generic slot/rotation/action acknowledgment.

Use target-project source for integration and exact-version Minecraft source for behavior. Record only relevant version, loader, mappings namespace/revision, Fabric API, Loom and Java facts. Prefer established interaction pathways that perform selection synchronization, prediction bookkeeping and sequencing. Raw packets require an actual need and exact-version evidence. Revalidate hand, item/count, slot domain, cooldown, screen/handler, range, target validity and applicable world conditions immediately before each transition.

## Smallest correct progression

intent â†’ validate â†’ acquire ownership â†’ next valid transition â†’ observe â†’ continue/wait/abort â†’ conditionally restore â†’ release

For a nontrivial sequence, name its preconditions, current step, expected transition, owned resources, completion predicate, justified minimum delay, bounded deadline, cancellation conditions, outcome and cleanup. A setting can impose a minimum interval; it cannot replace the required state observation. Yield to the game loop; no sleeps or busy waits on client/render threads. Tick counts and elapsed time differ. Choose timeout semantics deliberately: check a monotonic deadline before resuming work after a stalled loop, and invalidate work on lifecycle transitions. Do not mutate game state from a timer thread.

After potentially partial success, reconcile observable state or abort as uncertain. Never blindly retry consumption, placement or another non-idempotent action merely because confirmation is missing. A timeout is not proof of failure on the server. Bound queued work and emitted actions; revalidate after every wait. Cancellation must invalidate already-queued callbacks, including disable/re-enable and replacement of a world or connection. An operation/session generation or the established cancellable scope can provide that boundary.

## Ownership without stale restoration

- **Inventory/hotbar:** distinguish selected hotbar index, inventory index and active screen-handler slot ID. Snapshot only what is needed. Track the owner and session, selection changes and valid restore context. Respect manual changes, including away-and-back changes that a simple equality check misses. Restore only while ownership and context remain valid; never overwrite newer user input or a successor owner. Sent selection is not confirmed server selection.
- **Rotations:** distinguish camera, requested, last transmitted and actually observed correction state. Never rename last-sent values as server-confirmed. When multiple consumers contend, use one arbitration point with explicit priority/tie handling, preemption, expiry, handoff and release. Respect manual input and the project's movement conventions.
- **Input:** track synthetic contributions separately from physical keys. Removing automation must preserve keys the user still holds and stop repeated interaction. A simple Auto Sprint can use a small input/lifecycle hook; it does not need inventory or rotation managers.
- **Shared control:** acquire all needed resources coherently or release and retry acquisition within a bound. Do not hold one indefinitely while waiting for another. Invalidate a preempted operation before granting new ownership, so its delayed cleanup cannot restore over the successor.

Cleanup is idempotent, tolerates missing player/world/network objects, and releases subscriptions, queued work and owned state. Cover manual input, disablement, competing features, screen changes, death, respawn, dimension/world replacement, disconnect, timeout and exceptions. After disconnect or session replacement, discard old work without sending stale interactions or restoring into the new session.

## Mechanic-specific decisions

- **Anchor:** validate each placement/charge/use transition and dimension behavior against the target version. Offer meaningful targeting, timing, supported behavior and cancellation controls; do not turn every internal variable into a setting. Reported beta success is historical evidence, not proof of new code.
- **IPC:** upward and directional/crosshair behavior are distinct modes. Use the answered request; clarify an unresolved mode once. Validate item availability, ordering, cooldown, interruption and the observable projectile/outcome for the chosen mode. A projectile animation alone is insufficient.
- **Auto Tool:** cooperate with the current breaking interaction and manual selection; avoid switching oscillation. Temporary selection needs conditional restoration when applicable.

## Checks that establish the claim

Define acceptance before testing. Exercise normal completion and applicable missing/consumed items, invalid/unloaded targets, cooldown, delayed/rejected/missing updates, timeout after partial success, manual slot changes, competing ownership, screen changes, disable/re-enable, death, disconnect, world replacement, stale callbacks and ordinary latency/tick variation. Observe no stuck input, stale restore, indefinite ownership or duplicate action. Model tests help but do not establish live behavior.

Record artifact/revision, game/toolchain, scenario, environment, observation method, outcome and limits using the [verification vocabulary](workflow.md#reporting-verification). Local integrated-server success and a loopback dedicated process do not establish remote network behavior. Technical correctness, server permission and policy enforcement are separate. Use only permitted controlled testing; no enforcement probing, detection evasion or evasion-oriented timing randomization. Never promise ban safety or universal multiplayer compatibility.

### Exact 1.21.11 example of the distinction

In Mojang-mapped `MultiPlayerGameMode`, `useItemOn`/`useItem` synchronize carried selection and run prediction before returning the local result. `ServerGamePacketListenerImpl.handleUseItemOn` acknowledges the sequence before its range/location/world checks and later sends block updates. Thus a sequence acknowledgment is not proof that the gameplay action succeeded. `handleSetCarriedItem` validates the slot and changes server inventory selection without providing a generic per-request success acknowledgment. These observations are specific to 1.21.11. For the pinned source archive hashes, run `minecode resources` and read `docs/RETRIEVAL.md`, section “Automation architecture research,” inside that bundle.
