"""Explicit source allowlist for the installed MineCode resource bundle."""

from pathlib import Path


RUNTIME_DATA_FILES = (
    Path("references/sources/sources.yaml"),
    Path("references/sources/developer-knowledge.json"),
)

BUNDLE_FILES = (
    Path("README.md"),
    Path("CONTRIBUTING.md"),
    Path("SECURITY.md"),
    Path("LICENSE"),
    Path("docs/ARCHITECTURE.md"),
    Path("docs/assets/architecture.svg"),
    Path("docs/assets/minecode-demo.gif"),
    Path("docs/assets/minecode-demo.png"),
    Path("docs/assets/README.md"),
    Path("THIRD_PARTY_NOTICES.md"),
    Path("docs/ADVANCED_SETUP.md"),
    Path("docs/CAPABILITIES.md"),
    Path("docs/EVIDENCE_POLICY.md"),
    Path("docs/INSTALLATION.md"),
    Path("docs/LICENSING.md"),
    Path("docs/PROVIDERS.md"),
    Path("docs/QUICKSTART.md"),
    Path("docs/RETRIEVAL.md"),
    Path("docs/WORKFLOW.md"),
    Path("integrations/providers.json"),
    Path("integrations/semantic-provider.example.json"),
    Path("mcp/README.md"),
    Path("references/gameplay/techniques.json"),
)

SKILL_DIRECTORIES = (
    Path("skills/minecraft-debugger"),
    Path("skills/minecraft-java-developer"),
    Path("skills/minecraft-project-inspector"),
    Path("skills/minecraft-client-developer"),
    Path("skills/minecraft-server-developer"),
    Path("skills/minecraft-understand-anticheat"),
)


def required_files(root: Path, paths: tuple[Path, ...]) -> list[Path]:
    files = [root / path for path in paths]
    missing = [path.relative_to(root).as_posix() for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing release resource: " + ", ".join(missing))
    return files


def runtime_data_sources(root: Path) -> list[Path]:
    """Return the two authoritative runtime registry sources."""
    return required_files(root, RUNTIME_DATA_FILES)


def bundle_sources(root: Path) -> list[Path]:
    """Return only reviewed user resources and the product skills."""
    sources = required_files(root, BUNDLE_FILES)
    for relative in SKILL_DIRECTORIES:
        directory = root / relative
        if not directory.is_dir():
            raise FileNotFoundError(f"Missing release resource directory: {relative.as_posix()}")
        sources.extend(path for path in directory.rglob("*.md") if path.is_file())
    return sorted(set(sources), key=lambda path: path.relative_to(root).as_posix())


def check_build_tree(root: Path, package: Path) -> None:
    """Refuse stale build output rather than accidentally bundling retired/private files."""
    allowed = {path.relative_to(root / "src/minecode_runtime")
               for path in (root / "src/minecode_runtime").rglob("*.py")}
    allowed.update(Path("data") / path.name for path in runtime_data_sources(root))
    allowed.update(Path("data/bundle") / path.relative_to(root) for path in bundle_sources(root))
    unexpected = sorted(path.relative_to(package).as_posix() for path in package.rglob("*")
                        if path.is_file() and path.relative_to(package) not in allowed)
    if unexpected:
        raise ValueError("Unexpected build output; use a clean build directory: " + ", ".join(unexpected[:10]))
