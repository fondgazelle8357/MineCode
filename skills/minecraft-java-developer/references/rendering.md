# Rendering, screens, and input

Read the section for the requested surface. Use the active version and mappings; a familiar class name does not establish its call order or coordinate space.

## Screens that remain readable

Choose the intended layout before coding: clear hierarchy, a small set of primary controls, consistent spacing/type/color, visible selection and disabled states. Put advanced settings behind a section or disclosure. A requested polished interface is not satisfied by exposing every variable in a dense grid. Use the host's design ability and the project's existing widgets/theme; MineCode's job is to prevent Minecraft-specific mistakes.

Use screen/GUI-scaled dimensions for both drawing and hit testing. Recompute layout on resize/init; make content reachable at small window sizes and larger GUI scales. Handle clipping, scrolling, focus, drag/release, Escape, and saving through the existing screen/widget lifecycle. Do not rebuild widgets each frame.

Trace the parent screen's render method **before** positioning a `super.render(...)` call. Determine who draws the background, applies blur, submits custom content, and draws widgets. There is no cross-version rule that the parent belongs at the end.

### Minecraft 1.21.1: a concrete blur trap

Verified against the 1.21.1 client bytecode and Mojang mappings: `Screen.render(GuiGraphics,int,int,float)` invokes `renderBackground` before rendering registered widgets. The default `renderBackground` calls `renderBlurredBackground(float)` and then the menu background. Drawing custom content before `super.render(...)` therefore puts it before the parent's background/blur pass. Explicitly drawing the background and then calling the parent can also apply that pass twice.

For a 1.21.1 Mojang-mapped `Screen` that uses registered widgets, one supported ordering is to place panel drawing in the background override after the vanilla background, and let the parent draw widgets afterward:

```java
@Override
public void renderBackground(GuiGraphics graphics, int mouseX, int mouseY, float delta) {
    super.renderBackground(graphics, mouseX, mouseY, delta);
    // Original example: panel behind the screen's registered widgets.
    graphics.fill(12, 12, this.width - 12, this.height - 12, 0xE6101218);
}
```

The screen's normal render path calls `super.render(...)` once; do not also call `renderBackground` there. Draw any foreground decoration after the parent only when it should cover widgets. If the design deliberately needs no vanilla blur, override this screen's background path to draw its own background instead of calling the default; do not silently disable the player's global blur setting. Recheck this ownership on other Minecraft versions and custom base screens.

Mapping evidence: [Fabric's 1.21.1 Screen API](https://maven.fabricmc.net/docs/yarn-1.21.1%2Bbuild.1/net/minecraft/client/gui/screen/Screen.html). That Yarn build calls the blur method `applyBlur(float)`; the example above uses **Mojang** names. Method names and signatures differ across mappings and later versions. The Javadoc identifies methods; the local bytecode established their call order.

### Minecraft 1.21.11 is a different render path

Exact local Mojang-mapped 1.21.11 source shows `Screen.renderWithTooltipAndSubtitles` calls `renderBackground`, advances strata, then calls `render` and deferred elements. Here `render` itself draws registered renderables; the 1.21.1 parent-call explanation must not be transplanted. `renderBlurredBackground(GuiGraphics)` schedules blur before the current stratum. Input also uses event objects such as `KeyEvent`. Inspect the actual generation before overriding methods. [Yarn 1.21.11 build 3 API](https://maven.fabricmc.net/docs/yarn-1.21.11+build.3/net/minecraft/client/gui/screen/Screen.html) supplies mapping identities, not this call-order proof.

## Blurred or hidden screens

1. Identify what is blurred: the world behind the screen, the panel/text, or the whole frame. Inspect the screen code and the active parent/background path. Clean logs do not eliminate a rendering-order defect.
2. Trace background/blur -> custom panel -> widgets/text -> tooltip/foreground, including deferred buffer submission and clipping. Look for a late or duplicate parent/background call before assuming fractional scaling, font filtering, or shader incompatibility.
3. Compare with background blur disabled only as a diagnostic when useful and authorized. If the symptom disappears, investigate this screen's blur/compositing path; this comparison does not prove which call is wrong. Restore the setting afterward. A source change must work with the user's normal settings.
4. Patch the cause supported by that trace, then reopen the same screen under the original blur setting, GUI scale, and window size. Check readable text, unclipped controls, matching click positions, scrolling, and close/reopen persistence. If the screen cannot be observed, report the repair as unverified.

## World overlays and ESP

- Choose the Fabric/world render phase and supplied context for the exact version. Establish whether matrices already include the camera offset; subtract the camera once. Interpolate moving entities using the provided tick delta when appropriate.
- Separate depth-tested outlines from through-wall drawing. Define the depth policy in the selected render layer/pipeline and verify actual buffer submission; a temporary depth toggle restored before deferred drawing is not evidence of through-wall output. Keep blend/depth/shader changes from leaking into later rendering.
- Scan loaded world data with a bounded per-tick budget and retain results for rendering. A radius cap alone does not bound a cubic scan's cost. Avoid chunk loads and full-volume scans each frame. Clear or invalidate results on dimension/world changes, unloads, target changes, and disable. Prune stale blocks and entities. Bound retained results and scan frequency as well as work per update. Do not move unsafe world access onto background threads. Avoid hot-path allocations, blocking I/O, duplicate subscriptions and retained world references; release rendering resources through existing lifecycle hooks. Measure a relevant performance concern in the same scene/environment; do not invent FPS gains.
- Make the requested targets configurable using actual registry IDs or the project's existing target selector. Preset groups can help but should not silently replace arbitrary target selection when the request calls for it.
- Verify the requested effect near and behind geometry, while moving the camera, after changing a target, and after a world transition when those behaviors are in scope. Watch frame responsiveness; drawing something once proves little about correctness or cost.

## HUD and input

Use the supplied GUI coordinates, anchoring, and lifecycle for a HUD. Keep gameplay decisions and expensive computation in tick/state owners. Reuse the existing HUD or settings owner instead of adding a parallel framework.

For a keybind, decide press edge versus held behavior and what happens while a screen is focused. Toggle once per press; polling a held key each tick should not repeatedly toggle. Respect chat/text-entry focus, widget event consumption, rebinding, understandable collisions and unbinding. Release temporary state on relevant close, focus loss, disable, and world/player loss.

## Verification that answers the request

A build checks API compatibility. A launch checks only the runtime path exercised. For visual claims, inspect the actual screen or overlay and use its controls with normal game settings. A failed screenshot helper does not justify repeatedly relaunching or claiming visual success. Use another already-available observation path if practical; otherwise identify the unverified behavior and one concrete manual check.
