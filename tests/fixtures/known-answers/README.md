# Independent mapping answers

These are verbatim Tiny v2 headers, class records and method records extracted
from Fabric's published Yarn artifacts on 2026-10-17. Unrelated records were
omitted; these are mapping excerpts, not Minecraft implementations or complete
source archives. Yarn mappings are [CC0](https://github.com/FabricMC/yarn/blob/1.21.11/LICENSE).
The normal checks are offline and never regenerate expectations from MineCode.

| Yarn version | Public artifact SHA-256 | Original lines in `mappings/mappings.tiny` |
| --- | --- | --- |
| [1.20.4+build.3](https://maven.fabricmc.net/net/fabricmc/yarn/1.20.4+build.3/yarn-1.20.4+build.3-v2.jar) | `7d976ac58cda922a03a1cefe4a5af082758d0c434cc2d6fe2d9a5c20d2da3f1d` | 1, 134561, 134735, 135629 |
| [1.21.11+build.3](https://maven.fabricmc.net/net/fabricmc/yarn/1.21.11+build.3/yarn-1.21.11+build.3-v2.jar) | `296e5cb03a56754e4c9a5fcc60058d54bca5c4d59366425c06aea6b8bf40b6d7` | 1, 86654, 99291, 99432, 100433 |

Independent named-namespace cross-checks:
[1.20.4 InGameHud](https://maven.fabricmc.net/docs/yarn-1.20.4+build.3/net/minecraft/client/gui/hud/InGameHud.html#render(net.minecraft.client.gui.DrawContext,float))
and [1.21.11 InGameHud](https://maven.fabricmc.net/docs/yarn-1.21.11+build.3/net/minecraft/client/gui/hud/InGameHud.html#render(net.minecraft.client.gui.DrawContext,net.minecraft.client.render.RenderTickCounter)).
The former takes `DrawContext, float`; the latter takes `DrawContext, RenderTickCounter`.
Both map intermediary `class_329.method_1753` to `InGameHud.render`.

Tests put these slices in disposable Gradle-coordinate jars and send real MCP
requests. This checks artifact selection, namespace/version provenance, source
retrieval and context expansion. It does not test downloading Yarn, completeness
of a full jar, Mixin application, rendering, or gameplay. To update a pin, retrieve
the official artifact independently, verify its checksum, and review its records
and Javadoc before editing either fixture or oracle.
