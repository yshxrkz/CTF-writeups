"""Find writeups in the repository and parse their metadata.

A writeup is a ``README.md`` inside a platform folder (``TryHackMe/``,
``HackTheBox/``, ``PicoCTF/``), excluding the platform folder's own README.
Its metadata lives in the table under the title, e.g.::

    | **Platform**   | TryHackMe |
    | **Difficulty** | Easy      |
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from ctfw.errors import CtfwError

#: Platform display names. Each is also the name of its top-level folder.
PLATFORMS: tuple[str, ...] = ("TryHackMe", "HackTheBox", "PicoCTF")

WRITEUP_FILENAME = "README.md"

_FIELD_ROW = re.compile(r"^\|\s*\*\*(?P<key>[^*|]+?)\*\*\s*\|\s*(?P<value>.*?)\s*\|\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def platform_for(name: str) -> str:
    """Return the canonical platform name for ``name`` (case-insensitive).

    Raises:
        CtfwError: if ``name`` is not a known platform.
    """
    for platform in PLATFORMS:
        if platform.lower() == name.strip().lower():
            return platform
    raise CtfwError(f"unknown platform {name!r}; expected one of: {', '.join(PLATFORMS)}")


def iter_lines_outside_fences(lines: list[str]) -> Iterator[tuple[int, str]]:
    """Yield ``(line_number, line)`` for lines that are not inside a fenced code block.

    Line numbers are 1-based. Fence lines themselves are skipped.
    """
    fence: str | None = None
    for number, line in enumerate(lines, start=1):
        match = _FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
                continue
            if marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
                continue
        if fence is None:
            yield number, line


@dataclass(frozen=True)
class Writeup:
    """A parsed writeup.

    Attributes:
        path: Path relative to the repository root, e.g. ``TryHackMe/pickle-rick/README.md``.
        platform: Platform inferred from the top-level folder.
        title: Text of the first ``# `` heading (empty if there is none).
        fields: Metadata table values keyed by field name (``"Platform"``, ``"Date"``, ...).
        sections: ``## `` headings in document order.
        lines: Raw file lines, without trailing newlines.
    """

    path: Path
    platform: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)
    sections: tuple[str, ...] = ()
    lines: tuple[str, ...] = ()

    def get(self, key: str) -> str:
        """Return a metadata value, or ``""`` when the field is missing."""
        return self.fields.get(key, "")


def read_text(path: Path) -> str:
    """Read a UTF-8 text file, turning I/O and decoding failures into :class:`CtfwError`."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise CtfwError(f"{path}: not valid UTF-8 ({exc.reason})") from exc
    except OSError as exc:
        raise CtfwError(f"{path}: cannot read file ({exc.strerror})") from exc


def parse_writeup(path: Path, root: Path) -> Writeup:
    """Parse the writeup at ``path`` (absolute, or relative to the CWD).

    Args:
        path: The writeup's ``README.md``.
        root: Repository root; used to make ``Writeup.path`` relative and to
            infer the platform from the top-level folder.

    Raises:
        CtfwError: if the file cannot be read or is not under a platform folder.
    """
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise CtfwError(f"{path}: not inside repository root {root}") from exc
    platform = platform_for(relative.parts[0])

    lines = read_text(path).splitlines()
    title = ""
    fields: dict[str, str] = {}
    sections: list[str] = []
    in_header = True  # metadata only counts above the first "## " section

    for _, line in iter_lines_outside_fences(lines):
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("## "):
            sections.append(line[3:].strip())
            in_header = False
        elif in_header and (match := _FIELD_ROW.match(line)):
            fields.setdefault(match["key"].strip(), match["value"].strip())

    return Writeup(
        path=relative,
        platform=platform,
        title=title,
        fields=fields,
        sections=tuple(sections),
        lines=tuple(lines),
    )


def find_writeup_paths(root: Path) -> list[Path]:
    """Return the paths of every writeup under ``root``, sorted."""
    paths: list[Path] = []
    for platform in PLATFORMS:
        platform_dir = root / platform
        if not platform_dir.is_dir():
            continue
        for candidate in platform_dir.rglob(WRITEUP_FILENAME):
            if candidate.parent != platform_dir and candidate.is_file():
                paths.append(candidate)
    return sorted(paths)


def discover_writeups(root: Path) -> list[Writeup]:
    """Find and parse every writeup under ``root``."""
    return [parse_writeup(path, root) for path in find_writeup_paths(root)]
