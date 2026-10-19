"""Bounded discovery and read-only search of exact local Loom/Gradle artifacts."""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
from itertools import islice
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
from typing import Literal
import zipfile
from xml.etree import ElementTree

from .models import LocalReferenceArtifact
from .registry import tokens
from .retrieval_models import Evidence

MAX_ARCHIVE = 256_000_000
MAX_ENTRIES = 50_000
MAX_DIRECTORY = 16_000_000
MAX_ENTRY = 16_000_000
MAX_SCAN = 64_000_000
MAX_MATCHES = 2_000
SEARCHABLE = {".java", ".kt", ".json", ".mapping", ".properties", ".tiny", ".txt"}
MAX_CHILDREN = 512
MAX_FABRIC_MODULES = 64
MAX_POM = 256_000
MC_VERSION = r"\d+\.\d+(?:\.\d+)*(?:-(?:pre|rc)\d+)?"
ArtifactKind = Literal["minecraft-sources", "fabric-api-sources", "yarn-mappings"]
ArtifactScope = Literal["project", "gradle-user"]


def _limited(limitations: list[str] | None, reason: str) -> None:
    if limitations is not None and reason not in limitations:
        limitations.append(reason)


def _children(path: Path, limitations: list[str] | None = None) -> list[Path]:
    try:
        with os.scandir(path) as entries:
            selected = [Path(entry.path) for entry in islice(entries, MAX_CHILDREN + 1)]
            if len(selected) > MAX_CHILDREN:
                _limited(limitations, "directory_child_limit")
            return sorted(selected[:MAX_CHILDREN], key=lambda item: item.name.lower())
    except FileNotFoundError:
        return []  # A cache location that has never been created is normal.
    except OSError:
        _limited(limitations, "directory_unavailable")
        return []


def _safe_file(path: Path, boundary: Path) -> bool:
    try:
        if boundary != path and boundary not in path.parents:
            return False
        current = path
        while True:
            attrs = getattr(current.lstat(), "st_file_attributes", 0)
            if current.is_symlink() or attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                return False
            if current == boundary:
                break
            current = current.parent
        resolved_root = boundary.resolve(strict=True)
        resolved = path.resolve(strict=True)
        return (resolved_root in resolved.parents and path.is_file()
                and 0 < path.stat().st_size <= MAX_ARCHIVE)
    except OSError:
        return False


def _artifact(kind: ArtifactKind, path: Path, scope: ArtifactScope, *,
              artifact_version: str | None, minecraft_version: str | None,
              namespace: str | None, mappings_version: str | None,
              project_environment: dict[str, str | None], identity_evidence: dict[str, str],
              compatibility: dict[str, str]) -> LocalReferenceArtifact:
    identity = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
    return LocalReferenceArtifact(
        artifact_id=f"local-{kind}-{identity}", kind=kind, path=str(path.resolve()), scope=scope,
        minecraft_version=minecraft_version, mappings_type=namespace,
        mappings_version=mappings_version, namespace=namespace, artifact_version=artifact_version,
        project_environment=project_environment, identity_evidence=identity_evidence,
        compatibility=compatibility)


def _contains_version(text: str, version: str) -> bool:
    candidates = re.findall(rf"(?<![0-9a-z.])({MC_VERSION})(?![0-9a-z.])", text.lower())
    return version.lower() in candidates


def _compare(actual: str | None, expected: str | None) -> str:
    if not actual or not expected:
        return "unknown"
    return "exact" if actual == expected else "mismatch"


def _mapping_compatibility(namespace: str | None, artifact_version: str | None,
                           mappings_type: str | None, mappings_version: str | None) -> str:
    if not namespace or not mappings_type:
        return "unknown"
    if namespace != mappings_type:
        return "mismatch"
    if namespace == "yarn":
        return _compare(artifact_version, mappings_version)
    return "exact"


def _yarn_identity(version: str) -> tuple[str | None, str | None]:
    match = re.fullmatch(rf"(?P<minecraft>{MC_VERSION})\+build\.\d+", version, re.IGNORECASE)
    return (match.group("minecraft"), version) if match else (None, None)


