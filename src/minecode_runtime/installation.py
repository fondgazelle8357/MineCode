"""Explicit, project-local host setup. Never edits global host configuration."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import sys
import tempfile

SKILLS = ("minecraft-java-developer", "minecraft-project-inspector", "minecraft-debugger",
          "minecraft-client-developer", "minecraft-server-developer", "minecraft-understand-anticheat")
HOSTS = {"codex": (".agents/skills", ".codex/config.toml"),
         "claude": (".claude/skills", ".mcp.json")}
CODEX_TOOL_TIMEOUT = 630  # 600s execution plus bounded process cleanup/response overhead.

# Exact installed paths shipped through 0.4.0rc2. Keep entries when retiring resources;
# never replace this allowlist with a directory-prefix or manifest-supplied rule.
HISTORICAL_SKILL_FILES = (
    'minecraft-client-developer/SKILL.md',
    'minecraft-debugger/SKILL.md',
    'minecraft-java-developer/SKILL.md',
    'minecraft-java-developer/references/automation.md',
    'minecraft-java-developer/references/content-mods.md',
    'minecraft-java-developer/references/integration.md',
    'minecraft-java-developer/references/migration.md',
    'minecraft-java-developer/references/movement-inventory.md',
    'minecraft-java-developer/references/networking.md',
    'minecraft-java-developer/references/new-project.md',
    'minecraft-java-developer/references/rendering.md',
    'minecraft-java-developer/references/workflow.md',
    'minecraft-project-inspector/SKILL.md',
    'minecraft-server-developer/SKILL.md',
    'minecraft-server-developer/references/operations.md',
    'minecraft-understand-anticheat/SKILL.md',
    'minecraft-understand-anticheat/references/grim.md',
)


def resources() -> Path:
    bundled = Path(__file__).parent / "data" / "bundle"
    if bundled.is_dir():
        return bundled
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "skills" / SKILLS[0] / "SKILL.md").is_file():
        return checkout
    raise ValueError("MineCode resources are missing; reinstall the complete wheel.")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def target(root: Path, relative: str) -> Path:
    path = root / relative
    # Refuse links/junctions, including links still resolving inside this project.
    for component in (path, *path.parents):
        if component == root:
            break
        if component.is_symlink() or component.resolve() != component.absolute():
            raise ValueError(f"Refusing linked installation path: {component}")
        if component != path and component.exists() and not component.is_dir():
            raise ValueError(f"Installation parent is not a directory: {component}")
    if not path.resolve().is_relative_to(root):
        raise ValueError("Installation path escapes the project")
    return path


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def configuration(host: str, root: Path, flags: list[str]) -> str:
    # The environment's Python is durable even if the host has a different PATH.
    command = str(Path(sys.executable).absolute())
    args = ["-m", "minecode_runtime", "--project", str(root), *flags]
    if host == "codex":
        # Wait for this project server before the first model turn; fail visibly if it cannot start.
        return ("[mcp_servers.minecode]\ncommand = " + json.dumps(command, ensure_ascii=False)
                + "\nargs = " + json.dumps(args, ensure_ascii=False)
                + f"\nstartup_timeout_sec = 30\ntool_timeout_sec = {CODEX_TOOL_TIMEOUT}\nrequired = true\n")
    return json.dumps({"mcpServers": {"minecode": {
        "type": "stdio", "command": command, "args": args}}}, indent=2) + "\n"


def payloads(host: str, root: Path, flags: list[str], skills_only: bool) -> dict[str, bytes]:
    skill_root, config_path = HOSTS[host]
    result = {}
    for name in SKILLS:
        directory = resources() / "skills" / name
        if not (directory / "SKILL.md").is_file():
            raise ValueError(f"Missing bundled skill: {name}; reinstall the complete wheel.")
        for source in directory.rglob("*.md"):
            relative = f"{skill_root}/{name}/{source.relative_to(directory).as_posix()}"
            result[relative] = source.read_bytes()
    if not skills_only:
        result[config_path] = configuration(host, root, flags).encode("utf-8")
    return result


def manifest_path(root: Path, host: str) -> Path:
    return target(root, f".minecode/installation-{host}.json")


def read_manifest(root: Path, host: str) -> dict[str, str]:
    path = manifest_path(root, host)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Invalid installation manifest; review it manually before setup/removal.") from exc
    allowed = set(payloads(host, root, [], False))
    allowed.update(f"{HOSTS[host][0]}/{name}" for name in HISTORICAL_SKILL_FILES)
    if (not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("host") != host
            or not isinstance(data.get("files"), dict)
            or any(name not in allowed or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for name, value in data["files"].items())):
        raise ValueError("Invalid installation manifest; review it manually before setup/removal.")
    return data["files"]


def write_manifest(root: Path, host: str, files: dict[str, str]) -> None:
    atomic_write(manifest_path(root, host), (json.dumps(
        {"schema_version": 1, "host": host, "files": files}, indent=2) + "\n").encode("utf-8"))


def setup_host(root: Path, host: str, flags: list[str], skills_only: bool = False) -> list[str]:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project must be an existing directory")
    planned = payloads(host, root, flags, skills_only)
    owned = read_manifest(root, host)
    current = payloads(host, root, [], False)
    retired = set(owned) - set(current)
    # Preflight historical destinations too, before any update or retirement.
    for name in owned:
        target(root, name)
    # Preflight every path before changing anything; preserve unrelated settings.
    for name, content in planned.items():
        path = target(root, name)
        if path.exists() and (not path.is_file() or
                digest(path.read_bytes()) not in {owned.get(name), digest(content)}):
            raise ValueError(f"Preserving existing/modified file: {path}. "
                             "Use --print-config and merge the MineCode entry yourself; "
                             "use --skills-only to install skills without host configuration.")
    for name, content in planned.items():
        path = target(root, name)
        atomic_write(path, content)
        owned[name] = digest(content)
        # Record each completed file so an interrupted setup can be retried/removed.
        write_manifest(root, host, owned)
    for name in sorted(retired):
        path = target(root, name)
        if path.exists() and (not path.is_file() or digest(path.read_bytes()) != owned[name]):
            continue  # Keep modified retired files owned so removal can report them.
        path.unlink(missing_ok=True)
        del owned[name]
        write_manifest(root, host, owned)
    return list(planned)


def remove_host(root: Path, host: str) -> tuple[list[str], list[str]]:
    root = root.resolve(strict=True)
    owned = read_manifest(root, host)
    removed, retained = [], []
    # Validate all destinations before deleting any file.
    for name in owned:
        target(root, name)
    for name, expected in list(owned.items()):
        path = target(root, name)
        if path.exists() and (not path.is_file() or digest(path.read_bytes()) != expected):
            retained.append(name)
            continue
        path.unlink(missing_ok=True)
        removed.append(name)
        del owned[name]
        write_manifest(root, host, owned)
    if not owned:
        manifest_path(root, host).unlink(missing_ok=True)
    return removed, retained
