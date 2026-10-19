# Selective reference retrieval

MineCode searches for the few lines that answer the question, not an entire repository to dump into the conversation. It checks recognized local sources before selected external references and keeps version, mapping, and source details attached. No paid API, model call, vector database, or cloud account is required.

## Search, then expand

For local artifacts, pass `query` and omit `source_ids`. That parameter accepts registered repository IDs, not local `artifact_id` values. Expand returned `result_id` values in the same server session.

1. Inspect the active project using existing tools. Resolve Minecraft, loader, Java, mappings and sides; do not assume Yarn or Mojang names.
2. `minecode.search_sources(query, minecraft_version, loader, language, mappings, side, categories, max_results=5)` ranks metadata without downloads. `strict_version=true` accepts only an exact declared Minecraft version; unknowns and patch-family matches are excluded. Normal ranking retains potentially useful mismatches with explicit labels.
3. `minecode.search_reference_code(query, source_ids, max_results=5, refresh=false)` first searches version-qualified local Loom/Gradle artifacts discovered for the active project, then up to 1–3 optionally selected repositories. When exact local version/mapping results fill the requested limit, selected repositories are skipped with an explicit warning; `refresh=true` still fetches them. Exact local evidence precedes registered references; namespace mismatches and unknowns remain explicit. No automatic fallback to experimental sources. Explicit IDs count as deliberate selection, including historical/experimental research.
4. `minecode.get_reference_context(result_id, context_lines=20)` expands a chosen result from its registered snapshot or selected local artifact revision; changed local artifacts are rejected. Result IDs are session-local; the last 1,000 are retained. Search again after restart/eviction.
5. `minecode.search_developer_knowledge(query, minecraft_version, mappings, max_results=5, source_ids, fetch_content=true, refresh=false, strict_version=false)` ranks registered documentation separately and inspects at most three selected/highest-ranked sources. With a requested Minecraft version, known version mismatches are not fetched automatically unless the query concerns historical/migration work. Explicit source IDs can still select them. If only mismatches exist, the result contains labeled metadata and a warning. `fetch_content=false` is registry-only discovery. Offline misses or failed fetches explicitly return registry matches and warnings, never fabricated excerpts.

Example: search sources for `Java Fabric module settings architecture` with the project's version and mappings; select `meteor-client`; search `Modules Settings`; expand one returned result ID. For `Mixin inject HEAD callback cancellable`, search developer knowledge and select an official injector page. Neither action authorizes reuse of upstream code.

## Registry and ranking

`mappings` identifies a family such as `yarn` or `mojang-official`.
The optional `mappings_version` filter on source and developer-knowledge search
compares a specific mapping build separately. A Yarn family match does not establish
a build match, and `strict_version` still filters only Minecraft. Legacy input such
as `yarn-1.21.11+build.3` is normalized into these two dimensions. A declared namespace
is separate metadata; these tools do not translate names between namespaces.

`references/sources/sources.yaml` is the authoritative implementation-reference registry. Entries describe reviewed source identity, subsystem relevance, compatibility and reuse limits. Source availability and dependencies still need checking for the active project.

`references/sources/developer-knowledge.json` uses the same version-one source-envelope conventions. It adds `source_type`, `transport` (single page or repository), and optional `repository_source_id`. Repository-backed documentation inherits license, approvals, language, environment and branch from its existing implementation entry rather than creating a competing authority. Source checkouts read these files directly; wheel builds include a copy generated from those authorities.

Ranking uses lexical matches in title/category/tags/use cases, curated priority, explicit environment matches/mismatches, preferred language, historical intent and archive status. When a query contains topic words, generic environment words such as Minecraft, Java and Fabric cannot make an unrelated source relevant; the same topic terms are used for content search. Environment-only queries still work. Unknown compatibility receives no invented match bonus. Java gets preference over Kotlin for otherwise equivalent candidates. Stable source IDs break ties. Stars are unused. For ordinary versioned queries, Minecraft applicability precedes authority and lexical score in both metadata and fetched content. Mapping differences remain explicit. Experimental material is excluded by default.

