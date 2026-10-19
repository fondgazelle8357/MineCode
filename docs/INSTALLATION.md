# Installation

MineCode runs locally with Python 3.11+. It includes six Markdown skills and one MCP stdio server. Install it in a dedicated Python environment, then connect it to your Minecraft project. The host needs local skills and MCP support; the project's Java/build requirements are separate.

## Primary installation

Clone or download this repository and open a terminal in its root. Install from source below. For a reviewed release wheel, replace `.` with its filename, such as `./minecode_runtime-0.4.0rc3-py3-none-any.whl`, and compare its SHA-256 with the release checksum. Don't assume a similarly named package from a package index is MineCode.

### Windows - PowerShell

```powershell
py -3 --version
py -3 -m venv "$env:LOCALAPPDATA\MineCode\runtime"
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\python.exe" -m pip install .
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod"
```

Select Python 3.11 or newer and replace the project path with an existing folder. Installing dependencies may require network access.

### Linux and macOS

```sh
python3 --version
python3 -m venv ~/.local/share/minecode/runtime
~/.local/share/minecode/runtime/bin/python -m pip install .
~/.local/share/minecode/runtime/bin/minecode setup --host codex --project /absolute/path/to/MyMod
```

## Choose your host

Run setup for each project and host. It writes project-local configuration and records managed files. Conflicting or modified files are preserved; use [preview and merge](ADVANCED_SETUP.md#existing-host-settings) when configuration already exists.

| Host flag | Skills | MCP configuration |
| --- | --- | --- |
| `--host codex` | `.agents/skills/` | `.codex/config.toml` |
| `--host claude` | `.claude/skills/` | `.mcp.json` |

For Claude Code on Windows:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host claude --project "C:\Projects\MyMod"
```

On Linux/macOS use the same arguments with `~/.local/share/minecode/runtime/bin/minecode`.

Generated Codex configuration uses a separate 30-second startup timeout and a 630-second per-tool timeout. This accommodates MineCode's unchanged maximum 600-second execution budget plus bounded cleanup and response overhead. Other hosts may need an equivalent timeout adjustment; their own policies still apply.

Open the selected project, review trust/MCP prompts and start a fresh session. Codex loads project MCP configuration only for trusted projects. Claude Code uses its project MCP approval flow. Setup doesn't grant trust, edit global host configuration or override managed policies. A nested checkout may have a different project root from its parent.

Host references: [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Claude Code skills](https://code.claude.com/docs/en/skills), [Claude Code MCP](https://code.claude.com/docs/en/mcp). Other hosts can use the same [runtime and skill files](../mcp/README.md#install-and-connect); their discovery/approval mechanisms vary.

## Verify activation

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" doctor --host codex --project "C:\Projects\MyMod"
```

Use `--host claude` for that integration. Doctor is read-only: `configured_unverified` means files match the runtime, not that a model has called its tools. `skills_only` is intentional when you used `setup --skills-only`. Resolve missing or mismatched files before testing the full connection.

In a fresh host session, ask the agent to call `minecode.get_project_profile` and check the returned project and versions. Inspect an actual tool result. Configuration, connectivity and invocation are separate. See [troubleshooting](ADVANCED_SETUP.md#health-and-recovery) if tools are missing.

## Permissions

Setup leaves build execution, reference downloads and providers off. Local inspection, cached source lookup and supplied-log diagnostics work without these opt-ins. Enable only the [permissions](ADVANCED_SETUP.md#permissions-and-paths) you need. Builds use trusted project scripts; these flags aren't an OS sandbox.

Generated configuration contains machine-specific paths. Keep it and installation records out of shared commits. Review output before sharing: your coding host may send paths and source excerpts to its model service.

## Updates and uninstall

Update the same Python environment from reviewed source or a wheel, then rerun setup for each project and host. From the updated repository root:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\python.exe" -m pip install --upgrade .
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" setup --host codex --project "C:\Projects\MyMod"
```

For a wheel, replace `.` with its path. A replacement wheel with the same version requires `--force-reinstall --no-deps` when required dependencies are already installed. Keep the previous reviewed artifact for rollback. Include permission flags you intend to retain when rerunning setup, then restart the MCP connection/session.

Remove the integration from **each project first**, then uninstall the runtime:

```powershell
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\minecode.exe" remove --host codex --project "C:\Projects\MyMod"
& "$env:LOCALAPPDATA\MineCode\runtime\Scripts\python.exe" -m pip uninstall minecode-runtime
```

Repeat with `--host claude` where installed. Unchanged managed files are removed; modified files are retained for review. MineCode doesn't delete projects, caches or unrelated host settings. On Linux/macOS use the matching executables under `~/.local/share/minecode/runtime/bin/`.

## Maintainer package build

See [CONTRIBUTING.md](../CONTRIBUTING.md#check-your-work) for development checks and package builds. Explicit resource lists reject stale output. Tests and CI belong in the community repository; the wheel contains runtime code and user resources.