def _fabric_api_minecraft(version: str) -> str | None:
    match = re.search(rf"\+(?P<minecraft>{MC_VERSION})$", version, re.IGNORECASE)
    return match.group("minecraft") if match else None


def _loom_minecraft_version(text: str, *, named: bool = False) -> str | None:
    if named:
        match = re.match(r"minecraft-[a-z]+-(.*)", text, re.IGNORECASE)
        text = match.group(1) if match else ""
    match = re.match(rf"(?P<version>{MC_VERSION})(?=$|[+-])", text, re.IGNORECASE)
    return match.group("version") if match else None


def _loom_yarn_coordinate(text: str) -> tuple[str, str | None] | None:
    match = re.search(
        rf"(?:^|-)net\.fabricmc\.yarn\.(?:(?P<encoded>\d+(?:_\d+){{1,2}})\.)?"
        rf"(?P<version>{MC_VERSION}\+build\.\d+)(?:-v\d+)?$", text, re.IGNORECASE)
    return (match.group("version"), match.group("encoded")) if match else None


def _project_environment(minecraft_version: str | None, mappings_type: str | None,
                         mappings_version: str | None,
                         fabric_api_version: str | None = None) -> dict[str, str | None]:
    return {"minecraft_version": minecraft_version, "mappings_type": mappings_type,
            "mappings_version": mappings_version, "fabric_api_version": fabric_api_version}


def _loom_sources(root: Path, boundary: Path, scope: ArtifactScope, minecraft_version: str,
                  mappings_type: str | None, mappings_version: str | None,
                  limitations: list[str] | None = None) -> list[LocalReferenceArtifact]:
    base = root / "net" / "minecraft"
    found = []
    for module in _children(base, limitations):
        if not module.is_dir() or not module.name.startswith("minecraft-"):
            continue
        for version in _children(module, limitations):
            if not version.is_dir():
                continue
            for jar in _children(version, limitations):
                if not jar.name.endswith("-sources.jar") or not _safe_file(jar, boundary):
                    continue
                components = {"module": module.name, "version": version.name,
                              "source JAR": jar.name[:-len("-sources.jar")]}
                minecraft_evidence = {}
                yarn_evidence = {}
                for label, component in components.items():
                    value = _loom_minecraft_version(component, named=label != "version")
                    if value:
                        minecraft_evidence[label] = value
                    coordinate = _loom_yarn_coordinate(component)
                    if coordinate:
                        yarn_evidence[label] = coordinate[0]
                        mapped_minecraft, _ = _yarn_identity(coordinate[0])
                        if mapped_minecraft:
                            minecraft_evidence[label + " Yarn coordinate"] = mapped_minecraft
                        if coordinate[1]:
                            minecraft_evidence[label + " Yarn key"] = coordinate[1].replace("_", ".")
                minecraft_claims = set(minecraft_evidence.values())
                if minecraft_version not in minecraft_claims:
                    continue
                yarn_claims = set(yarn_evidence.values())
                minecraft_conflict = len(minecraft_claims) > 1
                mappings_conflict = len(yarn_claims) > 1
                artifact_minecraft = None if minecraft_conflict else next(iter(minecraft_claims))
                artifact_mappings = next(iter(yarn_claims)) if len(yarn_claims) == 1 else None
                namespace = "yarn" if yarn_evidence else None
                mapping_match = _mapping_compatibility(
                    namespace, artifact_mappings, mappings_type, mappings_version)
                if mappings_conflict:
                    mapping_match = "unknown"
                identity_evidence = {
                    "minecraft_version": "consistent Loom module/version/source JAR identity",
                    **({"namespace": "recognized Yarn coordinate in Loom artifact"}
                       if yarn_evidence else {}),
                    **({"mappings_version": "consistent Yarn coordinate in Loom artifact"}
                       if artifact_mappings else {}),
                }
                conflicts = []
                if minecraft_conflict:
                    conflicts.append("Minecraft " + ", ".join(
                        f"{label}={value}" for label, value in sorted(minecraft_evidence.items())))
                if mappings_conflict:
                    conflicts.append("Yarn " + ", ".join(
                        f"{label}={value}" for label, value in sorted(yarn_evidence.items())))
                if conflicts:
                    identity_evidence["conflict"] = "; ".join(conflicts)
                found.append(_artifact(
                    "minecraft-sources", jar, scope, artifact_version=version.name,
                    minecraft_version=artifact_minecraft, namespace=namespace,
                    mappings_version=artifact_mappings,
                    project_environment=_project_environment(
                        minecraft_version, mappings_type, mappings_version),
                    identity_evidence=identity_evidence,
                    compatibility={"minecraft": "mismatch" if minecraft_conflict else _compare(
                        artifact_minecraft, minecraft_version), "mappings": mapping_match}))
    return found


