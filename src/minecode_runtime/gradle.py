"""Fixed wrapper invocations within one trusted project; no general shell tool."""
import asyncio
from collections import deque
import os
import re
import signal
import time
from pathlib import Path
from .diagnostics import analyze, MAX_LOG_LINE
from .output_safety import sanitize
from .inspection import contained, inspect
from .models import Artifact, BuildResult, ClientResult, GradleResult

TASK_PATTERN = r"^:?(?:[A-Za-z0-9_][A-Za-z0-9_-]*:)*(?:build|classes|test|runClient)$"
OUTPUT_LIMIT = 64000


def validate_task(task: str) -> None:
    if not isinstance(task, str) or len(task) > 128 or not re.fullmatch(TASK_PATTERN, task):
        raise ValueError("Allowed task names: build, classes, test, runClient, optionally module-qualified.")


def wrapper_command(root: Path, task: str, offline: bool, *, discovery: bool = False,
                    windows: bool | None = None) -> list[str]:
    if not discovery:
        validate_task(task)
    elif task != "tasks":
        raise ValueError("Invalid internal discovery task.")
    windows = os.name == "nt" if windows is None else windows
    name = "gradlew.bat" if windows else "gradlew"
    wrapper = root / name
    if not wrapper.is_file() or not contained(root, wrapper):
        raise FileNotFoundError(f"Missing local {name}; add the project's Gradle wrapper.")
    args = ["--no-daemon", "--console=plain"]
    if offline:
        args.append("--offline")
    args += [task]
    if discovery:
        args.append("--all")
    if windows:
        # Explicitly select the validated project wrapper without putting the user path in shell text.
        return [str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "cmd.exe"),
                "/d", "/s", "/c", " ".join([r".\gradlew.bat", *args])]
    return [str(wrapper), *args]


async def stop_tree(process: asyncio.subprocess.Process) -> bool:
    """Bound cleanup and return whether the OS tree-stop operation succeeded."""
    tree_stopped = False
    try:
        if os.name == "nt":
            killer = await asyncio.create_subprocess_exec(
                str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"),
                "/PID", str(process.pid), "/T", "/F", stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL)
            try:
                tree_stopped = await asyncio.wait_for(killer.wait(), 5) == 0
            except TimeoutError:
                killer.kill()
                try:
                    await asyncio.wait_for(killer.wait(), 2)
                except TimeoutError:
                    pass
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                tree_stopped = True
            except ProcessLookupError:
                tree_stopped = process.returncode is not None
    except OSError:
        pass
    try:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.wait(), 3)
    except (OSError, TimeoutError):
        return False
    return tree_stopped


async def capture(stream: asyncio.StreamReader) -> tuple[str, bool]:
    # Keep bounded complete lines until redaction. Trimming raw bytes can detach
    # a credential from its label, including across subprocess read boundaries.
    lines: deque[str] = deque()
    size = 0
    pending = bytearray()
    oversized = False
    truncated = False

    def emit(newline: str = "") -> None:
        nonlocal size, truncated
        clean = "[oversized log line omitted]" if oversized else sanitize(pending.decode("utf-8", errors="replace"))
        lines.append(clean + newline)
        size += len(lines[-1])
        while size > OUTPUT_LIMIT:
            size -= len(lines.popleft())
            truncated = True

    while chunk := await stream.read(8192):
        parts = chunk.split(b"\n")
        for index, part in enumerate(parts):
            if not oversized:
                if len(pending) + len(part) > MAX_LOG_LINE:
                    pending.clear()
                    oversized = truncated = True
                else:
                    pending.extend(part)
            if index < len(parts) - 1:
                emit("\n")
                pending.clear()
                oversized = False
    if pending or oversized:
        emit()
    return "".join(lines), truncated


