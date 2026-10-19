"""Conservative local metadata inspection; never evaluate Gradle scripts."""
import json
import os
import re
import tomllib
from pathlib import Path
from .local_sources import discover_local_artifacts
from .models import Detection, ProjectProfile

MAX_FILE = 262144

# Recognize conventional declarations only. This is not a Gradle evaluator.
DEPENDENCY_PREFIX = (r"(?:^|[;{}\n])\s*(?:minecraft|mappings|modImplementation|modApi|modCompileOnly|"
                     r"modRuntimeOnly|implementation|api|compileOnly|runtimeOnly)\s*(?:\(\s*)?")
LITERALS = re.compile(r'"""[\s\S]*?"""|\x27\x27\x27[\s\S]*?\x27\x27\x27|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27')


def _syntax(text: str) -> str:
    """Mask strings while preserving offsets, so examples/log messages aren't code."""
    return LITERALS.sub(lambda m: re.sub(r"[^\n]", " ", m[0]), text)


def _coordinates(text: str) -> list[tuple[str, str]]:
    syntax = _syntax(text)
    found = []
    for match in LITERALS.finditer(text):
        literal = match[0]
        if literal.startswith(('"""', "'''")):
            continue
        if (re.search(DEPENDENCY_PREFIX + r"$", syntax[max(0, match.start() - 512):match.start()])
                and re.match(r"[ \t\r]*(?:\)|[;\n}]|$)", text[match.end():])
                and re.fullmatch(r"(?:com\.mojang:minecraft|net\.fabricmc:fabric-loader|"
                                 r"net\.fabricmc\.fabric-api:fabric-api|net\.fabricmc:yarn):[^'\"]+", literal[1:-1])):
            found.append((literal[0], literal[1:-1]))
    return found


def without_comments(text: str) -> str:
    """Strip Gradle comments in linear time, preserving literals and token boundaries."""
    output: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in "'\"":
            delimiter = char * 3 if text.startswith(char * 3, index) else char
            start = index
            index += len(delimiter)
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text.startswith(delimiter, index):
                    index += len(delimiter)
                    break
                else:
                    index += 1
            output.append(text[start:index])
        elif text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = len(text) if end < 0 else end
            output.append(" ")
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            output.append(" " + "\n" * text.count("\n", index, end))
            index = end
        else:
            output.append(char)
            index += 1
    return "".join(output)


def _catalog_accessor(alias: str) -> str:
    return ".".join(part for part in re.split(r"[-_.]+", alias) if part)


def _catalog_version(entry: dict, versions: dict) -> str | None:
    value = entry.get("version")
    if isinstance(value, str):
        return value
    reference = value.get("ref") if isinstance(value, dict) else entry.get("version.ref")
    resolved = versions.get(reference) if isinstance(reference, str) else None
    return resolved if isinstance(resolved, str) else None


def _catalog_evidence(catalog: dict, build_text: str) -> tuple[list[tuple[str, str]], bool, bool]:
    syntax = _syntax(build_text)
    versions = catalog.get("versions", {})
    libraries = catalog.get("libraries", {})
    plugins = catalog.get("plugins", {})
    if not all(isinstance(table, dict) for table in (versions, libraries, plugins)):
        return [], False, False
    evidence, minecraft, fabric = [], False, False
    modules = {"com.mojang:minecraft": "minecraft_version",
               "net.fabricmc:fabric-loader": "fabric_loader_version",
               "net.fabricmc.fabric-api:fabric-api": "fabric_api_version",
               "net.fabricmc:yarn": "mappings_version"}
    for alias, raw in libraries.items():
        accessor = _catalog_accessor(alias)
        if not re.search(DEPENDENCY_PREFIX + rf"(?:variantOf\s*\(\s*)?libs\.{re.escape(accessor)}(?![\w.])", syntax):
            continue
        module = version = None
        if isinstance(raw, str):
            parts = raw.split(":")
            if len(parts) == 3:
                module, version = ":".join(parts[:2]), parts[2]
        elif isinstance(raw, dict):
            module = raw.get("module")
            if not isinstance(module, str) and isinstance(raw.get("group"), str) and isinstance(raw.get("name"), str):
                module = f'{raw["group"]}:{raw["name"]}'
            version = _catalog_version(raw, versions)
        field = modules.get(module) if isinstance(module, str) else None
        if field:
            if isinstance(version, str):
                evidence.append((field, version))
            minecraft = minecraft or field == "minecraft_version"
            fabric = fabric or field != "minecraft_version"
            if field == "mappings_version":
                evidence.append(("mappings_type", "yarn"))
    for alias, raw in plugins.items():
        accessor = _catalog_accessor(alias)
        if not re.search(rf"\balias\s*\(\s*libs\.plugins\.{re.escape(accessor)}\s*\)", syntax):
            continue
        plugin = version = None
        if isinstance(raw, str):
            plugin, separator, version = raw.partition(":")
            if not separator:
                version = None
        elif isinstance(raw, dict):
            plugin = raw.get("id")
            version = _catalog_version(raw, versions)
        if plugin == "fabric-loom":
            fabric = True
            if isinstance(version, str):
                evidence.append(("loom_version", version))
    return evidence, minecraft, fabric