def _module_artifacts(gradle_home: Path, group: str, module: str, version: str,
                      suffix: str, kind: ArtifactKind, minecraft_version: str | None,
                      mappings_type: str | None, mappings_version: str | None,
                      fabric_api_version: str | None = None,
                      limitations: list[str] | None = None) -> list[LocalReferenceArtifact]:
    base = gradle_home / "caches" / "modules-2" / "files-2.1" / group / module / version
    found = []
    for digest in _children(base, limitations):
        if not digest.is_dir():
            continue
        for jar in _children(digest, limitations):
            expected = jar.name.endswith("-v2.jar") if kind == "yarn-mappings" else jar.name.endswith(suffix)
            if expected and _safe_file(jar, gradle_home):
                artifact_version = base.name
                if kind == "fabric-api-sources":
                    artifact_minecraft = _fabric_api_minecraft(artifact_version)
                    namespace = None
                    artifact_mappings = None
                    compatibility = {
                        "minecraft": _compare(artifact_minecraft, minecraft_version),
                        "fabric_api": _compare(artifact_version, fabric_api_version),
                        "mappings": "unknown",
                    }
                    identity_evidence = {
                        "artifact_version": "Gradle module coordinate",
                        **({"minecraft_version": "Fabric API artifact version suffix"}
                           if artifact_minecraft else {}),
                    }
                else:
                    artifact_minecraft, artifact_mappings = _yarn_identity(artifact_version)
                    namespace = "yarn"
                    compatibility = {
                        "minecraft": _compare(artifact_minecraft, minecraft_version),
                        "mappings": _mapping_compatibility(
                            namespace, artifact_mappings, mappings_type, mappings_version),
                    }
                    identity_evidence = {
                        "artifact_version": "Gradle module coordinate",
                        "namespace": "Yarn module coordinate",
                        **({"minecraft_version": "Yarn artifact version",
                            "mappings_version": "Yarn artifact version"}
                           if artifact_minecraft else {}),
                    }
                found.append(_artifact(
                    kind, jar, "gradle-user", artifact_version=artifact_version,
                    minecraft_version=artifact_minecraft, namespace=namespace,
                    mappings_version=artifact_mappings,
                    project_environment=_project_environment(
                        minecraft_version, mappings_type, mappings_version, fabric_api_version),
                    identity_evidence=identity_evidence, compatibility=compatibility))
    return found


