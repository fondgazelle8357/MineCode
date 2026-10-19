"""Read-only host setup checks. Never confuse installed files with an active MCP connection."""
from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path
import sys
import tomllib

from .installation import CODEX_TOOL_TIMEOUT, HOSTS, SKILLS, digest, manifest_path, payloads, read_manifest, target


def inspect_installation(project: Path, host: str) -> dict[str, object]:
    """Inspect local installation; host/model invocation requires separate, real evidence.

    This deliberately does not invoke Codex/Claude, install dependencies, contact the
    network, or execute project code. A valid config is not proof of MCP discovery.
    """
    if host not in HOSTS:
        raise ValueError("Unsupported MineCode host")
    root = project.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project must be an existing directory")

    skill_root, config_relative = HOSTS[host]
    expected = payloads(host, root, [], False)
    skill_prefixes = tuple(f"{skill_root}/{name}/" for name in SKILLS)
    skill_files = {name: content for name, content in expected.items()
                   if name.startswith(skill_prefixes)}
    matching_skills = []
    missing_skills = []
    outdated_skills = []

    for name, content in sorted(skill_files.items()):
        path = target(root, name)
        if not path.is_file():
            missing_skills.append(name)
        elif digest(path.read_bytes()) == digest(content):
            matching_skills.append(name)
        else:
            outdated_skills.append(name)

    manifest_file = manifest_path(root, host)
    manifest_exists = manifest_file.is_file()
    manifest_error = None
    recorded = {}
    if manifest_exists:
        try:
            recorded = read_manifest(root, host)
        except ValueError:
            manifest_error = "Invalid installation manifest; inspect it manually."

    config_file = target(root, config_relative)
    config_exists = config_file.is_file()
    config_valid = False
    config_error = None
    config_digest = None
    config_enabled = None
    configured_executable = None
    configured_project = None
    if config_exists:
        try:
            content = config_file.read_bytes()
            config_digest = digest(content)
            raw = content.decode("utf-8")
            decoded = tomllib.loads(raw) if host == "codex" else json.loads(raw)
            group = "mcp_servers" if host == "codex" else "mcpServers"
            server = decoded.get(group, {}).get("minecode", {})
            expected_args = ["-m", "minecode_runtime", "--project", str(root)]
            actual_args = server.get("args")
            configured_executable = server.get("command")
            configured_project = actual_args[3] if isinstance(actual_args, list) and len(actual_args) >= 4 else None
            config_enabled = server.get("enabled", True) if host == "codex" else None
            config_valid = (
                server.get("command") == str(Path(sys.executable).absolute())
                and isinstance(actual_args, list)
                and actual_args[:4] == expected_args
            )
            if host == "codex":
                config_valid = (config_valid and config_enabled is True and server.get("required") is True
                                and type(server.get("startup_timeout_sec")) in (int, float)
                                and server["startup_timeout_sec"] > 0
                                and type(server.get("tool_timeout_sec")) in (int, float)
                                and server["tool_timeout_sec"] >= CODEX_TOOL_TIMEOUT)
            if not config_valid:
                config_error = ("MineCode is not configured for this Python/project, or "
                                "required/enabled Codex startup or the 630s tool timeout is not set.")
        except (OSError, ValueError, UnicodeError, AttributeError, TypeError):
            config_error = "Host configuration is unreadable or invalid."

    skills_complete = bool(skill_files) and not missing_skills and not outdated_skills
    skills_owned = (
        manifest_exists and manifest_error is None
        and all(recorded.get(name) == digest(content) for name, content in skill_files.items())
    )
    # Ownership controls safe update/removal, not whether a manually merged config
    # can start this runtime. Never claim ownership of unrelated host settings.
    config_ownership = (
        "unknown" if manifest_error else
        "unmanaged" if config_relative not in recorded else
        "missing" if not config_exists else
        "managed_unchanged" if recorded[config_relative] == config_digest else "modified"
    )
    if skills_complete and config_valid and manifest_error is None:
        status = "configured_unverified"
    elif skills_complete and not config_exists and skills_owned and config_relative not in recorded:
        status = "skills_only"
    elif not manifest_exists and not config_exists and not matching_skills and not outdated_skills:
        status = "missing"
    else:
        status = "incomplete_or_mismatched"

    return {
        "host": host,
        "project": str(root),
        "status": status,
        "runtime_executable": str(Path(sys.executable).absolute()),
        "runtime_version": version("minecode-runtime"),
        "manifest_present": manifest_exists,
        "manifest_error": manifest_error,
        "skills": {
            "expected": len(skill_files),
            "matching": len(matching_skills),
            "missing": missing_skills,
            "outdated": outdated_skills,
        },
        "config_present": config_exists,
        "config_matches_runtime": config_valid,
        "config_error": config_error,
        "config_enabled": config_enabled,
        "configured_executable": configured_executable,
        "configured_project": configured_project,
        "ownership": {"skills_managed": skills_owned, "config": config_ownership},
        "host_trust": "unverified",
        "mcp_transport": "not_tested",
        "host_model_turn": "unverified",
        "next": (
            "Start a fresh session in the selected host and require an actual "
            "minecode.get_project_profile MCP tool result. A downloaded wheel, copied "
            "skills, config file, or static doctor result is not proof of host connectivity."
            if status == "configured_unverified" else
            "Review installation and host config; use 'minecode setup --host ... --project ...' "
            "after preserving any manually edited files."
        ),
    }
