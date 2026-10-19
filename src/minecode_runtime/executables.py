"""Safe executable resolution for subprocess boundaries."""
from collections.abc import Iterable, Mapping
import os
from pathlib import Path


def _environment_value(environment: Mapping[str, str], name: str) -> str | None:
    for key, value in environment.items():
        if key.casefold() == name.casefold():
            return value
    return None


def _usable_executable(path: Path) -> str | None:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_file() or (os.name != "nt" and not os.access(resolved, os.X_OK)):
        return None
    return str(resolved)


def resolve_executable(
    command: str,
    *,
    env: Mapping[str, str] | None = None,
    blocked_dirs: Iterable[str | os.PathLike[str] | None] = (),
) -> str | None:
    """Resolve a configured executable without consulting the working directory."""
    configured = Path(command)
    if configured.is_absolute():
        return _usable_executable(configured)
    if configured.name != command:
        return None

    blocked = {Path(directory).resolve() for directory in blocked_dirs if directory is not None}
    environment = os.environ if env is None else env
    path_value = _environment_value(environment, "PATH")
    path_entries = (path_value if path_value is not None else os.defpath).split(os.pathsep)
    names = [command]
    if os.name == "nt" and not configured.suffix:
        pathext = _environment_value(environment, "PATHEXT") or ".COM;.EXE;.BAT;.CMD"
        names = [command + extension for extension in pathext.split(os.pathsep) if extension]

    for entry in path_entries:
        directory = Path(entry.strip('"'))
        if not entry or not directory.is_absolute():
            continue
        try:
            directory = directory.resolve()
        except OSError:
            continue
        if directory in blocked:
            continue
        for name in names:
            resolved = _usable_executable(directory / name)
            if resolved is not None:
                return resolved
    return None