def _fabric_module_sources(gradle_home: Path, api_version: str, minecraft_version: str,
                           mappings_type: str | None, mappings_version: str | None,
                           limitations: list[str] | None = None) -> list[LocalReferenceArtifact]:
    """Follow only literal direct dependencies of the selected cached Fabric API POM."""
    coordinate = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.+-]{0,159}")
    if not coordinate.fullmatch(api_version):
        return []
    base = gradle_home / "caches/modules-2/files-2.1/net.fabricmc.fabric-api/fabric-api" / api_version
    declarations: dict[str, set[str]] = {}
    poms = []
    for digest in _children(base, limitations):
        pom = digest / f"fabric-api-{api_version}.pom"
        if _safe_file(pom, gradle_home) and pom.stat().st_size <= MAX_POM:
            poms.append(pom)
    if len(poms) > 8:
        _limited(limitations, "fabric_pom_limit")
        return []
    for pom in poms:
        try:
            with pom.open("rb") as stream:
                raw = stream.read(MAX_POM + 1)
            if len(raw) > MAX_POM or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                continue
            root = ElementTree.fromstring(raw.decode("utf-8"))
        except (OSError, UnicodeError, ElementTree.ParseError):
            continue
        ns = "{http://maven.apache.org/POM/4.0.0}" if root.tag.startswith("{") else ""

        def value(element: ElementTree.Element, name: str) -> str:
            return (element.findtext(ns + name) or "").strip()

        if (root.tag != ns + "project" or value(root, "groupId") != "net.fabricmc.fabric-api"
                or value(root, "artifactId") != "fabric-api" or value(root, "version") != api_version):
            continue
        for dependency in root.findall(f"{ns}dependencies/{ns}dependency"):
            module, version = value(dependency, "artifactId"), value(dependency, "version")
            if (value(dependency, "groupId") != "net.fabricmc.fabric-api"
                    or not module.startswith("fabric-") or module == "fabric-api"
                    or not coordinate.fullmatch(module) or not coordinate.fullmatch(version)
                    or value(dependency, "scope") not in {"", "compile", "runtime"}
                    or value(dependency, "type") not in {"", "jar"}
                    or value(dependency, "classifier") or value(dependency, "optional") == "true"):
                continue
            declarations.setdefault(module, set()).add(version)
            if len(declarations) > MAX_FABRIC_MODULES:
                _limited(limitations, "fabric_module_limit")
                return []
    found = []
    for module, versions in sorted(declarations.items()):
        if len(versions) != 1:
            continue
        version = next(iter(versions))
        for artifact in _module_artifacts(
                gradle_home, "net.fabricmc.fabric-api", module, version, "-sources.jar",
                "fabric-api-sources", minecraft_version, mappings_type, mappings_version, api_version, limitations):
            if Path(artifact.path).name != f"{module}-{version}-sources.jar":
                continue
            artifact.minecraft_version = _fabric_api_minecraft(api_version)
            artifact.compatibility = {"minecraft": _compare(artifact.minecraft_version, minecraft_version),
                                      "fabric_api": "exact", "mappings": "unknown"}
            artifact.identity_evidence = {
                "artifact_version": f"Gradle module coordinate net.fabricmc.fabric-api:{module}:{version}",
                "dependency": f"Direct dependency in cached net.fabricmc.fabric-api:fabric-api:{api_version} POM",
                "minecraft_version": "Parent Fabric API version suffix; dependency relationship only",
            }
            found.append(artifact)
    if len(found) > MAX_FABRIC_MODULES:
        _limited(limitations, "fabric_module_artifact_limit")
    return found[:MAX_FABRIC_MODULES]


def discover_local_artifacts(project: Path, minecraft_version: str | None,
                             mappings_type: str | None, mappings_version: str | None,
                             fabric_api_version: str | None, *,
                             limitations: list[str] | None = None) -> list[LocalReferenceArtifact]:
    """Inspect only version-qualified Loom and Gradle dependency-cache locations."""
    if not minecraft_version:
        return []
    gradle_home = Path(os.environ.get("GRADLE_USER_HOME", Path.home() / ".gradle")).expanduser()
    artifacts = _loom_sources(project / ".gradle" / "loom-cache" / "minecraftMaven", project, "project",
                              minecraft_version, mappings_type, mappings_version, limitations)
    artifacts += _loom_sources(gradle_home / "caches" / "fabric-loom" / "minecraftMaven", gradle_home,
                               "gradle-user", minecraft_version, mappings_type, mappings_version, limitations)
    if mappings_type == "yarn" and mappings_version:
        artifacts += _module_artifacts(gradle_home, "net.fabricmc", "yarn", mappings_version, ".jar",
                                       "yarn-mappings", minecraft_version, mappings_type, mappings_version,
                                       limitations=limitations)
    if fabric_api_version:
        artifacts += _module_artifacts(gradle_home, "net.fabricmc.fabric-api", "fabric-api",
                                       fabric_api_version, "-sources.jar", "fabric-api-sources",
                                       minecraft_version, mappings_type, mappings_version,
                                       fabric_api_version, limitations)
    order = {"project": 0, "gradle-user": 1}
    kind_order = {"minecraft-sources": 0, "fabric-api-sources": 1, "yarn-mappings": 2}
    selected = sorted(artifacts, key=lambda item: (order[item.scope], kind_order[item.kind], item.path))[:12]
    if len(artifacts) > 12:
        _limited(limitations, "artifact_candidate_limit")
    if fabric_api_version:
        selected += _fabric_module_sources(gradle_home, fabric_api_version, minecraft_version,
                                           mappings_type, mappings_version, limitations)
    return selected