SKIP = {".git", ".gradle", ".venv", "build", "node_modules", "__pycache__"}
NAMES = {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
         "gradle.properties", "gradle-wrapper.properties", "fabric.mod.json", "pom.xml",
         "gradlew", "gradlew.bat", "plugin.yml", "paper-plugin.yml"}


def contained(root: Path, path: Path) -> bool:
    return path.resolve().is_relative_to(root)


def inventory(root: Path) -> tuple[list[Path], list[str]]:
    files, warnings = [], []
    visited = 0
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and contained(root, Path(base) / d))
        visited += 1
        if visited > 2000:
            warnings.append("Inspection stopped at 2,000 directories; profile may be incomplete.")
            break
        for name in sorted(names):
            path = Path(base) / name
            if name in NAMES or name.endswith(".java") or name.endswith(".mixins.json"):
                if contained(root, path):
                    files.append(path)
                else:
                    warnings.append(f"Skipped link outside project: {path.relative_to(root)}")
    return files, warnings


def read_local(root: Path, path: Path, warnings: list[str]) -> str:
    try:
        if not contained(root, path) or path.stat().st_size > MAX_FILE:
            warnings.append(f"Skipped outside/oversized metadata: {path.relative_to(root)}")
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.append(f"Cannot read {path.relative_to(root)}: {exc.strerror}")
        return ""