The initial developer registry covers official Fabric developer/networking docs, Loom, Loader, API source/Javadocs, example mod, migration/mapping guidance, release announcements, Yarn source/versioned Javadocs, and SpongePowered Mixin wiki, callback/injection-point guides, maintainer internals and source Javadocs. Current Fabric guides observed on 2026-10-06 target 26.2, so they are not represented as 1.21-compatible. The 1.21 networking API page is explicitly versioned. Yarn Javadocs are labeled Yarn; the agent must check its active namespace.

Registered issue/PR pages and specific comment URLs can use `issue-discussion`, `pr-discussion`, `issue-comment` or `pr-comment`; optional `discussion` metadata carries repository, number, author, author-role evidence, date, topic and version relevance. Unknown roles/dates remain null. They use the same bounded HTTPS page reader and lower authority. No arbitrary issue crawler, GitHub-wide search, automatic maintainer-role inference or initial community-comment corpus is provided. Register a specific discussion after primary evidence proves insufficient. HTML retrieval may omit dynamically loaded comments; a page match is not proof every comment was inspected.

## Cache and offline behavior

Default: `Path.home() / '.minecode' / 'cache'`, compatible with Windows without a hardcoded username. `--reference-cache PATH` can choose a disjoint location outside the selected development project. Cache creation is lazy. Ancestors such as a linked home or system temporary directory are resolved once to a canonical parent. Links/reparse points at or inside the cache root and project/cache overlap are rejected.

`--allow-retrieval-network` permits selected public retrieval. It is separate from `--allow-network` (Gradle) and `--allow-execution` (trusted project scripts). Cached searches and expansions need neither network permission nor authentication. Public HTTPS Git uses installed Git with no credentials/helper prompts. No account is required.

Each source ID, canonical URL, transport and registered ref combination has a manifest pointing to an immutable snapshot directory. Repositories are shallow, single-branch **bare** clones: no checkout, hooks, filters, submodules or LFS execution. Reads use tree/blob objects and lexical Git search, with filename-token relevance bonuses. Snapshots record ref, commit and retrieval time. Only the searchable file index is generated; fetches do not profile architecture or read unrelated source files. Registry applicability remains declared metadata, not verification of the fetched build.

Local discovery reads only conventional project/global Loom Minecraft Maven locations and exact declared Yarn/Fabric API module-cache coordinates. It does not run Gradle, scan the home directory, extract archives, copy artifacts, or mutate caches. Before Python indexes a ZIP, a bounded metadata check validates the actual central-directory framing, at most 50,000 entries and 16 MB of directory metadata. Excessive or malformed directories are rejected entirely, with an unavailable-artifact warning; other scan limits still preserve partial matches. Classic ZIPs, fixed-size ZIP64 footers, per-entry ZIP64 and normal comments are supported. Split archives and ZIP64 extensible footers are rejected. The check and indexing use the same open file handle. Project profiles report discovered artifacts, scope, namespace and exact/supporting compatibility. `refresh` affects registered repositories only; local artifacts are observed again on each search, and context expansion rejects an artifact changed since selection.

Static profiles use literal dependency declarations and supported property/catalog
references. An unused `gradle.properties` key or a quoted coordinate in a log message
does not establish a version. Custom/computed Gradle logic can remain unknown;
declarations are not proof of dependency resolution.

Partial local discovery/search sets `truncated` and names the limits in
`truncation_reasons` (for example `directory_child_limit`, `artifact_candidate_limit`,
`archive_scan_byte_limit` or `archive_match_file_limit`). Profiles expose discovery
limits as `local_reference_limitations`. Earlier matches survive a scan limit.
Each archive contributes its best matching line per file, so repeated hits in one
file cannot consume the 2,000 matching-file budget. Empty partial results do not
establish that the requested API is absent.

Fabric API module sources are also discovered through literal direct dependencies in the selected version's cached POM (at most eight POMs of 256 KB and 64 module archives, in addition to twelve primary artifacts). Unresolved, conflicting, optional, and non-runtime dependencies are excluded. The parent dependency establishes the Fabric API relationship; the source mapping namespace remains unknown.

Documentation uses a single-page HTTPS fetch, readable HTML/text extraction and a SHA-256 text revision, with retrieval time and available ETag/Last-Modified. Cached document hashes are rechecked before returning content. No links are crawled. Same-host redirects are checked; non-public addresses, credentials, non-HTTPS schemes and unexpected content types are rejected. No downloaded script or binary is executed.