def snapshot(artifact: LocalReferenceArtifact) -> dict:
    path = Path(artifact.path)
    raw_hash = _hash(path)
    file_stat = path.stat()
    return {"kind": "local-archive", "location": artifact.path, "revision": "sha256:" + raw_hash,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "size": file_stat.st_size,
            "mtime_ns": file_stat.st_mtime_ns, "artifact": artifact.model_dump()}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_entry(name: str) -> bool:
    path = PurePosixPath(name)
    return (not path.is_absolute() and "\\" not in name and "\x00" not in name
            and all(part not in {"", ".", ".."} for part in path.parts)
            and path.suffix.lower() in SEARCHABLE)


def _verify(snapshot_data: dict) -> Path:
    path = Path(snapshot_data["location"])
    file_stat = path.stat()
    if file_stat.st_size != snapshot_data["size"] or file_stat.st_mtime_ns != snapshot_data["mtime_ns"]:
        raise ValueError("Local reference artifact changed; search again")
    return path


def verify(snapshot_data: dict) -> None:
    path = _verify(snapshot_data)
    if "sha256:" + _hash(path) != snapshot_data["revision"]:
        raise ValueError("Local reference artifact changed; search again")


def _check_zip_directory(stream) -> None:
    """Bound ZIP metadata before ZipFile eagerly allocates its full index.

    Only directory framing is inspected here; zipfile owns decoding/decompression.
    Support classic and fixed-size ZIP64 footers, including prepended ZIPs.
    Split archives and ZIP64 extensible footer data are deliberately unsupported.
    """
    stream.seek(0, 2)
    size = stream.tell()
    if not 22 <= size <= MAX_ARCHIVE:
        raise ValueError("Local archive exceeds file-size limit or has no ZIP footer")
    stream.seek(max(0, size - 65557))  # Fixed footer + maximum 16-bit comment.
    tail = stream.read(65557)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or offset + 22 > len(tail):
        raise ValueError("Invalid local archive ZIP footer")
    _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset, comment = struct.unpack_from(
        "<4s4H2LH", tail, offset)
    if offset + 22 + comment != len(tail):
        raise ValueError("Invalid local archive ZIP comment/footer length")
    end = size - len(tail) + offset
    classic = (disk_entries, entries, directory_size, directory_offset)
    stream.seek(max(0, end - 20))
    locator = stream.read(20)
    zip64 = len(locator) == 20 and locator[:4] == b"PK\x06\x07"
    zip64_offset = None
    if zip64:
        _, locator_disk, zip64_offset, disks = struct.unpack("<4sLQL", locator)
        if locator_disk or disks != 1 or end < 76:
            raise ValueError("Invalid or split local ZIP64 archive")
        end -= 76  # Fixed ZIP64 footer (56) and locator (20).
        stream.seek(end)
        footer = stream.read(56)
        if len(footer) != 56 or footer[:4] != b"PK\x06\x06":
            raise ValueError("Invalid local ZIP64 footer")
        _, record_size, _, _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset = struct.unpack(
            "<4sQ2H2L4Q", footer)
        if record_size != 44:
            raise ValueError("Unsupported local ZIP64 extensible footer")
        for declared, actual, sentinel in zip(classic, (disk_entries, entries, directory_size, directory_offset),
                                               (0xffff, 0xffff, 0xffffffff, 0xffffffff)):
            if declared != sentinel and declared != actual:
                raise ValueError("Inconsistent local ZIP64 directory metadata")
    elif any(value == sentinel for value, sentinel in zip(classic, (0xffff, 0xffff, 0xffffffff, 0xffffffff))):
        raise ValueError("Missing local ZIP64 footer")
    if disk or directory_disk or disk_entries != entries:
        raise ValueError("Invalid or split local ZIP directory")
    if entries > MAX_ENTRIES:
        raise ValueError("archive_entry_limit: local archive rejected before indexing")
    if directory_size > MAX_DIRECTORY:
        raise ValueError("archive_directory_byte_limit: local archive rejected before indexing")
    start = end - directory_size
    prefix = start - directory_offset
    if start < 0 or prefix < 0 or zip64_offset is not None and zip64_offset + prefix != end:
        raise ValueError("Invalid local archive central-directory offset")
    stream.seek(start)
    count = 0
    while stream.tell() < end:
        header = stream.read(min(46, end - stream.tell()))
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ValueError("Malformed local archive central-directory record")
        length = sum(struct.unpack_from("<3H", header, 28))  # Name, extra, comment.
        if stream.tell() + length > end:
            raise ValueError("Truncated local archive central-directory record")
        count += 1
        if count > MAX_ENTRIES or count > entries:
            raise ValueError("archive_entry_limit: inconsistent local archive entry count")
        stream.seek(length, 1)
    if count != entries:
        raise ValueError("Inconsistent local archive entry count")


