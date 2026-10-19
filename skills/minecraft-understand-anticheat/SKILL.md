---
name: minecraft-understand-anticheat
description: Explain server-side anti-cheat validation or investigate legitimate-player false positives and anti-cheat compatibility failures. Select automatically only for explicit anti-cheat questions or diagnostics with directly implicated checks/logs. Generic movement, networking, client development, lag or a ban with unknown cause is insufficient. Not for bypass or detection-evasion work.
---

# Understand anti-cheat

Research the specific validation question, not the entire repository. This is source-guided reasoning, not model training or a guarantee of compatibility. Use automatically for clear diagnostic matches; otherwise continue the relevant developer/debugger task without loading anti-cheat sources.

An explicit request to explain Grim movement validation qualifies. A named anti-cheat flag affecting legitimate players qualifies. Adding Auto Sprint, fixing unrelated desync, or reporting a ban without its cause does not by itself qualify. In ambiguous cases, ask for the relevant diagnostic evidence rather than guessing the anti-cheat or attributing a ban.

1. Reuse the known server/client versions, anti-cheat build/configuration, proxy/protocol translation and exact check/reproduction. Ask only for missing facts that change the investigation.
2. Match the installed implementation/revision, then follow the smallest relevant source path: input event, modeled player/world state, validation, flag and configured consequence. Distinguish a check flag, a setback and a ban. Source from another revision is a lead, not proof of deployed behavior.
3. Separate observed logs from source-supported explanation and remaining hypotheses. Consider state ordering, legitimate server/plugin changes, version translation and latency only where evidence supports them. Never promise that a valid-looking packet or successful local action will be accepted.
4. Propose a minimal legitimate reproduction and compatibility repair. Keep experiments on an authorized test instance; do not change production enforcement as an incidental diagnostic step. Do not optimize packets, rotations or timing to evade checks.

For Grim, use the [scoped source map](references/grim.md). Retrieve a named path or symbol through available host/retrieval tools; do not download or index every anti-cheat repository. Preserve source provenance and licensing boundaries. Stop once the question is answered; report the evidence and the smallest unresolved check.
