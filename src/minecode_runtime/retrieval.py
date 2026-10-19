"""Four small retrieval operations; no model, vector store or reference execution."""
from collections import OrderedDict
from pathlib import Path
import re
import threading
from typing import TypedDict, Unpack
import uuid
from .inspection import inspect
from .local_sources import evidence as local_evidence
from .local_sources import matches as local_matches
from .local_sources import read as local_read
from .local_sources import snapshot as local_snapshot
from .local_sources import verify as verify_local_snapshot
from .reference_cache import ReferenceCache
from .registry import content_terms, evidence, historical_query, load_registry, rank, TRUST_ORDER, VERSION_ORDER
from .retrieval_models import Evidence, EvidencePacket

SEARCH_CHARS = 600
CONTEXT_CHARS = 8000


def preferred_local(item: Evidence) -> bool:
    # A pinned Fabric dependency is applicable even when its source namespace is
    # unknown. This does not promote unqualified or conflicting game artifacts.
    return item.provenance.get("selection") == "exact-local" or (
        item.provenance.get("artifact_kind") == "fabric-api-sources"
        and item.compatibility == {"minecraft": "exact", "fabric_api": "exact", "mappings": "unknown"})


class SourceSelectionError(ValueError):
    """Expected caller selection error whose safe guidance can cross the MCP boundary."""


class RankFilters(TypedDict, total=False):
    minecraft_version: str | None
    loader: str | None
    language: str | None
    mappings: str | None
    mappings_version: str | None
    side: str | None
    categories: list[str] | None
    strict_version: bool
    include_experimental: bool


