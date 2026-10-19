# Movement and rotation

Classify the intended effect before choosing state: a visual camera turn, local player yaw/pitch, body/head/render pose, movement-relative orientation, server-visible facing or action, or a temporary rotation request. These surfaces can intentionally differ; changing one does not prove the others changed.

Start with local ownership. Find the existing rotation or movement controller, then inspect one or two features that use the same path. Trace the request API, camera/requested/last-transmitted rotation state, priority or arbitration, overwrite points, movement correction, and release/restore behavior only when present and relevant. A simple visual turn may use the project's direct local path when no manager or network behavior owns it; do not invent a controller for that case.

Trace the project's real timing from raw or transformed input through its tick, input, movement, interaction, packet, and render hooks. Apply state in the phase the existing owner expects; there is no universal pre/post event rule. For a server-facing action, reuse the established vanilla-packet or project-network path and its authority rules rather than adding custom synchronization.

For movement-relative behavior, identify the input source, the yaw used as its frame of reference, any existing transformation/helper, who owns the resulting movement, and when later code can overwrite it. Movement correction is needed only when the requested server-facing orientation differs from the local movement/view frame. Reuse the project's correction behavior and settings; do not import a generic algorithm without confirming the active version's input and movement semantics.

Temporary requests need explicit end conditions. Release or restore them when the action ends and on relevant disable, disconnect, player/world loss, or world change without stealing control from a higher-priority request. Where the affected path requires it, wrap angular deltas, respect its pitch bounds, preserve previous/current values used for interpolation, and avoid a visible or server-facing discontinuity on restore.

A build can verify names and signatures, not rotation behavior. When runtime verification is required, observe the intended surface: camera/render result, movement direction, server-facing interaction, competing-module priority, and release/restore behavior.

# Inventory

Classify the intent before choosing an inventory path: read-only item search, local hotbar selection, selection for a server-relevant action, interaction with an open screen/container, an actual move/swap/click, or temporary selection/use. Observation alone should not introduce clicks or networking, and a selected-slot change is not the same operation as transferring an item.

Establish the slot domain before translating or mutating anything. A player inventory index, hotbar position, selected hotbar slot, screen-handler slot ID, logical armor/offhand location, and cursor/carried stack are not interchangeable. Prefer the project's slot abstraction or helper, then the active handler and exact-version Minecraft source; do not use remembered magic numbers or a universal container layout.

Start with local ownership. Find any inventory manager, helper, action queue, or slot abstraction and inspect one or two inventory features that use it. Reuse its search, selection, click/action, arbitration, and cleanup paths rather than adding raw duplicate logic. When a screen is involved, establish which handler is active and which current handler state makes the action meaningful, including relevant container identity, slots, cursor state, tracking/revision, action type, and open/close lifecycle; exact names and mechanics remain version-sensitive.

Separate client observation or prediction, the requested action, and the authoritative server/container result. Directly changing a client stack does not establish server inventory state. When synchronization matters, identify the existing project or vanilla path and the later handler update, selected-state observation, or gameplay result that provides scoped evidence of the outcome; do not assume a generic acknowledgment exists; inspect exact-version packet identity or order only when that distinction affects the implementation.

Trace the local timing and ownership through player/world availability, input or tick phase, the current screen/handler, and any pending action. Do not invent a universal queue or delay. A temporary selection or action must release or restore on its normal completion and relevant disable, screen change/close, disconnect, or world change, but only while it still owns the state; do not overwrite a newer user or feature selection.

A build verifies API compatibility, not inventory behavior. When runtime verification is required, observe the intended slot domain, selected item or handler/cursor state, authoritative item/count update or resulting gameplay action, competing ownership, and cleanup.

# PvP and combat

Resolve the mechanic before choosing implementation APIs. A gameplay term can identify vocabulary and possible state, but it does not establish exact timing, version behavior, server rules, packet order, or a project integration path. If the term is ambiguous, establish the intended mechanic and observable outcome first.

Identify only the state surfaces that mechanic needs: target and entity state; distance, collision or visibility; attack, interaction, cooldown or item-use state; movement and facing; held item or inventory state; block/world or projectile state; and local, transmitted or server-authoritative results. Do not turn this into a universal combat model.

Start with local ownership. Inspect one or two similar features and reuse the project's target/interaction path plus its existing movement, rotation, inventory, event and network owners. A sprint or movement feature should follow the current input/attack path; a rotation-dependent action should use rotation arbitration; a temporary weapon action should use inventory selection/restoration ownership. Do not add a parallel combat state machine to coordinate systems the client already owns.

Establish version-sensitive mechanics from the active project's exact-version Minecraft source and relevant Fabric behavior. For block/entity/projectile mechanics such as crystals, anchors, pearls or mace attacks, confirm only the placement, collision, fall/item, target or world conditions that affect the requested feature. Timing may depend on cooldown state, movement, held item, latency, server ticks and plugins; do not hardcode a remembered delay, reach value or guaranteed outcome.

Keep authority explicit: distinguish client input/request, prediction or animation, transmitted action/state, and the server-owned result. A successful send, local target mutation, animation, build or temporary inventory change does not prove a hit, knockback, placement, explosion, teleport or item action occurred. Define the observable game/server result that would demonstrate success before claiming behavior is verified.

Inspect packet identity or ordering only when the mechanic genuinely depends on it. Reuse the project's packet/event path, preserve relevant state ordering, and verify exact-version behavior rather than inventing a sequence from memory. Historical clients may explain decomposition but not modern compatibility or reuse rights.

For multi-step actions and interruption, read [stateful automation](automation.md). Local success does not establish remote acceptance or server permission.
