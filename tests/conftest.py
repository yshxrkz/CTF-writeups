"""Shared fixtures: build small throwaway writeup repositories under tmp_path."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = PROJECT_ROOT / "templates" / "writeup-template.md"

README = """\
# CTF Writeups

## Index

<!-- index:start -->
<!-- index:end -->
"""


def writeup_text(
    title: str = "Example Room",
    *,
    platform: str = "TryHackMe",
    link: str = "https://tryhackme.com/room/example",
    difficulty: str = "Easy",
    category: str = "Web",
    date: str = "2026-01-15",
    flag_value: str = "`REDACTED`",
    extra: str = "",
) -> str:
    """Return the text of a writeup that passes every lint check by default."""
    return f"""\
# {title}

| Field          | Value |
| -------------- | ----- |
| **Platform**   | {platform} |
| **Link**       | {link} |
| **Difficulty** | {difficulty} |
| **Category**   | {category} |
| **Date**       | {date} |

## Summary

Short summary.

## Tools

nmap.

## Enumeration

Scanned it.

## Exploitation

Exploited it.

## Flags

| Flag   | Location   | Value |
| ------ | ---------- | ----- |
| User   | `/home/u`  | {flag_value} |

## Lessons Learned

Learned things.
{extra}"""


WriteFile = Callable[[str, str], Path]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repository: README with index markers and the real template."""
    (tmp_path / "README.md").write_text(README, encoding="utf-8")
    (tmp_path / "templates").mkdir()
    shutil.copy(TEMPLATE, tmp_path / "templates" / "writeup-template.md")
    return tmp_path


@pytest.fixture
def write(repo: Path) -> WriteFile:
    """Write ``text`` to ``relative`` inside ``repo``, creating parent folders."""

    def _write(relative: str, text: str) -> Path:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return _write