class Runtime:
    def __init__(self, project: Path, *, allow_execution: bool = False, allow_network: bool = False):
        self.root = project.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Selected project must be a directory.")
        self.allow_execution = allow_execution
        self.offline = not allow_network
        self.lock = asyncio.Lock()

    async def _execute(self, task: str, timeout_seconds: int, *, discovery: bool = False) -> GradleResult:
        if not discovery:
            validate_task(task)
        if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
            raise ValueError("Timeout must be an integer from 1 to 600 seconds.")
        if not self.allow_execution:
            return GradleResult(task=task, summary="Execution disabled. Start the server with --allow-execution only for a trusted project.")
        try:
            command = wrapper_command(self.root, task, self.offline, discovery=discovery)
        except FileNotFoundError as exc:
            return GradleResult(task=task, summary=str(exc))
        started = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(*command, cwd=self.root,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                start_new_session=os.name != "nt")
        except OSError as exc:
            return GradleResult(task=task, summary=f"Cannot start the project wrapper: {exc.strerror}.")
        assert process.stdout is not None and process.stderr is not None
        readers = [asyncio.create_task(capture(process.stdout)), asyncio.create_task(capture(process.stderr))]
        combined = asyncio.gather(process.wait(), *readers)
        timed_out = False
        cleanup_confirmed = True
        try:
            await asyncio.wait_for(asyncio.shield(combined), timeout_seconds)
        except TimeoutError:
            timed_out = True
            cleanup_confirmed = await stop_tree(process)
            # Bound draining even if an escaped descendant still holds a pipe.
            try:
                await asyncio.wait_for(asyncio.shield(combined), 3)
            except TimeoutError:
                combined.cancel()
                await asyncio.gather(combined, return_exceptions=True)
        except asyncio.CancelledError:
            await stop_tree(process)
            combined.cancel()
            await asyncio.gather(combined, return_exceptions=True)
            raise
        values = [reader.result() if reader.done() and not reader.cancelled() else ("", True) for reader in readers]
        stdout, stderr = values[0][0], values[1][0]
        success = not timed_out and process.returncode == 0
        state = "timed_out" if timed_out else "completed" if success else "failed"
        diagnosis = analyze((stdout + "\n" + stderr)[-128000:]) if not success else None
        if success:
            summary = f"Gradle task {task} completed."
        elif timed_out:
            summary = f"Gradle task {task} exceeded {timeout_seconds}s; process cleanup was attempted. Startup is unverified."
        else:
            assert diagnosis is not None
            summary = f"Gradle task {task} failed (exit {process.returncode}). {diagnosis.likely_root_cause} Next: {diagnosis.next_step}"
        return GradleResult(task=task, success=success, exit_code=process.returncode, state=state,
            summary=summary, stdout=stdout, stderr=stderr, output_truncated=any(v[1] for v in values),
            elapsed_seconds=round(time.monotonic() - started, 3), diagnosis=diagnosis,
            warnings=([] if cleanup_confirmed else ["OS process-tree cleanup could not be confirmed; inspect remaining project processes."]) + ["Output redaction is best-effort; review before sharing.", "Project scripts and wrapper are trusted code, not OS-sandboxed. Gradle --offline does not prevent all wrapper/plugin network access."])

    async def run_gradle(self, task: str, timeout_seconds: int = 120) -> GradleResult:
        async with self.lock:
            return await self._execute(task, timeout_seconds)

    def _artifacts(self) -> dict[str, tuple[int, int]]:
        result = {}
        visited = 0
        # Bounded module walk; build directories are otherwise deliberately skipped by inspection.
        for base, dirs, _ in os.walk(self.root, followlinks=False):
            visited += 1
            if visited > 2000:
                break
            dirs[:] = sorted(d for d in dirs if d not in {".git", ".gradle", ".venv", "node_modules"}
                             and contained(self.root, Path(base) / d))
            rel = Path(base).relative_to(self.root)
            if len(rel.parts) > 6 or len(result) >= 200:
                dirs[:] = []
                continue
            if Path(base).name == "libs" and Path(base).parent.name == "build":
                for path in sorted(Path(base).glob("*.jar"))[:200]:
                    if contained(self.root, path) and path.is_file():
                        stat = path.stat()
                        result[str(path.relative_to(self.root))] = (stat.st_mtime_ns, stat.st_size)
                dirs[:] = []
            elif Path(base).name == "build":
                dirs[:] = [d for d in dirs if d == "libs"]
        return result

    async def build_project(self, timeout_seconds: int = 120) -> BuildResult:
        async with self.lock:
            before = self._artifacts()
            execution = await self._execute("build", timeout_seconds)
            after = self._artifacts()
            return BuildResult(execution=execution, artifacts=[
                Artifact(path=str(self.root / path), changed_during_build=before.get(path) != stamp)
                for path, stamp in after.items()])

    async def run_client(self, timeout_seconds: int = 120) -> ClientResult:
        async with self.lock:
            if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 600:
                raise ValueError("Timeout must be an integer from 1 to 600 seconds.")
            profile = inspect(self.root)
            if not profile.detection.fabric_detected:
                return ClientResult(execution=GradleResult(task="runClient",
                    summary="No Fabric/Loom markers found; development-client task is not yet plausible."))
            started = time.monotonic()
            discovery = await self._execute("tasks", min(timeout_seconds, 60), discovery=True)
            if not discovery.success:
                return ClientResult(execution=GradleResult(task="runClient",
                    summary="Client was not launched because Gradle task discovery failed or is disabled."),
                    discovery=discovery)
            tasks = sorted(set(re.findall(r"(?m)^\s*((?::?[A-Za-z0-9_-]+:)*runClient)\s+-", discovery.stdout)))
            if "runClient" in tasks:
                task = "runClient"
            elif len(tasks) == 1:
                task = tasks[0]
            else:
                return ClientResult(execution=GradleResult(task="runClient", state="task_missing",
                    summary="No unambiguous runClient task was listed by Gradle."),
                    discovery=discovery, startup_state="task_missing")
            remaining = int(timeout_seconds - (time.monotonic() - started))
            if remaining < 1:
                return ClientResult(execution=GradleResult(task=task, state="timed_out",
                    summary="Client was not launched: task discovery exhausted the timeout."), discovery=discovery)
            execution = await self._execute(task, remaining)
            state = "process_exited" if execution.success else "unverified_timeout" if execution.state == "timed_out" else "failed"
            return ClientResult(execution=execution, discovery=discovery, startup_state=state)
