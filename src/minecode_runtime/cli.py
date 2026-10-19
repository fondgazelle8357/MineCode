"""Installation commands alongside the backwards-compatible stdio entry point."""

import argparse
import json
from importlib.metadata import version
from pathlib import Path
import sys

from .installation import HOSTS, configuration, payloads, read_manifest, remove_host, resources, setup_host
from .installation_diagnostics import inspect_installation


def main() -> None:
    management = {"setup", "remove", "doctor", "resources", "-h", "--help", "--version"}
    if len(sys.argv) < 2 or sys.argv[1] not in management:
        from .server import main as serve

        serve()
        return
    parser = argparse.ArgumentParser(
        description="Install, inspect, or remove MineCode's project-local host integration.",
        epilog="MCP hosts start the runtime with --project and optional trust flags.",
    )
    parser.add_argument("--version", action="version", version=version("minecode-runtime"))
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("resources", help="Print the installed documentation/resource directory")
    for action in ("setup", "remove", "doctor"):
        help_text = (
            "Install or update one project-local host integration"
            if action == "setup"
            else "Remove unchanged MineCode-managed files" if action == "remove"\
            else "Inspect installed skills and host configuration without claiming MCP activation"
        )
        sub = commands.add_parser(action, help=help_text)
        sub.add_argument("--project", type=Path, required=True)
        sub.add_argument("--host", choices=HOSTS, required=True)
        if action == "setup":
            sub.add_argument("--skills-only", action="store_true")
            sub.add_argument("--print-config", action="store_true", help="Preview configuration without writing files")
            for flag in ("allow-execution", "allow-network", "allow-retrieval-network", "allow-provider-execution"):
                sub.add_argument("--" + flag, action="store_true", help="Explicitly opt in for this project")
            sub.add_argument("--providers-config", type=Path)
            sub.add_argument("--reference-cache", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "resources":
            print(resources())
        elif args.action == "remove":
            removed, retained = remove_host(args.project, args.host)
            print(json.dumps({"removed": removed, "retained_modified": retained}, indent=2))
        elif args.action == "doctor":
            print(json.dumps(inspect_installation(args.project, args.host), indent=2))
        else:
            root = args.project.resolve(strict=True)
            if not root.is_dir():
                raise ValueError("Project must be an existing directory")
            flags = [
                "--" + flag.replace("_", "-")
                for flag in ("allow_execution", "allow_network", "allow_retrieval_network", "allow_provider_execution")
                if getattr(args, flag)
            ]
            for option in ("providers_config", "reference_cache"):
                value = getattr(args, option)
                if value is not None:
                    flags.extend(["--" + option.replace("_", "-"), str(value.resolve())])
            if args.print_config:
                print(configuration(args.host, root, flags), end="")
            else:
                changed = setup_host(root, args.host, flags, args.skills_only)
                print(
                    json.dumps(
                        {
                            "host": args.host,
                            "project": str(root),
                            "installed": changed,
                            "retained_retired": sorted(set(read_manifest(root, args.host))
                                                       - set(payloads(args.host, root, [], False))),
                            "next": "Open this project in the host, review project trust/MCP approval, then start a fresh session.",
                        },
                        indent=2,
                    )
                )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
