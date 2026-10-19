# Third-party notices and reference rights

MineCode's own code and documentation use the MIT License; see [LICENSE](LICENSE). This file credits separately maintained software and records reviewed source restrictions; it does not grant additional rights.

- **REFERENCE:** selective study of external evidence, no implementation copied into MineCode.
- **INTEGRATION:** communicating with separately installed software through MCP. No provider source/binary is bundled.
- **CODE REUSE:** including/modifying third-party implementation. No third-party implementation is copied into the MineCode runtime.

## Optional integrations

[Minecraft Dev MCP](https://github.com/MCDxAI/minecraft-dev-mcp), revision `1120c5b4ad78f56a879553722b23da219208eeeb`, and [MCP Fabric](https://github.com/denfry/mcpfabric), revision `f0acc37be526a7c38e52cf1337f3e60e570b4e9d`, are MIT-licensed. The requested Etoryx repository explicitly directs development to denfry. Their exact license/provenance URLs are in [provider metadata](integrations/providers.json). Retain copyright and permission notices when distributing copies/substantial portions. Provider dependencies and Minecraft/game data have separate terms; the MIT provider license does not relicense them.

### MCDxAI/minecraft-dev-mcp

MIT License

Copyright (c) 2025 Minecraft Dev MCP Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


### denfry/mcpfabric

MIT License

Copyright (c) 2026 dabinayo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.


## Reviewed implementation references

Exact revision-pinned license URLs and limitations live in [the registry](references/sources/sources.yaml); all copying, generated derivation and redistribution approvals remain false. This is an intended-use approval state, not a claim that permissive upstream licenses prohibit all reuse.

| Source | Observed license | Relevant restrictions / attribution |
| --- | --- | --- |
| Sodium | PolyForm Shield 1.0.0 | Noncompete terms and required notices; not unrestricted open-source reuse |
| ViaFabricPlus, ViaVersion | GPL v3 text | Copyleft/source and notice obligations; exact intended use/version review needed |
| XaeroPlus | MIT, copyright rfresh2 | Retain notices; Xaero dependencies have separate terms |
| Sodium Extra | LGPL v3 text | LGPL plus incorporated GPL terms; review modifications/linkage/distribution |
| 3D Skin Layers | tr7zw Protective License | No commercial advantage/monetary compensation; retain notices |
| FancyMenu | DSMSLv3.1, Keksuccino | Custom source/fork/download restrictions; no embedded code/JAR or compiled fork distribution without permission |
| Mouse Tweaks | BSD-3-Clause, Ivan Molodetskikh | Preserve notices/disclaimer; no endorsement grant |
| Fabric Carpet | MIT, gnembon | Retain copyright/permission notices |

Fabric developer docs and release site identify CC-BY-NC-SA-4.0 terms. New summaries are compact original reference notes, not copied articles or reusable code. GitHub PR/comments retain their own authorship/provenance and uncertain page-specific reuse rights; repository license badges are not assumed to license every discussion comment. Maintainer status is recorded only when supported by the inspected association metadata.

## Existing runtime components

MineCode depends on the separately installed official MCP Python SDK (MIT; copyright Anthropic, PBC), Pydantic (MIT; Pydantic Services Inc. and contributors), and PyYAML (MIT; Ingy döt Net and Kirill Simonov). Installed license files were inspected. Package managers retain their full notices and transitive dependency licenses; this file is not a replacement for those distributions' notices.

The distribution bundles MineCode's own skills/guidance, original registry metadata and these notices. No provider source/binary, third-party implementation, downloaded reference snapshot, Minecraft game data or dependency wheel is embedded. Runtime dependencies remain separately installed with their own distribution notices. The Python `build` frontend (MIT, PyPA contributors) is used to validate source and wheel distributions; it is not a runtime dependency or bundled implementation. Existing provider credits and reference restrictions still apply. Install from this repository or a reviewed release artifact. Its MIT license does not relicense dependencies or retrieved material.

## Gameplay and test references

The gameplay registry credits Mojang authors, Minecraft Wiki contributors and named project maintainers per entry. Descriptions are concise original factual summaries; no article images, substantial passages or client implementation code are copied. External material keeps its own rights. Source links and research dates remain in [gameplay metadata](references/gameplay/techniques.json).

The community test suite includes small CC0 Yarn mapping excerpts with origins, artifact hashes and verification instructions in `tests/fixtures/known-answers/README.md`. These are mapping records, not Minecraft implementation source. No Minecraft JARs, game assets, external-client patches or provider binaries are distributed.
