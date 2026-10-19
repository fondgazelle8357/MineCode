# Grim diagnostic source map

Initial source study: Grim branch 2.0, revision [f5bbe9cf55a631f40b3d28d722d0f82b514e3403](https://github.com/GrimAnticheat/Grim/tree/f5bbe9cf55a631f40b3d28d722d0f82b514e3403), reviewed 2026-10-12. This is not necessarily the user's installed build. Re-resolve the relevant path for that build. MineCode's existing source ID is `grim-anticheat`; use it only after the diagnostic relevance gate is met.

Under `common/src/main/java/ac/grim/grimac/`:

| Diagnostic question | Inspected path and useful boundary |
| --- | --- |
| Which stage receives the event? | `events/packets/CheckManagerListener.java` routes incoming/outgoing events to a player's manager and handles position updates. Configuration and play state have distinct paths; dispatch is not itself a violation. |
| Which checks or processors run? | `manager/CheckManager.java` builds typed listener arrays and dispatches packet, position and post-prediction callbacks. Trace the actual listener, not a filename match. |
| Where does movement processing begin? | `checks/impl/movement/PredictionRunner.java` delegates position updates outside vehicles to the movement runner. It is an entrypoint, not the complete prediction algorithm. Follow the implicated downstream owner only when necessary. |
| Could state ordering explain a false positive? | `utils/latency/LatencyUtils.java` queues work against transaction progress and handles callbacks in its synchronization path. This models ordering; it is not a generic success acknowledgment for a gameplay action. |
| Does an alert prove a ban cause? | `checks/Check.java` separates flag recording, alerting and setback paths. `manager/PunishmentManager.java` loads configured check groups and consequences. The deployed configuration, events and command output are needed to attribute an actual punishment. |

This limited study does not certify check accuracy, thresholds, all protocol versions or live server compatibility. No bypass strategies or threshold-tuning recipes are maintained. Useful false-positive evidence includes the precise check, legitimate action, surrounding state updates, installed versions and reproduction outcome; avoid collecting unrelated player data.

The pinned repository [LICENSE](https://github.com/GrimAnticheat/Grim/blob/f5bbe9cf55a631f40b3d28d722d0f82b514e3403/LICENSE) is GPL v3. This guide describes source structure; no implementation was copied. The registry's reuse/derivation/redistribution approvals remain false. Do not infer permission to transplant code into a differently licensed project.