@contextmanager
def _open_archive(path: Path):
    with path.open("rb") as stream:
        _check_zip_directory(stream)
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            yield archive


def read(snapshot_data: dict, entry: str) -> str:
    path = _verify(snapshot_data)
    if not _safe_entry(entry):
        raise ValueError("Unsafe or excluded archive entry")
    with _open_archive(path) as archive:
        info = archive.getinfo(entry)
        if info.file_size > MAX_ENTRY:
            raise ValueError("Local reference entry exceeds limit")
        raw = archive.read(info)
    if b"\0" in raw:
        raise ValueError("Binary local reference entry")
    return raw.decode("utf-8", errors="replace")


def matches(snapshot_data: dict, terms: set[str], *, identifiers: set[str] | None = None,
            limitations: list[str] | None = None) -> list[tuple[int, str, int, int]]:
    path = _verify(snapshot_data)
    results = []
    scanned = 0
    # Java identifiers are case-sensitive: the field inGameHud is not InGameHud.
    literal = re.compile(r"(?<![\w$])(?:" + "|".join(re.escape(term) for term in sorted(identifiers))
                         + r")(?![\w$])") if identifiers else None
    classes = {}
    hits = {}
    declarations = {}
    with _open_archive(path) as archive:
        infos = archive.infolist()
        for info in infos:
            if not _safe_entry(info.filename):
                continue
            if info.file_size > MAX_ENTRY:
                _limited(limitations, "archive_entry_size_limit")
                continue
            scanned += info.file_size
            if scanned > MAX_SCAN:
                _limited(limitations, "archive_scan_byte_limit")
                break
            raw = archive.read(info)
            if b"\0" in raw:
                continue
            path_terms = tokens(PurePosixPath(info.filename).stem)
            path_score = 3 * len(terms & path_terms) + sum(term in info.filename.lower() for term in terms)
            path_identifiers = set(literal.findall(info.filename)) if literal else set()
            text = raw.decode("utf-8", errors="replace")
            # Only explicit same-archive Java extends links. No guessed imports,
            # cross-artifact hierarchy, override resolution or inferred behavior.
            if info.filename.endswith('.java'):
                package = re.search(r'^\s*package\s+([\w.]+)\s*;', text, re.M)
                prefix = package[1] + '.' if package else ''
                stem = PurePosixPath(info.filename).stem
                declaration = re.search(r'\b(?:class|interface)\s+' + re.escape(stem)
                                        + r'\b(?:\s*<[^{};]*>)?\s+extends\s+([\w.$]+)', text)
                parent = declaration[1] if declaration else None
                if parent and '.' not in parent:
                    imported = re.search(r'\bimport\s+([\w.]+\.' + re.escape(parent) + r')\s*;', text)
                    parent = imported[1] if imported else prefix + parent
                classes[prefix + stem] = (info.filename, parent, stem)
            best = None
            best_key = None
            owner_identifiers = set()
            for line_number, line in enumerate(text.splitlines(), 1):
                if info.filename.endswith('.tiny') and line.startswith('c\t'):
                    owner_identifiers = {name.rsplit('/', 1)[-1] for name in line.split('\t')[1:]}
                    owner_identifiers &= identifiers or set()
                score = sum(term in line.lower() for term in terms)
                line_identifiers = set(literal.findall(line)) if literal else set()
                scope = path_identifiers | owner_identifiers
                coverage = len(scope | line_identifiers) + int(bool(scope) and bool(line_identifiers - scope))
                # Prefer a declaration over an import, documentation or invocation
                # of the same member. This is a lexical anchor, not a Java parser.
                definition = bool(line_identifiers and (line.startswith(('\tm\t', '\tf\t')) or re.match(
                    r'\s*(?:(?:public|protected|private|static|final|abstract|synchronized|native|default)\s+)*'
                    r'(?:<[^;{}()]+>\s+)?'
                    r'[\w$<>?,.\[\]]+\s+(?:' + '|'.join(map(re.escape, sorted(line_identifiers))) + r')\s*\(', line)))
                # Exact requested class/member identifiers beat their split words.
                # Within a class, anchor at the member rather than its declaration.
                key = (coverage, definition, len(line_identifiers), score + path_score)
                if score and (best_key is None or key > best_key):
                    best_key = key
                    best = (score + path_score + int(definition), info.filename, line_number, coverage)
                    hits[info.filename] = path_identifiers | owner_identifiers | line_identifiers
                    declarations[info.filename] = line_identifiers if definition else set()
            # The public search exposes one initial hit per file. Repeated lines
            # in an early file must not consume the entire result budget.
            if best is not None:
                if len(results) >= MAX_MATCHES:
                    _limited(limitations, "archive_match_file_limit")
                    break
                results.append(best)
    # A method can be declared in an explicit cached superclass rather than in
    # the queried class. Boost only real member hits along those observed links.
    inherited = {}
    for name, (_, parent, stem) in classes.items():
        if stem not in (identifiers or set()):
            continue
        visited = {name}
        while parent in classes and parent not in visited:
            visited.add(parent)
            filename, parent, _ = classes[parent]
            if declarations.get(filename, set()) - {stem}:
                inherited.setdefault(filename, set()).add(stem)
    return [(score, filename, line, coverage + len(inherited.get(filename, set()) - hits.get(filename, set()))
             + int(bool(inherited.get(filename))))
            for score, filename, line, coverage in results]