def inspect(root: Path) -> ProjectProfile:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Selected project must be a directory.")
    files, warnings = inventory(root)
    texts = {p: read_local(root, p, warnings) for p in files if p.name in NAMES}
    catalog_path = root / "gradle" / "libs.versions.toml"
    if catalog_path.is_file():
        texts[catalog_path] = read_local(root, catalog_path, warnings)
    builds = {p: t for p, t in texts.items() if p.name in {"build.gradle", "build.gradle.kts"}}
    builds = {p: without_comments(t) for p, t in builds.items()}
    descriptors = {}
    for path, value in texts.items():
        if path.name == "fabric.mod.json":
            try:
                data = json.loads(value)
                if isinstance(data, dict):
                    descriptors[path] = data
                else:
                    warnings.append(f"Invalid Fabric descriptor: {path.relative_to(root)}")
            except (ValueError, RecursionError):
                warnings.append(f"Invalid JSON: {path.relative_to(root)}")
    build_text = "\n".join(builds.values())
    catalog_values, catalog_minecraft, catalog_fabric = [], False, False
    catalog_text = texts.get(catalog_path, "")
    if catalog_text:
        try:
            catalog = tomllib.loads(catalog_text)
            if any(name in catalog and not isinstance(catalog[name], dict) for name in ("versions", "libraries", "plugins")):
                warnings.append("Unsupported version catalog structure: gradle/libs.versions.toml")
            else:
                catalog_values, catalog_minecraft, catalog_fabric = _catalog_evidence(catalog, build_text)
        except (tomllib.TOMLDecodeError, RecursionError):
            warnings.append("Invalid TOML: gradle/libs.versions.toml")
    fabric = bool(descriptors) or catalog_fabric or bool(re.search(r"fabric-loom|net\.fabricmc", build_text))
    # Descriptor location is evidence of a plugin project, not resolved platform/version
    # or proof of Folia support. Avoid parsing an unrelated root plugin.yml as Minecraft.
    plugin = any(p.name in {"plugin.yml", "paper-plugin.yml"}
                 and p.parent.relative_to(root).parts[-3:] == ("src", "main", "resources")
                 and text.strip() for p, text in texts.items())
    if plugin:
        warnings.append("Server plugin descriptor found; platform, API/server version and Folia support require source/build inspection. Descriptor api-version is not an installed Minecraft version.")
    if plugin and fabric:
        warnings.append("Both Fabric and server plugin markers found; select the affected module before applying platform guidance.")
    minecraft = fabric or plugin or catalog_minecraft or bool(re.search(r"com\.mojang:minecraft|net\.minecraft", build_text))
    java = any(p.suffix == ".java" for p in files) or bool(re.search(
        r"java-library|id\s*[\( ]\s*['\"]java['\"]|JavaLanguageVersion|sourceCompatibility", build_text))
    java = java or fabric or plugin
    gradle = bool(builds) or any(p.name in {"gradlew", "gradlew.bat", "settings.gradle", "settings.gradle.kts"} for p in files)
    client = any(d.get("environment") == "client" for d in descriptors.values())
    detection = Detection(project_root=str(root), minecraft_detected=minecraft, java_detected=java,
        gradle_detected=gradle, fabric_detected=fabric,
        project_type="minecraft" if fabric and plugin else "server-plugin" if plugin else
        "fabric-client" if fabric and client else "fabric-mod" if fabric else
        "minecraft" if minecraft else "java" if java else "unknown",
        descriptor_files=sorted(str(p.relative_to(root)) for p in texts), warnings=warnings.copy())
    profile = ProjectProfile(detection=detection, warnings=warnings, gradle_files=[
        str(p.relative_to(root)) for p in texts if p.name.endswith((".gradle", ".gradle.kts")) or p.name in {"gradle.properties", "libs.versions.toml"}],
        likely_build_task="build" if gradle else None,
        likely_run_client_task="runClient" if fabric else None)
    candidates: dict[str, list[tuple[str, str]]] = {}

    def record(field: str, value: object, source: Path):
        if isinstance(value, str) and value.strip() and not any(c in value for c in "$}{"):
            candidates.setdefault(field, []).append((value.strip(), str(source.relative_to(root))))

    # Root properties only: module properties may use the same keys with different meanings.
    props = {}
    prop_path = root / "gradle.properties"
    for line in texts.get(prop_path, "").splitlines():
        match = re.match(r"\s*([A-Za-z_][\w.-]*)\s*=\s*(.*?)\s*$", line)
        if match and not line.lstrip().startswith(("#", "!")):
            props[match[1]] = match[2]
    # A familiar property name alone says nothing about whether the build uses it.
    for field, value in catalog_values:
        record(field, value, catalog_path)
    for path, text in texts.items():
        if path.name.startswith("settings.gradle"):
            match = re.search(r"""rootProject\.name\s*=\s*['"]([^'"]+)['"]""", without_comments(text))
            if match:
                record("project_name", match[1], path)
        if path.name == "gradle-wrapper.properties":
            match = re.search(r"gradle-([\d.]+)-(?:bin|all)\.zip", text)
            if match:
                record("gradle_version", match[1], path)
    for path, text in builds.items():
        # Only literal dependency coordinates, with simple root property interpolation.
        for quote, coordinate in _coordinates(text):
            if quote == '"':
                coordinate = re.sub(r"\$(?:\{([A-Za-z_][\w.-]*)\}|([A-Za-z_]\w*))",
                    lambda match: props.get((match[1] or match[2]).removeprefix("project."), match[0]), coordinate)
            parts = coordinate.split(":")
            field = {"minecraft": "minecraft_version", "fabric-loader": "fabric_loader_version",
                     "fabric-api": "fabric_api_version", "yarn": "mappings_version"}[parts[1]]
            record(field, parts[2], path)
            if parts[1] == "yarn":
                record("mappings_type", "yarn", path)
        if re.search(r"(?:^|[;{}\n])\s*mappings\s*(?:\(\s*)?(?:loom\.)?officialMojangMappings\s*\(\s*\)", _syntax(text)):
            record("mappings_type", "mojang-official", path)
        match = re.search(r"""id\s*(?:\(\s*)?['"]fabric-loom['"]\s*\)?\s*version\s*['"]([^'"]+)['"]""", text)
        if match:
            record("loom_version", match[1], path)
        for pattern in (r"JavaLanguageVersion\.of\(\s*(\d+)\s*\)", r"options\.release(?:\.set\(|\s*=\s*)(\d+)",
                        r"sourceCompatibility\s*=\s*(?:JavaVersion\.VERSION_)?['\"]?(\d+(?:[._]\d+)?)"):
            for value in re.findall(pattern, text):
                record("java_version", value[2:] if value.startswith(("1.", "1_")) else value, path)
    for path, data in descriptors.items():
        record("mod_id", data.get("id"), path)
        # Descriptor constraints are not resolved installed versions.
        for value in data.get("mixins", []) if isinstance(data.get("mixins", []), list) else []:
            config = value if isinstance(value, str) else value.get("config") if isinstance(value, dict) else None
            if isinstance(config, str):
                profile.mixin_configs.append(config)
        entries = data.get("entrypoints", {})
        if isinstance(entries, dict):
            for key, values in entries.items():
                if isinstance(values, list):
                    for value in values:
                        name = value if isinstance(value, str) else value.get("value") if isinstance(value, dict) else None
                        if isinstance(name, str):
                            profile.entrypoints.setdefault(key, []).append(name)
    for field, values in candidates.items():
        unique = sorted(set(v for v, _ in values))
        profile.evidence[field] = sorted(set(source for _, source in values))
        if len(unique) == 1:
            setattr(profile, field, unique[0])
        else:
            profile.warnings.append(f"Conflicting {field}: {', '.join(unique)}; left unknown.")
    # Derive observed roots from the bounded inventory, without another unbounded walk.
    roots = set()
    for path in files:
        for parent in path.parents:
            if parent == root:
                break
            rel = parent.relative_to(root).as_posix()
            if re.search(r"(?:^|/)src/(?:main|client|test)/(?:java|resources)$", rel):
                roots.add(rel)
    profile.source_roots = sorted(roots)
    profile.client_source_roots = sorted(r for r in roots if "/client/" in "/" + r)
    profile.mixin_configs = sorted(set(profile.mixin_configs))
    profile.local_reference_artifacts = discover_local_artifacts(
        root, profile.minecraft_version, profile.mappings_type, profile.mappings_version,
        profile.fabric_api_version, limitations=profile.local_reference_limitations)
    if profile.local_reference_limitations:
        profile.warnings.append("Local artifact discovery is incomplete: " + ", ".join(profile.local_reference_limitations))
    profile.warnings.append("Static declared metadata only; computed/custom Gradle configuration and installed JVM versions remain unverified.")
    return profile