class Retrieval:
    def __init__(self, project: Path, *, cache_root: Path | None = None,
                 allow_network: bool = False, sources: dict | None = None):
        self.project = project.resolve()
        self.sources = load_registry() if sources is None else sources
        self.cache = ReferenceCache(project, cache_root, allow_network)
        self.selected: OrderedDict[str, tuple[dict, Evidence]] = OrderedDict()
        self.lock = threading.RLock()

    def search_sources(self, query: str, max_results: int = 5,
                       **filters: Unpack[RankFilters]) -> EvidencePacket:
        self.validate(query, max_results)
        results = rank(self.sources, query, **filters)
        return EvidencePacket(results=results[:max_results], truncated=len(results) > max_results)

    @staticmethod
    def validate(query: str, limit: int):
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
            raise ValueError("Query must contain 1–300 characters")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("max_results must be 1–10")

    def excerpt(self, item: Evidence, snapshot: dict, path: str, line: int,
                radius: int = 0, max_chars: int = SEARCH_CHARS) -> Evidence:
        text = local_read(snapshot, path) if snapshot["kind"] == "local-archive" else self.cache.read(snapshot, path)
        lines = text.splitlines()
        start, end = max(1, line - radius), min(len(lines), line + radius)
        selected = lines[start - 1:end]
        full = "\n".join(selected)
        excerpt = full[:max_chars]
        item = item.model_copy(deep=True)
        item.path, item.start_line = path, start
        item.end_line = start + excerpt.count("\n") if excerpt else start
        item.excerpt = excerpt
        item.content_truncated = len(full) > max_chars or start > 1 or end < len(lines)
        item.revision, item.retrieved_at = snapshot["revision"], snapshot["retrieved_at"]
        if snapshot["kind"] == "local-archive":
            item.provenance.update(archive_revision=snapshot["revision"])
            if path.endswith('.tiny') and text.startswith('tiny\t2\t'):
                owner = next((row for row in reversed(lines[:line]) if row.startswith('c\t')), None)
                if owner:
                    item.provenance['mapping_owner'] = dict(zip(lines[0].split('\t')[3:], owner.split('\t')[1:]))
        else:
            item.provenance.update(ref=snapshot.get("ref"), fetched_url=snapshot["url"],
                                   last_modified=snapshot.get("last_modified"), etag=snapshot.get("etag"))
        item.match_kind = "content"
        return item

    def remember(self, snapshot: dict, item: Evidence) -> Evidence:
        key = uuid.uuid4().hex
        item.result_id = key
        self.selected[key] = snapshot, item
        while len(self.selected) > 1000:
            self.selected.popitem(last=False)
        return item

    def search_reference_code(self, query: str, source_ids: list[str] | None = None, max_results: int = 5,
                              refresh: bool = False) -> EvidencePacket:
        self.validate(query, max_results)
        if source_ids is not None and (not 1 <= len(source_ids) <= 3 or len(set(source_ids)) != len(source_ids)):
            raise SourceSelectionError("source_ids accepts 1–3 distinct registered repository IDs from minecode.search_sources. For local artifacts, omit source_ids.")
        sources = []
        for sid in source_ids or []:
            if sid not in self.sources or self.sources[sid].get("source_type"):
                raise SourceSelectionError(
                    "source_ids accepts registered repository IDs from minecode.search_sources, not local artifact_id values. "
                    "To search local mapped artifacts, retry minecode.search_reference_code with the same query and omit source_ids. "
                    "Expand a returned result_id with minecode.get_reference_context.")
            sources.append(evidence(self.sources[sid]))
        with self.lock:
            local = self.search_local_content(query, max_results)
            preferred = [item for item in local.results if preferred_local(item)]
            if len(preferred) >= max_results and not refresh:
                if sources:
                    local.warnings.append("Version-qualified local results fill the result limit; selected repositories were not fetched.")
                return EvidencePacket(results=preferred[:max_results], warnings=local.warnings,
                                      truncated=local.truncated or bool(sources),
                                      truncation_reasons=[*local.truncation_reasons,
                                                          *(["repository_candidates_skipped"] if sources else [])])
            registered = self.search_content(query, sources, max_results, refresh) if sources else EvidencePacket()
            if sources and not local.results:
                local.warnings = [warning for warning in local.warnings
                                  if not warning.startswith("No version-qualified local")]
            supporting_local = [item for item in local.results if item not in preferred]
            combined = [*preferred, *registered.results, *supporting_local]
            return EvidencePacket(results=combined[:max_results],
                                  warnings=[*local.warnings, *registered.warnings],
                                  truncation_reasons=sorted(set([*local.truncation_reasons,
                                      *registered.truncation_reasons,
                                      *(["result_limit"] if len(combined) > max_results else [])])),
                                  truncated=local.truncated or registered.truncated or len(combined) > max_results)

    def search_local_content(self, query: str, limit: int) -> EvidencePacket:
        packet = EvidencePacket()
        terms = content_terms(query)
        identifiers = {word for word in re.findall(r'[A-Za-z][A-Za-z0-9_]*', query)
                       if word.lower() in terms}
        identifier_query = any('_' in word or re.search(r'[a-z][A-Z]', word) for word in identifiers)
        profile = inspect(self.project)
        artifacts = profile.local_reference_artifacts
        packet.truncation_reasons.extend(profile.local_reference_limitations)
        packet.truncated = bool(packet.truncation_reasons)
        if packet.truncated:
            packet.warnings.append("Local artifact discovery is incomplete: " + ", ".join(packet.truncation_reasons))
        if not artifacts:
            packet.warnings.append("No version-qualified local Loom/Gradle source artifacts were found. "
                                   "Inspect the project's exact-version mapped Minecraft JAR with native tools "
                                   "(for example javap); this search does not inspect compiled classes.")
            return packet
        scored = []
        for artifact in artifacts:
            try:
                snapshot_data = local_snapshot(artifact)
                candidate = local_evidence(artifact)
                limitations: list[str] = []
                rows = sorted(local_matches(snapshot_data, terms, identifiers=identifiers, limitations=limitations),
                              key=lambda row: (-row[3], -row[0], row[1], row[2]))
                if limitations:
                    packet.truncation_reasons.extend(limitations)
                    packet.warnings.append(artifact.artifact_id + ": partial search (" + ", ".join(limitations) + ")")
                seen = set()
                for score, path, line, coverage in rows:
                    # Explicit API queries must match an identifier, not only
                    # fragments such as Block/Entity in CampfireBlockEntity.
                    if identifier_query and not coverage:
                        continue
                    if path in seen:
                        continue
                    seen.add(path)
                    item = self.excerpt(candidate, snapshot_data, path, line)
                    item.score += score * 12
                    item.reasons.append("Lexical match in version-qualified local artifact")
                    scored.append((item, snapshot_data, coverage))
                    if len(seen) >= limit + 1:
                        break
            except (OSError, ValueError, TimeoutError) as exc:
                packet.truncation_reasons.append("local_artifact_unavailable")
                packet.warnings.append(artifact.artifact_id + ": " + str(exc)[:240])
            except Exception as exc:
                packet.truncation_reasons.append("local_artifact_unavailable")
                packet.warnings.append(artifact.artifact_id + ": local artifact unavailable (" + type(exc).__name__ + ")")
        if identifier_query and not scored:
            packet.warnings.append("No literal identifier match in the searched local artifacts; "
                                   "split-word matches were excluded.")
            if not any(artifact.kind == "minecraft-sources" for artifact in artifacts):
                packet.warnings.append(
                    f"No local Minecraft source archive was discovered for Minecraft {profile.minecraft_version} "
                    f"(project mappings: {profile.mappings_type or 'unknown'}). Fabric API sources and mapping "
                    "records are not Minecraft implementation bodies. Inspect the project's exact-version "
                    "mapped Minecraft JAR with native tools (for example javap); this search does not inspect compiled classes.")
        # Applicability is a boundary, not a finite bonus lexical matches can defeat.
        scored.sort(key=lambda pair: (not preferred_local(pair[0]), -pair[2],
                                     bool(pair[2]) and pair[0].provenance.get("artifact_kind") == "yarn-mappings",
                                     -pair[0].score, pair[0].source_id, pair[0].path or ""))
        if len(scored) > limit:
            packet.truncation_reasons.append("result_limit")
        packet.truncation_reasons = sorted(set(packet.truncation_reasons))
        packet.truncated = bool(packet.truncation_reasons)
        packet.results = [self.remember(snapshot_data, item) for item, snapshot_data, _ in scored[:limit]]
        return packet

    def search_content(self, query: str, candidates: list[Evidence], limit: int,
                       refresh: bool, metadata_fallback: bool = False,
                       prefer_version: bool = False) -> EvidencePacket:
        packet = EvidencePacket()
        scored = []
        terms = content_terms(query)
        if not terms:
            return packet
        for candidate in candidates:
            try:
                snapshot = self.cache.snapshot(self.sources[candidate.source_id], refresh)
                matches = sorted(self.cache.matches(snapshot, terms), key=lambda row: (-row[0], row[1], row[2]))
                # At most one initial result per file; expansion is explicit.
                seen = set()
                for score, path, line in matches:
                    if path in seen:
                        continue
                    seen.add(path)
                    item = self.excerpt(candidate, snapshot, path, line)
                    item.score += score * 12
                    item.reasons.append("Lexical match in cached content")
                    scored.append((item, snapshot))
                    if len(seen) >= limit + 1:
                        break
                if not matches and metadata_fallback:
                    candidate.reasons.append("Registry match only; no cached content match")
                    scored.append((candidate, None))
            except (OSError, ValueError, TimeoutError) as exc:
                packet.warnings.append(candidate.source_id + ": " + str(exc)[:240])
                if metadata_fallback:
                    candidate.reasons.append("Registry match only; content unavailable")
                    scored.append((candidate, None))
            except Exception as exc:
                # Network timeouts and subprocess timeouts are not all OSError subclasses.
                packet.warnings.append(candidate.source_id + ": retrieval unavailable (" + type(exc).__name__ + ")")
                if metadata_fallback:
                    scored.append((candidate, None))
        scored.sort(key=lambda pair: (
            VERSION_ORDER.get(pair[0].compatibility.get("minecraft", "unknown"), 2) if prefer_version else 0,
            -TRUST_ORDER.get(pair[0].trust, 0), -pair[0].score, pair[0].source_id, pair[0].path or ""))
        packet.truncated = len(scored) > limit
        packet.results = [self.remember(snapshot, item) if snapshot else item for item, snapshot in scored[:limit]]
        return packet

    def search_developer_knowledge(self, query: str, max_results: int = 5,
                                   source_ids: list[str] | None = None, fetch_content: bool = True,
                                   refresh: bool = False,
                                   **filters: Unpack[RankFilters]) -> EvidencePacket:
        self.validate(query, max_results)
        candidates = rank(self.sources, query, knowledge=True, **filters)
        if source_ids is not None:
            if not 1 <= len(source_ids) <= 3 or len(set(source_ids)) != len(source_ids):
                raise ValueError("Select 1–3 distinct documentation IDs")
            for sid in source_ids:
                if sid not in self.sources or not self.sources[sid].get("source_type"):
                    raise ValueError("Unknown developer-knowledge ID")
            # Explicit selection can include low-trust material; still enforce query/filter relevance.
            explicit_filters: RankFilters = {**filters, "include_experimental": True}
            candidates = [c for c in rank(self.sources, query, knowledge=True, **explicit_filters) if c.source_id in source_ids]
        if not fetch_content:
            return EvidencePacket(results=candidates[:max_results], truncated=len(candidates) > max_results)
        prefer_version = bool(filters.get('minecraft_version')) and not historical_query(query, filters.get('minecraft_version'))
        skipped = []
        if source_ids is None and prefer_version:
            skipped = [item for item in candidates if item.compatibility.get('minecraft') == 'mismatch']
            candidates = [item for item in candidates if item.compatibility.get('minecraft') != 'mismatch']
        with self.lock:
            packet = self.search_content(query, candidates[:3], max_results, refresh,
                                         metadata_fallback=True, prefer_version=prefer_version)
            packet.truncated |= len(candidates) > 3
            if skipped:
                packet.warnings.append('Known Minecraft version mismatches were not fetched automatically; '
                                       'use fetch_content=false to inspect them or select source_ids explicitly.')
                packet.truncated = True
                if not candidates:
                    packet.results = skipped[:max_results]
            return packet

    def get_reference_context(self, result_id: str, context_lines: int = 20) -> EvidencePacket:
        if type(context_lines) is not int or not 0 <= context_lines <= 50:
            raise ValueError("context_lines must be 0–50")
        with self.lock:
            if result_id not in self.selected:
                raise ValueError("Unknown/expired result_id; search again in this server session")
            snapshot, item = self.selected[result_id]
            if item.path is None:
                raise ValueError("Selected result has no retrievable path")
            if snapshot["kind"] == "local-archive":
                verify_local_snapshot(snapshot)
            center = ((item.start_line or 1) + (item.end_line or 1)) // 2
            expanded = self.excerpt(item, snapshot, item.path, center, context_lines, CONTEXT_CHARS)
            expanded.result_id = result_id
            return EvidencePacket(results=[expanded], truncated=expanded.content_truncated)
