"""Disposable, immutable snapshots outside the active project. Never execute reference code."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import signal
import time
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid
from .executables import resolve_executable
from .registry import ID, tokens

MAX_FILE = 512_000
MAX_DOCUMENT = 2_000_000
MAX_GIT_OUTPUT = 8_000_000
EXTENSIONS = {".java", ".kt", ".gradle", ".kts", ".json", ".toml", ".properties", ".md", ".mdx", ".txt", ".yaml", ".yml", ".mapping"}
NOISE = {".git", ".gradle", "build", "out", "target", "node_modules", "vendor", "generated", "assets", ".idea"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_path(path: str) -> bool:
    p = PurePosixPath(path)
    return (not p.is_absolute() and not any(c in path for c in "\\:\x00\r\n")
            and all(part not in {".", ".."} for part in path.split("/"))
            and not any(part.lower() in NOISE for part in p.parts)
            and p.suffix.lower() in EXTENSIONS and not re.search(r"\.(min|generated)\.", path))


def no_links(path: Path) -> None:
    for part in [path, *path.parents]:
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError("Cache paths must not contain symlinks or reparse points")


def git(args: list[str], cwd: Path | None = None, timeout: int = 90) -> bytes:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_TERMINAL_PROMPT="0", GIT_LFS_SKIP_SMUDGE="1")
    executable = resolve_executable("git", env=env, blocked_dirs=(Path.cwd(), cwd))
    if executable is None:
        raise ValueError("Git retrieval failed; check repository availability, Git installation and registered ref")
    command = [executable, "-c", "core.hooksPath=" + os.devnull, "-c", "credential.helper=",
               "-c", "protocol.allow=never", "-c", "protocol.https.allow=always",
               "-c", "http.followRedirects=false", *args]
    # Outputs are bounded before entering memory or a model response.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=errors, start_new_session=os.name != "nt")
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Git retrieval timed out; retry or select a smaller source")
                if os.fstat(output.fileno()).st_size > MAX_GIT_OUTPUT or os.fstat(errors.fileno()).st_size > MAX_GIT_OUTPUT:
                    raise ValueError("Git output limit reached; narrow the query or source")
                time.sleep(0.02)
        except BaseException:
            if os.name == "nt":
                try:
                    subprocess.run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"),
                                    "/PID", str(process.pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=5, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.kill()
            process.wait(timeout=5)
            raise
        if os.fstat(output.fileno()).st_size > MAX_GIT_OUTPUT:
            raise ValueError("Search output limit reached; narrow the query or selected source")
        if process.returncode not in (0, 1) or (process.returncode == 1 and "grep" not in args):
            raise ValueError("Git retrieval failed; check repository availability, Git installation and registered ref")
        output.seek(0)
        return output.read(MAX_GIT_OUTPUT)


def public_https(url: str, host: str | None = None) -> str:
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError("Only public HTTPS sources are supported")
    if host and p.hostname != host:
        raise ValueError("Cross-host documentation redirect refused")
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Non-public source address refused")
    return p.hostname


class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_https(newurl, urlsplit(req.full_url).hostname)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "header", "footer"}:
            self.ignored += 1
        if not self.ignored and tag in {"p", "div", "li", "br", "pre", "h1", "h2", "h3", "tr"}:
            self.output.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "header", "footer"} and self.ignored:
            self.ignored -= 1
        if not self.ignored and tag in {"p", "div", "li", "pre", "h1", "h2", "h3", "tr"}:
            self.output.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.output.append(data)


def fetch_document(url: str) -> tuple[str, dict]:
    public_https(url)
    request = Request(url, headers={"User-Agent": "MineCode-retrieval/0.1", "Accept": "text/html,text/plain,application/json"})
    with build_opener(SameHostRedirect()).open(request, timeout=20) as response:
        kind = response.headers.get_content_type()
        if kind not in {"text/html", "text/plain", "text/markdown", "application/json"}:
            raise ValueError("Unsupported documentation content type")
        body = response.read(MAX_DOCUMENT + 1)
        if len(body) > MAX_DOCUMENT:
            raise ValueError("Document exceeds download limit; register a more specific page")
        text = body.decode("utf-8", errors="replace")
        if kind == "text/html":
            parser = ReadableHTML()
            parser.feed(text)
            text = "\n".join(line.strip() for line in "".join(parser.output).splitlines() if line.strip())
        return text, {"url": response.url, "last_modified": response.headers.get("Last-Modified"),
                      "etag": response.headers.get("ETag")}


class ReferenceCache:
    def __init__(self, project: Path, root: Path | None = None, allow_network: bool = False):
        requested = (root or Path.home() / ".minecode" / "cache").absolute()
        # System-owned home/tmp ancestors may be links. Anchor once to their
        # canonical location; continue rejecting links at/inside the cache root.
        self.root = requested.parent.resolve() / requested.name
        no_links(self.root)
        project = project.resolve()
        resolved = self.root.resolve()
        if resolved == project or project in resolved.parents or resolved in project.parents:
            raise ValueError("Reference cache and active project must be disjoint")
        self.allow_network = allow_network
        self.pins: dict[str, dict] = {}

    def checked(self, path: Path) -> Path:
        no_links(path)
        if self.root.resolve() not in path.resolve().parents:
            raise ValueError("Path escapes reference cache")
        return path

    def folder(self, source: dict) -> Path:
        if not ID.fullmatch(source["id"]):
            raise ValueError("Invalid source ID")
        # URL, transport and ref jointly identify the requested evidence.
        identity_data = [source.get("canonical_url") or source["url"],
                         "document" if source.get("source_type") and source.get("transport", "document") != "repository" else "repository",
                         source.get("default_branch")]
        identity = hashlib.sha256(json.dumps(identity_data).encode()).hexdigest()[:16]
        return self.checked(self.root / (source["id"] + "-" + identity))

    @contextmanager
    def locked(self, source: dict):
        folder = self.folder(source)
        folder.mkdir(parents=True, exist_ok=True)
        lock = self.checked(folder / "fetch.lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ValueError("Source cache is locked; retry after its fetch completes (stale locks require manual removal)") from exc
        try:
            os.close(fd)
            yield folder
        finally:
            self.checked(lock).unlink()

    def snapshot(self, source: dict, refresh: bool = False) -> dict:
        sid = source["id"]
        cache_key = self.folder(source).name
        if cache_key in self.pins and not refresh:
            return self.pins[cache_key]
        # Snapshots are immutable and current.json is atomically replaced only
        # after a fetch completes. Readers need no writer lock or cache mutation.
        manifest = self.checked(self.folder(source) / "current.json")
        if manifest.exists() and not refresh:
            snapshot = json.loads(manifest.read_text(encoding="utf-8"))
            self.checked(Path(snapshot["location"]))
            self.pins[cache_key] = snapshot
            return snapshot
        if not self.allow_network:
            raise ValueError("Source not cached (or refresh requested); enable --allow-retrieval-network explicitly")
        with self.locked(source) as folder:
            manifest = self.checked(folder / "current.json")
            if manifest.exists() and not refresh:
                snapshot = json.loads(manifest.read_text(encoding="utf-8"))
                self.checked(Path(snapshot["location"]))
                self.pins[cache_key] = snapshot
                return snapshot
            if not self.allow_network:
                raise ValueError("Source not cached (or refresh requested); enable --allow-retrieval-network explicitly")
            location = self.checked(folder / uuid.uuid4().hex)
            location.mkdir()
            url = source.get("canonical_url") or source["url"]
            snapshot = {"source_id": sid, "location": str(location), "retrieved_at": now(), "url": url}
            if source.get("source_type") and source.get("transport", "document") != "repository":
                text, metadata = fetch_document(url)
                snapshot.update(metadata)
                snapshot["revision"] = "sha256:" + hashlib.sha256(text.encode()).hexdigest()
                (location / "document.txt").write_text(text, encoding="utf-8")
                snapshot["kind"] = "document"
            else:
                public_https(url)
                # No checkout, submodules, LFS, hooks, filters or downloaded executables.
                args = ["clone", "--bare", "--depth=1", "--single-branch", "--no-tags", "--template="]
                ref = source.get("default_branch")
                if ref:
                    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}", ref) or ".." in ref:
                        raise ValueError("Invalid registered ref")
                    args += ["--branch", ref]
                git([*args, "--", url, str(location / "repo.git")])
                repo = location / "repo.git"
                revision = git(["rev-parse", "HEAD"], repo).decode().strip()
                if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
                    raise ValueError("Invalid repository revision")
                snapshot.update(kind="repository", revision=revision, ref=ref)
                tree = git(["ls-tree", "-r", "-l", "-z", revision], repo)
                entries = {}
                for row in tree.split(b"\0"):
                    if not row or b"\t" not in row:
                        continue
                    info, raw_path = row.split(b"\t", 1)
                    mode, kind, blob, size = info.split()
                    path = raw_path.decode("utf-8", errors="replace")
                    if mode not in {b"100644", b"100755"} or kind != b"blob" or not safe_path(path) or int(size) > MAX_FILE:
                        continue
                    entries[path] = {"blob": blob.decode(), "size": int(size)}
                if len(entries) > 50_000:
                    raise ValueError("Repository exceeds searchable file limit")
                (location / "files.json").write_text(json.dumps(entries), encoding="utf-8")
            pending = self.checked(folder / "pending.json")
            pending.write_text(json.dumps(snapshot), encoding="utf-8")
            pending.replace(manifest)
            self.pins[cache_key] = snapshot
            return snapshot

    def read(self, snapshot: dict, path: str) -> str:
        location = self.checked(Path(snapshot["location"]))
        if snapshot["kind"] == "document":
            if path != "document.txt":
                raise ValueError("Invalid document path")
            file = self.checked(location / path)
            if file.stat().st_size > MAX_DOCUMENT:
                raise ValueError("Cached document exceeds limit")
            text = file.read_text(encoding="utf-8")
            if "sha256:" + hashlib.sha256(text.encode()).hexdigest() != snapshot["revision"]:
                raise ValueError("Cached document changed; explicitly refresh the source")
            return text
        if not safe_path(path):
            raise ValueError("Unsafe or excluded reference path")
        entries = json.loads(self.checked(location / "files.json").read_text(encoding="utf-8"))
        entry = entries.get(path)
        if not entry or not re.fullmatch(r"[0-9a-f]{40,64}", entry["blob"]):
            raise ValueError("Path is not a selected text blob")
        repo = self.checked(location / "repo.git")
        raw = git(["cat-file", "blob", entry["blob"]], repo)
        if len(raw) > MAX_FILE or b"\0" in raw:
            raise ValueError("Binary or oversized text blob")
        return raw.decode("utf-8", errors="replace")

    def matches(self, snapshot: dict, terms: set[str]) -> list[tuple[int, str, int]]:
        location = self.checked(Path(snapshot["location"]))
        if snapshot["kind"] == "document":
            text = self.read(snapshot, "document.txt")
            lowered = text.lower()
            # An API member mentioned a few times is more useful than the class name
            # repeated throughout a Javadoc page. Keep scores integer and bounded.
            weights = {term: max(1, 100 // max(1, lowered.count(term))) for term in terms}
            return [(sum(weights[t] for t in terms if t in line), "document.txt", i)
                    for i, line in enumerate(lowered.splitlines(), 1) if any(t in line for t in terms)]
        entries = json.loads(self.checked(location / "files.json").read_text(encoding="utf-8"))
        args = ["grep", "--no-ext-grep", "--no-textconv", "-I", "-n", "-i", "-F"]
        for term in sorted(terms):
            args += ["-e", term]
        args += [snapshot["revision"], "--", *["*" + ext for ext in sorted(EXTENSIONS)]]
        raw = git(args, self.checked(location / "repo.git"))
        matches = []
        for row in raw.decode("utf-8", errors="replace").splitlines():
            parts = row.split(":", 3)
            if len(parts) == 4 and parts[1] in entries and parts[2].isdigit():
                _, path, line, text = parts
                score = sum(t in text.lower() for t in terms)
                score += 3 * len(terms & tokens(PurePosixPath(path).stem))
                score += sum(t in path.lower() for t in terms)
                matches.append((score, path, int(line)))
        return matches
