"""Validate repository-local Markdown links without making network requests."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
SKIP_DIRS = {"build", "dist"}


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part.startswith(".") or part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    )


def local_target(raw_target: str) -> str | None:
    target = raw_target.strip().strip("<>").split(" ", 1)[0]
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    return unquote(parsed.path)


def main() -> int:
    failures: list[str] = []
    checked = 0
    for document in markdown_files():
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK.findall(text):
            target = local_target(raw_target)
            if target is None:
                continue
            checked += 1
            resolved = ROOT / target.lstrip("/") if target.startswith("/") else document.parent / target
            if not resolved.exists():
                failures.append(f"{document.relative_to(ROOT)} -> {raw_target}")
    if failures:
        print("Broken local Markdown links:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print(f"Checked {checked} local Markdown links across {len(markdown_files())} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
