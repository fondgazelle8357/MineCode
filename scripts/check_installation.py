"""Run with the wheel's isolated Python (-I), outside the source checkout."""

import asyncio
import json
import os
from importlib.metadata import version
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from urllib.parse import unquote, urlsplit

from mcp import Client
from mcp.client.stdio import StdioServerParameters
from jsonschema import Draft202012Validator
import yaml
import minecode_runtime
from minecode_runtime.installation import SKILLS, remove_host, resources, setup_host
from minecode_runtime.registry import load_registry


async def main() -> None:
    module = Path(minecode_runtime.__file__).resolve()
    assert module.is_relative_to(Path(sys.prefix).resolve()), module
    bundle = resources()
    assert bundle.is_relative_to(module.parent), bundle
    registry = load_registry()
    assert {
        "yarn-screen-1211",
        "fabric-world-rendering-1211",
        "owo-lib",
        "cloth-config",
        "mixinextras",
        "liquidbounce",
        "yarn-screen-12111",
        "yarn-interaction-12111",
    } <= registry.keys()
    for name in (
        "README.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "LICENSE",
        "docs/ARCHITECTURE.md",
        "docs/assets/architecture.svg",
        "docs/INSTALLATION.md",
        "docs/QUICKSTART.md",
        "docs/ADVANCED_SETUP.md",
        "docs/CAPABILITIES.md",
        "docs/EVIDENCE_POLICY.md",
        "docs/WORKFLOW.md",
        "docs/RETRIEVAL.md",
        "integrations/providers.json",
        "mcp/README.md",
        "references/gameplay/techniques.json",
        "THIRD_PARTY_NOTICES.md",
    ):
        assert (bundle / name).is_file(), name
    assert set(SKILLS) == {
        "minecraft-java-developer",
        "minecraft-project-inspector",
        "minecraft-debugger",
        "minecraft-client-developer",
        "minecraft-server-developer",
        "minecraft-understand-anticheat",
    }
    for name in SKILLS:
        assert (bundle / "skills" / name / "SKILL.md").is_file(), name
    assert (bundle / "skills/minecraft-java-developer/references/workflow.md").is_file()

    for name in (
        "automation",
        "rendering",
        "networking",
        "movement-inventory",
        "migration",
        "integration",
        "new-project",
    ):
        assert (bundle / f"skills/minecraft-java-developer/references/{name}.md").is_file(), name
    version_result = subprocess.run(
        [sys.executable, "-m", "minecode_runtime", "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert version_result.stdout.strip() == version("minecode-runtime")

    packaged = [path.relative_to(bundle).as_posix() for path in bundle.rglob("*") if path.is_file()]
    forbidden = (
        "project-notes/",
        "evals/",
        "test-projects/",
        "context/",
        "core/",
        "examples/",
        "hooks/",
        "java-analysis/",
        "minecraft-analysis/",
        "references/sources/",
    )
    assert not [name for name in packaged if name.startswith(forbidden) or Path(name).name.startswith("PHASE_")]

    privacy_patterns = {
        "windows_user_profile": re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.IGNORECASE),
        "unix_user_profile": re.compile(r"/(?:home|Users)/[^/\s]+/"),
        "local_ai_workspace": re.compile(r"\.codex[\\/]\.chatgpt-projects|\.chatgpt-projects", re.IGNORECASE),
        "internal_project_id": re.compile(r"\bg-p-[a-f0-9]{8,}\b", re.IGNORECASE),
        "private_repository": re.compile(r"github\.com/[^/\s]+/[^/\s]*(?:private|internal)[^/\s]*", re.IGNORECASE),
        "internal_development_phase": re.compile(r"\bphase(?:\s+|_)\d+(?=\b|_)", re.IGNORECASE),
    }
    privacy_hits = {category: [] for category in privacy_patterns}
    for path in module.parent.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".json", ".yaml", ".svg", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8")
        for category, pattern in privacy_patterns.items():
            if pattern.search(text):
                privacy_hits[category].append(path.relative_to(module.parent).as_posix())
    assert not {category: files for category, files in privacy_hits.items() if files}

    help_result = subprocess.run(
        [sys.executable, "-m", "minecode_runtime", "--help"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert all(command in help_result.stdout for command in ("setup", "remove", "doctor", "resources"))
    resources_result = subprocess.run(
        [sys.executable, "-m", "minecode_runtime", "resources"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert resources_result.returncode == 0, resources_result.stderr
    assert Path(resources_result.stdout.strip()).resolve() == bundle.resolve()
    checked = 0
    for document in bundle.rglob("*.md"):
        for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            target = raw.strip().strip("<>").split(" ", 1)[0]
            parsed = urlsplit(target)
            if not target or target.startswith("#") or parsed.scheme or parsed.netloc:
                continue
            assert (document.parent / unquote(parsed.path)).exists(), (document, target)
            checked += 1
    with tempfile.TemporaryDirectory(prefix="minecode installed ") as directory:
        root = Path(directory).resolve()

        def doctor(host, expected_status):
            # Exercise the installed console script, not just the Python helper.
            executable = Path(sys.executable).with_name("minecode.exe" if sys.platform == "win32" else "minecode")
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = subprocess.run(
                [str(executable), "doctor", "--host", host, "--project", str(root)],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            report = json.loads(result.stdout)
            assert report["status"] == expected_status, report
            assert report["runtime_version"] == version("minecode-runtime"), report
            assert report["runtime_executable"] == str(Path(sys.executable).absolute()), report
            assert report["mcp_transport"] == "not_tested" and report["host_model_turn"] == "unverified"
            assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}

        doctor("codex", "missing")
        setup_host(root, "codex", [], skills_only=True)
        doctor("codex", "skills_only")
        (root / "build.gradle").write_text(
            "plugins { id 'fabric-loom' version '1.10.5' }\n"
            'minecraft "com.mojang:minecraft:$minecraft_version"\n'
            'mappings "net.fabricmc:yarn:$yarn_mappings:v2"\n'
        )
        (root / "gradle.properties").write_text(
            "minecraft_version=1.21\nloader_version=0.16.10\nyarn_mappings=1.21+build.1\n"
        )
        identity = "1.21-net.fabricmc.yarn.1_21.1.21+build.1-v2"
        archive_path = (
            root
            / ".gradle/loom-cache/minecraftMaven/net/minecraft/minecraft-merged-fixture"
            / identity
            / "minecraft-merged-sources.jar"
        )
        archive_path.parent.mkdir(parents=True)
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("example/Noise.java", "installedEvidenceProbe\n" * 2001)
            archive.writestr("example/Fixture.java", "class Fixture { void installedEvidenceProbe() {} }")
        for host, skill_directory in (("codex", ".agents/skills"), ("claude", ".claude/skills")):
            setup_host(root, host, [])
            doctor(host, "configured_unverified")
            for name in SKILLS:
                for source in (bundle / "skills" / name).rglob("*.md"):
                    relative = source.relative_to(bundle / "skills")
                    installed = root / skill_directory / relative
                    assert installed.read_bytes() == source.read_bytes()
                    if installed.name == "SKILL.md":
                        frontmatter = yaml.safe_load(installed.read_text(encoding="utf-8").split("---", 2)[1])
                        assert frontmatter["name"] == name and frontmatter["description"].strip()
                    for raw in re.findall(r"\[[^\]]*\]\(([^)]+)\)", installed.read_text(encoding="utf-8")):
                        parsed = urlsplit(raw)
                        if parsed.scheme or parsed.netloc or not parsed.path:
                            continue
                        target = (installed.parent / unquote(parsed.path)).resolve()
                        assert target.is_relative_to(root / skill_directory) and target.is_file(), (relative, raw)
        skill_count = sum(1 for source in (bundle / "skills").rglob("*.md"))
        config = tomllib.loads((root / ".codex/config.toml").read_text())
        server = config["mcp_servers"]["minecode"]
        async with Client(StdioServerParameters(command=server["command"], args=server["args"])) as client:
            tools = (await client.list_tools()).tools
            assert len(tools) == 14
            assert len({tool.name for tool in tools}) == 14
            assert all(isinstance(tool.input_schema, dict) for tool in tools)
            assert all(isinstance(tool.output_schema, dict) for tool in tools)
            schemas = {tool.name: tool for tool in tools}
            for tool in tools:
                Draft202012Validator.check_schema(tool.input_schema)
                Draft202012Validator.check_schema(tool.output_schema)

            async def call(name, arguments=None):
                tool = schemas["minecode." + name]
                Draft202012Validator(tool.input_schema).validate(arguments or {})
                result = await client.call_tool(tool.name, arguments or {})
                assert not result.is_error, result
                Draft202012Validator(tool.output_schema).validate(result.structured_content)
                return result.structured_content

            called = set()
            original_call = call

            async def call(name, arguments=None):
                called.add(name)
                return await original_call(name, arguments)

            assert (await call("detect_project"))["fabric_detected"]
            assert (await call("run_gradle", {"task": "build"}))["state"] == "blocked"
            assert not (await call("run_client"))["gameplay_verified"]
            diagnosis = await call(
                "analyze_build_failure", {"output": "Example.java:7: error: cannot find symbol token=INSTALL_CANARY"}
            )
            assert "INSTALL_CANARY" not in json.dumps(diagnosis)
            assert diagnosis["affected_line"] == 7
            assert await call("analyze_runtime_failure", {"output": "java.lang.IllegalStateException: fixture"})
            assert not (await call("call_provider", {"capability": "mapping_lookup", "arguments": {}}))["success"]
            assert not (await call("search_reference_code", {"query": "zzquasarunmatchedzz"}))["results"]
            packet = await call("search_reference_code", {"query": "installedEvidenceProbe"})
            assert {item["path"] for item in packet["results"]} == {"example/Noise.java", "example/Fixture.java"}
            assert not packet["truncated"] and not packet["truncation_reasons"]
            evidence = packet["results"][0]
            assert evidence["compatibility"] == {"minecraft": "exact", "mappings": "exact"}
            expanded = await call("get_reference_context", {"result_id": evidence["result_id"]})
            assert "installedEvidenceProbe" in expanded["results"][0]["excerpt"]
            # A forged ID must fail over real installed stdio, not expose a file.
            invalid = await client.call_tool("minecode.get_reference_context", {"result_id": "0" * 32})
            assert invalid.is_error
            called.add("get_reference_context")
            profile = await call("get_project_profile")
            assert profile["minecraft_version"] == "1.21", profile
            assert (await call("build_project"))["execution"]["state"] == "blocked"
            for provider in ("minecraft-dev-mcp", "mcp-fabric"):
                assert (await call("provider_status", {"provider": provider}))["status"] == "unavailable"
            assert (await call("search_sources", {"query": "Fabric rendering"}))["results"]
            assert (await call("search_developer_knowledge", {"query": "callback", "fetch_content": False}))["results"]
            mapping = await call(
                "search_developer_knowledge",
                {
                    "query": "Screen render",
                    "minecraft_version": "1.21.11",
                    "mappings": "yarn",
                    "mappings_version": "1.21.11+build.3",
                    "fetch_content": False,
                },
            )
            assert mapping["results"][0]["compatibility"]["mappings"] == "exact-declared"
            assert mapping["results"][0]["compatibility"]["mappings_version"] == "exact-declared"
            gameplay = await call("search_gameplay_techniques", {"query": "IPC"})
            assert gameplay["results"][0]["id"] == "instant-pearl-catch"
            assert {"minecode." + name for name in called} == {tool.name for tool in tools}
        claude = json.loads((root / ".mcp.json").read_text())["mcpServers"]["minecode"]
        async with Client(StdioServerParameters(command=claude["command"], args=claude["args"])) as client:
            result = await client.call_tool("minecode.get_project_profile", {})
            assert not result.is_error and result.structured_content["minecraft_version"] == "1.21"
        setup_host(root, "codex", ["--allow-execution"])
        doctor("codex", "configured_unverified")
        assert (
            "--allow-execution"
            in tomllib.loads((root / ".codex/config.toml").read_text())["mcp_servers"]["minecode"]["args"]
        )
        edited = root / ".agents/skills/minecraft-debugger/SKILL.md"
        edited.write_text(edited.read_text(encoding="utf-8") + "\nBeta tester note.\n", encoding="utf-8")
        try:
            setup_host(root, "codex", [])
        except ValueError as exc:
            assert "Preserving existing/modified file" in str(exc)
        else:
            raise AssertionError("Setup overwrote a modified user file")
        removed, retained = remove_host(root, "codex")
        assert len(removed) == skill_count and retained == [".agents/skills/minecraft-debugger/SKILL.md"]
        assert edited.read_text(encoding="utf-8").endswith("Beta tester note.\n")
        removed, retained = remove_host(root, "claude")
        assert len(removed) == skill_count + 1 and not retained
    print(
        json.dumps(
            {
                "installed_module": "isolated site-packages/minecode_runtime",
                "registry_entries": len(registry),
                "tools": 14,
                "tool_schemas": "passed",
                "connection_scope": "installed stdio; host discovery and agent effectiveness remain unverified",
                "skills_installed_and_local_references_checked": len(SKILLS),
                "cli_help_and_resources": "passed",
                "installed_doctor_read_only_missing_skills_full_update": "passed",
                "developer_and_gameplay_references": "passed",
                "privacy_categories": {category: len(files) for category, files in privacy_hits.items()},
                "packaged_links_checked": checked,
                "setup_update_remove_and_modified_file_protection": "passed",
            }
        )
    )
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(
                "\nInstalled wheel: CONNECTED over stdio; all 14 tool request/response contracts passed. "
                "All six skills and local references installed for Codex and Claude. "
                "Host/model discovery and skill effectiveness remain UNVERIFIED.\n"
            )


if __name__ == "__main__":
    asyncio.run(main())
