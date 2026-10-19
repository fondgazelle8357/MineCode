"""Version-one registry reader and deterministic, explainable ranking."""
import json
import re
from importlib.resources import files
from pathlib import Path
import yaml
from .retrieval_models import Evidence

ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
STOP = {"a", "an", "the", "in", "of", "to", "for", "and", "with", "how", "does", "add", "use"}
TRUST_ORDER = {'primary': 5, 'maintainer-documentation': 4, 'maintainer-explanation': 3,
               'community-technical': 2, 'community-discussion': 1}
ENVIRONMENT_TERMS = {'minecraft', 'java', 'fabric', 'forge', 'neoforge', 'yarn', 'mojang', 'official'}
VERSION_ORDER = {'exact-declared': 0, 'same-family-not-exact': 1, 'unknown': 2, 'mismatch': 3}


def canonical_key(url):
    return url.lower().rstrip('/').removesuffix('.git')


def mapping_identity(family: str | None, version: str | None = None) -> tuple[str | None, str | None]:
    """Accept the legacy Yarn label while keeping family and build distinct."""
    match = re.fullmatch(r"yarn-(\d+\.\d+(?:\.\d+)*(?:-(?:pre|rc)\d+)?\+build\.\d+)", family or "", re.I)
    if match:
        if version is not None and version != match[1]:
            raise ValueError("Conflicting Yarn mapping build versions")
        return "yarn", match[1]
    return family, version


def tokens(text: str) -> set[str]:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    result = set()
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        if word in STOP or len(word) <= 1:
            continue
        result.add(word)
        if word.endswith("sses"):
            result.add(word[:-2])
        elif len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
            result.add(word[:-1])
    return result


def query_terms(query: str) -> set[str]:
    terms = tokens(query)
    topic = {term for term in terms - ENVIRONMENT_TERMS if not term.isdecimal()}
    return topic or terms


def content_terms(query: str) -> set[str]:
    # Preserve literal API names as well as their words (e.g. AFTER_ENTITIES).
    identifiers = {word.lower() for word in re.findall(r'[A-Za-z][A-Za-z0-9_]*', query)
                   if '_' in word or re.search(r'[a-z][A-Z]', word)}
    return query_terms(query) | identifiers


def historical_query(query: str, minecraft_version: str | None = None) -> bool:
    return bool({'historical', 'legacy', 'migration', 'old'} & tokens(query)) or \
        (minecraft_version or '').startswith('1.12') or '1.12' in query


def load_registry(directory: Path | None = None) -> dict[str, dict]:
    # Source checkout uses the authority directly. Wheels contain its build-time copy.
    directory = directory or Path(__file__).resolve().parents[2] / "references" / "sources"
    base = directory if directory.is_dir() else files("minecode_runtime").joinpath("data")
    sources = {}
    urls = set()
    for name in ("sources.yaml", "developer-knowledge.json"):
        raw = base.joinpath(name).read_text(encoding="utf-8")
        data = yaml.safe_load(raw) if name.endswith("yaml") else json.loads(raw)
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported registry schema")
        for source in data["sources"]:
            sid = source["id"]
            if not ID.fullmatch(sid) or sid in sources:
                raise ValueError("Invalid or duplicate source ID")
            key = (bool(source.get('source_type')), canonical_key(source.get('canonical_url') or source['url']))
            if key in urls:
                raise ValueError('Duplicate source URL in the same registry channel')
            urls.add(key)
            for field in ('name', 'category', 'environment', 'license', 'code_reuse'):
                if field not in source:
                    raise ValueError('Missing source field: ' + field)
            for field in ('environment', 'license', 'code_reuse'):
                if not isinstance(source[field], dict):
                    raise ValueError('Expected object for source field: ' + field)
            for field in ('allowed', 'generated_derivation_allowed', 'redistribution_allowed'):
                if type(source['code_reuse'].get(field)) is not bool:
                    raise ValueError('Reuse approvals must be explicit booleans')
            quality=source.get('quality', {})
            if not isinstance(quality, dict) or quality.get('maintenance', 'unknown') not in {'active', 'archived', 'historical', 'unknown', 'moved'}:
                raise ValueError('Invalid source quality metadata')
            if not isinstance(quality.get('unique_subsystems', []), list) or not all(isinstance(x,str) for x in quality.get('unique_subsystems', [])):
                raise ValueError('Subsystem coverage must be a string list')
            sources[sid] = source
    for source in sources.values():
        parent_id = source.get("repository_source_id")
        if parent_id:
            parent = sources[parent_id]
            for field in ("license", "code_reuse", "language", "environment", "default_branch"):
                source[field] = parent.get(field)
    return sources