The first snapshot used for each source identity in a server session stays pinned. A URL, transport or ref change selects a separate cache entry. Older URL-only cache entries are left untouched and require a one-time refetch with retrieval network enabled. Only `refresh=true` fetches again; existing result IDs still expand the old snapshot. Refresh failures do not replace the current manifest. Published snapshots can be read without acquiring a writer lock, including offline and while a fetch is active or its lock is stale. Per-source exclusive lock files prevent concurrent writers; a crashed fetch can leave a stale lock that blocks a new fetch. Stop affected servers and remove that exact lock before retrying the fetch. Incomplete snapshots are disposable and never used without an atomically published manifest.

Cache deletion is deliberately manual: stop servers, confirm the configured cache path is outside your project, and remove that cache directory using your OS. It is rebuilt on demand. No cache-clear tool accepts arbitrary paths. Default/accidental `.minecode/`, `.cache/` and `reference-cache/` directories are Git-ignored. Git object storage has no total disk quota: large repositories may still consume substantial space; shallow fetching, timeout and selected-source limits reduce this but do not constitute a disk sandbox.

## Context and resource limits

| Boundary | Default / maximum |
| --- | --- |
| Query | 1–300 characters |
| Returned candidates/hits | 5 / 10 |
| Selected repositories or fetched knowledge sources | at most 3 |
| Initial content | one matching line, at most 600 characters per hit; one hit per file |
| Expanded context | 20 neighboring lines / 50 each side (101 total), at most 8,000 characters |
| Source text blob | 512,000 bytes; binaries excluded |
| Local artifact | 256 MB archive; 50,000 entries; 16 MB per entry; 64 MB searchable text per archive |
| Documentation response | 2,000,000 bytes; HTTP socket timeout 20 seconds |
| Git command | 90 seconds; process-tree stop on timeout; output cap 8 MB checked during execution |
| Searchable tree | at most 50,000 accepted files, also limited by tree-list output cap |

Noise filtering excludes `.git`, build/dependency/cache directories, assets, generated/minified files, symlink blobs, submodules and oversized/binary text. Java/Kotlin/build/config/Markdown/text and mapping files are eligible. Local search can examine many files; only a few hits reach the agent. Output truncation and fetch failures are explicit. Narrow a query when the local search cap is reached. Limits are character/line bounds, not tokenizer-specific guarantees.

Content search preserves literal camel-case and underscore API names alongside their words. Within a documentation page, infrequent query terms receive more weight than repeated class-name boilerplate. This helps a query such as `WorldRenderEvents AFTER_ENTITIES` reach the named event rather than a neighboring nested-class entry. It remains lexical retrieval, not semantic API resolution.

## Evidence, rights and security

Explicit CamelCase/underscore local queries reject matches with no literal identifier coverage. If Minecraft source is unavailable, inspect the exact-version mapped Minecraft JAR with native tools such as `javap`. Compiled classes are not searched and no source is automatically decompiled. Literal hits still require checking ownership and behavior.

Every result retains source ID, URL, type, trust, priority, historical status, declared environment, language, license, separate reuse/derivation/redistribution approvals, provenance, selection reasons and compatibility labels. Content adds exact commit/hash, path, line range, retrieval time and an opaque result ID. A reported permissive license alone does not override unapproved reuse; unknown rights are `reference-only`, unapproved known rights are `reuse-unapproved`, and approved non-permissive cases still `require-review`.

All packets carry an evidence-only policy and every result is explicitly `untrusted: true`. README instructions, comments and documentation remain source text. No retrieved text is evaluated, interpolated into a shell command, promoted to server instructions or used to invoke Gradle. Prompt-injection-looking content is not silently rewritten or treated as authority. The consuming coding agent must honor the evidence boundary; this is not a guarantee that every downstream model resists prompt injection.

Research escalation: local project/build/runtime evidence → current applicable official documentation/source → maintained references → historical/specialized references → specific issue/PR research. Experimental research requires deliberate selection. Contradictions, missing APIs, mapping differences or unexplained failures trigger further investigation, not forced adoption of a vaguely similar implementation.

There is no CLI or tool for importing project knowledge or adding user sources to the registry. The core can receive a separately supplied registry, but the beta has no user-facing source-registration flow.