def evidence(artifact: LocalReferenceArtifact) -> Evidence:
    exact = bool(artifact.compatibility) and all(
        value == "exact" for value in artifact.compatibility.values())
    return Evidence(
        source_id=artifact.artifact_id,
        title=f"Local {artifact.kind.replace('-', ' ')} ({artifact.minecraft_version})",
        url=Path(artifact.path).as_uri(), source_type="local-gradle-artifact", trust="local-evidence",
        priority="project-evidence", historical=False,
        language=None if artifact.kind == "yarn-mappings" else "Java",
        environment={"minecraft": artifact.minecraft_version, "mappings": artifact.namespace},
        license={"reported": "unknown", "evidence_url": None},
        code_reuse={"allowed": False, "generated_derivation_allowed": False, "redistribution_allowed": False},
        reuse_status="reference-only", compatibility=artifact.compatibility,
        provenance={
            "scope": artifact.scope, "artifact_path": artifact.path, "artifact_kind": artifact.kind,
            "project_environment": artifact.project_environment,
            "artifact_identity": {
                "artifact_version": artifact.artifact_version,
                "minecraft_version": artifact.minecraft_version,
                "namespace": artifact.namespace,
                "mappings_version": artifact.mappings_version,
            },
            "identity_evidence": artifact.identity_evidence,
            "namespace": artifact.namespace,
            "selection": "exact-local" if exact else "supporting-local",
        },
        score=(10_000 if exact else 8_000) + (100 if artifact.scope == "project" else 0),
        reasons=["Version-qualified local Gradle/Loom artifact", "Namespace preserved; no name translation applied"])