def evidence(source: dict) -> Evidence:
    environment = dict(source.get("environment", {}))
    family, mapping_version = mapping_identity(environment.get("mappings"), environment.get("mappings_version"))
    if family is not None:
        environment["mappings"] = family
    if mapping_version is not None:
        environment["mappings_version"] = mapping_version
    historical = source.get("historical", source.get("priority") == "legacy")
    trust = source.get("trust", "experimental" if source.get("priority") == "experimental" else
                       "historical" if historical else "curated-reference")
    if source.get("source_type") in {"issue-comment", "pr-comment", "issue-discussion", "pr-discussion"}:
        author = source.get('discussion', {})
        trust = ('maintainer-explanation' if author.get('author_association') in {'MEMBER', 'OWNER'}
                 and author.get('provenance_url') else 'community-discussion')
    license_info = source.get("license", {})
    reuse = source.get("code_reuse", {})
    reported = license_info.get("reported")
    status = "reference-only" if not reported or reported == "NOASSERTION" else "reuse-unapproved"
    if reuse.get("allowed"):
        status = "permissive" if reported in {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "CC0-1.0"} else "requires-review"
    return Evidence(source_id=source["id"], title=source["name"],
                    url=source.get("canonical_url") or source["url"],
                    source_type=source.get("source_type", "repository"), trust=trust,
                    priority=source.get("priority", "specialized"), historical=historical,
                    language=source.get("language"), environment=environment,
                    license=license_info, code_reuse=reuse, reuse_status=status,
                    quality=source.get('quality', {}),
                    provenance={"review": source.get("review", {}), "notes": source.get("notes", ""),
                                "discussion": source.get("discussion"), "technical_summary": source.get('technical_summary'),
                                "scope": "curated-reference"})


def rank(sources: dict[str, dict], query: str, *, knowledge: bool = False,
         minecraft_version: str | None = None, loader: str | None = None,
         language: str | None = "Java", mappings: str | None = None, side: str | None = None,
         categories: list[str] | None = None, strict_version: bool = False,
         include_experimental: bool = False, mappings_version: str | None = None) -> list[Evidence]:
    mappings, mappings_version = mapping_identity(mappings, mappings_version)
    terms = query_terms(query)
    if not terms:
        return []
    historical_intent = historical_query(query, minecraft_version)
    found = []
    for source in sources.values():
        if bool(source.get("source_type")) != knowledge:
            continue
        item = evidence(source)
        if item.trust == "experimental" and not include_experimental:
            continue
        if categories and source["category"] not in categories:
            continue
        task_text = " ".join([source["name"], source["category"], *source.get("tags", []), *source.get("use_for", [])])
        matched = terms & tokens(task_text)
        # Environment-only matches must not make an unrelated source relevant.
        if not matched:
            continue
        item.score = 12 * len(matched)
        item.reasons = ["Task matches: " + ", ".join(sorted(matched))]
        item.score += {"core": 8, "specialized": 4, "legacy": 4, "experimental": -12}.get(item.priority, 0)
        quality=source.get('quality', {})
        if quality.get('source_completeness') == 'default-branch-docs-only':
            item.score -= 12
            item.reasons.append('Default branch has documentation only; select a reviewed source branch before code retrieval.')
        coverage=terms & tokens(' '.join(quality.get('unique_subsystems', [])))
        if coverage:
            item.score += min(6, 2 * len(coverage))
            item.reasons.append('Reviewed subsystem coverage: ' + ', '.join(sorted(coverage)))
        for field, requested in (("minecraft", minecraft_version), ("loader", loader), ("mappings", mappings),
                                 ("mappings_version", mappings_version), ("side", side)):
            if not requested:
                continue
            actual = item.environment.get(field)
            if actual is None:
                state = "unknown"
            elif str(actual).lower() == requested.lower():
                state = "exact-declared"
            elif field == "minecraft" and str(actual).startswith(requested + "."):
                state = "same-family-not-exact"
            else:
                state = "mismatch"
            item.compatibility[field] = state
            item.score += {"exact-declared": 14, "same-family-not-exact": 4, "unknown": 0, "mismatch": -16}[state]
            if field == "minecraft" and state == "unknown":
                item.reasons.append("Minecraft applicability unknown.")
        if strict_version and item.compatibility.get("minecraft") != "exact-declared":
            continue
        if language:
            item.compatibility["language"] = "match" if (item.language or "").lower() == language.lower() else "different-or-unknown"
            item.score += 7 if item.compatibility["language"] == "match" else 0
        if item.historical:
            item.reasons.append("Historical concepts remain useful; exact implementation needs revalidation.")
            if historical_intent:
                item.score += 20
        if source.get("archived"):
            item.reasons.append("Archived source; no current maintenance assumed.")
        item.reasons.append("Reuse: " + item.reuse_status)
        found.append(item)
    # For ordinary versioned queries, applicability precedes authority and lexical score.
    return sorted(found, key=lambda x: (
        VERSION_ORDER.get(x.compatibility.get("minecraft", "unknown"), 2)
        if minecraft_version and not historical_intent else 0,
        -TRUST_ORDER.get(x.trust, 0) if knowledge else 0,
        -x.score,
        x.source_id,
    ))