A rotation manager or event dispatcher found in another project is a research lead, not a ready-made answer. Check whether the idea fits, write the change, and verify it in the target project. Code reuse needs its own rights review. See [working with MineCode](WORKFLOW.md) and the [test record](CAPABILITIES.md). Retrieval doesn't teach MineCode new rules automatically.

## Ranking and curation

Registry totals: 22 implementation references / 35 developer entries. Source quality records maintenance, historical significance, technical usefulness, source completeness, subsystem coverage, licensing confidence and compatibility limits independently. Existing environment fields hold Minecraft/loader/mapping relevance. Unreviewed dimensions remain unknown; stars are not scored. Historical status does not subtract score by itself; explicit environment mismatches still do. Subsystem matches add at most six points; documentation-only default branches receive a source-completeness warning/penalty.

Within the version applicability order, developer ranking prefers official evidence, maintainer documentation, verified MEMBER/OWNER explanations with provenance, technical community writing, then general discussion. Association is evidence of upstream membership, not proof of every assertion. A contributor PR does not automatically become a maintainer explanation. No issue crawler exists. New sources do not increase existing per-call/page/excerpt limits. Canonical URLs are deduplicated within each channel; an explicitly linked implementation source and its developer-source view remain distinct purposes.

## Gameplay terminology

[The static registry](../references/gameplay/techniques.json) contains 24 entries: sword 4, movement 1, mace 4,
pearls 4, wind-charge 2, shield 2, crystal 2, anchor 2 and inventory 3. It is separate from the implementation
references and developer-knowledge sources; these are different kinds of evidence.

Use `minecode.search_gameplay_techniques(query, max_results=3, category=null)` before searching implementations
when a user's term is unclear. Examples: `IPC`, `What is a P-crit?`, `W-tap`, `stunslam`, `slam`.
Exact normalized names/aliases rank first; whole alias phrases and lexical matches follow with deterministic ties.
Unknown queries return no results. This is a small glossary, not semantic search or an API compatibility resolver.

Each entry keeps definition, mechanic, actions, version context, server/timing dependence, client/server relevance,
related techniques, development and automation relevance, confidence, source links/check date and uncertainty.
The latter two implementation-oriented fields are explicitly MineCode analysis, not claims copied from a gameplay source.
Confidence describes support for the explanation, not successful testing on a user's server.

Names and aliases are Unicode-normalized and must be unique, including within an entry. IDs must be unique;
related IDs must exist. Sources require HTTPS attribution, type, date and support scope. Schema violations fail
closed. Registry size is capped at 256 KiB / 40 entries. Queries allow 1–300 characters, result limits 1–5
(booleans rejected), output at 16,000 characters. Entries are removed whole when the bound is reached, retaining
provenance and context; output is never cut through JSON or a caveat. Lookup uses packaged resources offline
and performs no downloads, learning, writes, game actions or source-code retrieval.

### Research limits and use

Research/check date is 2026-10-07, not a claim that every cited page describes the latest release. Official mechanics
articles and release notes establish their publication-era behavior. Wiki material supplies community terminology;
some individual Wiki pages were unavailable to direct fetching and their search-index excerpts were used for basic
hand/slot terminology. No access restriction was bypassed. Project descriptions explain what maintainers claim,
not what MineCode independently tested. No gameplay technique in this registry was experimentally validated by MineCode.

IPC is specifically environment-dependent: the cited server mod changes same-tick pearl/wind-charge interaction.
Pearl catch also has a pursuit meaning; clarify context before implementation. Breach/attribute swapping is not a
stable supported mechanic: Mojang's 26.2 pre3 notes reverted a fix while explicitly promising a later fix. Recheck the
actual release and server rather than assuming the behavior still exists. Timing is not a universal tick/millisecond recipe.
Do not infer server permission, anti-cheat compatibility or bypass guarantees from a term.

Descriptions are concise original factual explanations with attribution, not copied implementations, article archives,
images or scripts. Linked sources retain their own rights; see [third-party notices](../THIRD_PARTY_NOTICES.md) and
[licensing policy](LICENSING.md) before code reuse. Keep changes manual and reviewed. There is no runtime registry update or promotion path.

Tests cover schema, context/provenance, duplicate IDs/aliases, related IDs, exact/natural alias lookup, unknown terms,
category filtering, deterministic ranking, input bounds, oversized files and whole-entry output truncation. Installed
package acceptance exercises IPC lookup without relying on the repository checkout.
