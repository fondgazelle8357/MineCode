# Networking

First decide whether synchronization is needed. Keep presentation-only client state local. For shared or gameplay state, identify the authoritative logical side and direction—C2S request/report, S2C synchronization, both, or neither—and define what the server can independently validate before accepting client input.

Separate two paths. **Mod custom payload networking** uses the active generation's payload/type, codec, directional registry, receiver and play/configuration lifecycle. **Vanilla/client network behavior** observes or sends existing Minecraft packets through the project's packet events, hooks or network manager. Do not create a custom payload or another dispatcher when the established vanilla/project path already owns the behavior.

For a custom payload change:

1. Trace the project's client/server entrypoints and networking helper before using raw Fabric calls.
2. Resolve the active Minecraft/Fabric generation from local declarations and source. Then use exact-version Fabric documentation/Javadocs and, if needed, Fabric API source; do not mix method names or lifecycle assumptions across generations.
3. Verify the payload type and codec are registered for the correct direction and play/configuration phase on every required physical side before receiver registration. Register the receiver only on the logical destination.
4. Confirm callback thread semantics, player/world availability, connection lifetime and disconnect/world-change cleanup before mutating state.
5. Build for static compatibility, then runtime-test the relevant connection and delivery path when registration or delivery behavior matters. Compilation does not prove the peer accepts the payload or the handler runs.

Treat C2S gameplay data as a request or observation, not truth. Validate permissions and facts the server owns—such as player state, reach, target existence or current inventory—before mutation or broadcast. Synchronization communicates state; it does not grant authority.

Bound payload sizes, collection lengths, numeric ranges, frequency and queued work before expensive processing. Reject malformed or unauthorized requests without partial mutation. Preserve session identity when dispatching to the owning game thread; discard delayed work after disconnect/world replacement. Distinguish send, receive, validation, authoritative mutation and client synchronization in observations. For client automation using vanilla interactions, read [stateful automation](automation.md); do not add a custom acknowledgment protocol the peer does not implement.
