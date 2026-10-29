"""Lint checks for writeups and the rest of the repository.

Each check returns a list of :class:`Issue`. :func:`run_checks` runs them all.

Issue codes:

========  ==============================================================
META001   required metadata field is missing
META002   template placeholder was left in (title or metadata value)
META003   ``Platform`` field doesn't match the folder the writeup is in
META004   ``Date`` is not a valid ``YYYY-MM-DD`` date
META005   ``Difficulty`` is not one of :data:`DIFFICULTIES`
META006   ``Link`` is not an ``https://`` URL
SECT001   required ``## `` section is missing
LEAK001   flag-format string (``THM{...}``, ``HTB{...}``, ...) that isn't redacted
LEAK002   value in the Flags table isn't ``REDACTED``
LEAK003   32-character hex string (HackTheBox flag format, or an MD5/NTLM hash)
LINK001   relative link or image points to a file that doesn't exist
LINK002   relative link points outside the repository
FILE001   text file isn't valid UTF-8, so it couldn't be scanned
========  ==============================================================

Add ``ctfw: allow-leak`` anywhere on a line (e.g. in an HTML comment) to
skip the LEAK checks for that line.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from ctfw.writeup import PLATFORMS, Writeup, discover_writeups, iter_lines_outside_fences

REQUIRED_FIELDS: tuple[str, ...] = ("Platform", "Link", "Difficulty", "Category", "Date")
REQUIRED_SECTIONS: tuple[str, ...] = (
    "Summary",
    "Tools",
    "Enumeration",
    "Exploitation",
    "Flags",
    "Lessons Learned",
)
DIFFICULTIES: tuple[str, ...] = ("Very Easy", "Easy", "Medium", "Hard", "Insane")

ALLOW_LEAK_MARKER = "ctfw: allow-leak"
REDACTED = "REDACTED"

#: Folders never scanned (besides any folder whose name starts with ".").
SKIP_DIRS = frozenset({"node_modules", "venv", "__pycache__", "build", "dist", "htmlcov"})
#: Outside the platform folders only these file types are scanned. Inside them,
#: every text file is scanned (exploit scripts and notes can leak flags too).
DOC_SUFFIXES = frozenset({".md", ".txt"})
MAX_SCAN_BYTES = 2_000_000

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FIELD_ROW = re.compile(r"^\|\s*\*\*(?P<key>[^*|]+?)\*\*\s*\|")
_FLAG = re.compile(r"\b(?P<prefix>THM|HTB|picoCTF|flag|CTF)\{(?P<inner>[^{}\n]*)\}", re.IGNORECASE)
_HEX32 = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{32}(?![0-9A-Za-z])")
_INLINE_CODE = re.compile(r"(`+).*?\1")
_INLINE_LINK = re.compile(r"\]\(\s*<?(?P<target>[^)\s>]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
_REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(?P<target>[^\s>]+)>?")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_TABLE_SEPARATOR = re.compile(r"^\|?[\s:|-]+\|?$")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")


@dataclass(frozen=True, order=True)
class Issue:
    """A single lint finding.

    Attributes:
        path: File path relative to the repository root.
        line: 1-based line number, or 0 when the issue concerns the whole file.
        code: Stable identifier such as ``LEAK001`` (see module docstring).
        message: Human-readable explanation.
    """

    path: Path
    line: int
    code: str
    message: str

    def format(self) -> str:
        """Format as ``path:line: CODE message`` (editor/CI friendly)."""
        location = self.path.as_posix() + (f":{self.line}" if self.line else "")
        return f"{location}: {self.code} {self.message}"

    def format_github(self) -> str:
        """Format as a GitHub Actions workflow command (shows inline on PRs)."""
        line = f",line={self.line}" if self.line else ""
        message = self.message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        return f"::error file={self.path.as_posix()}{line},title={self.code}::{message}"


# --------------------------------------------------------------------------- metadata


def _field_line(writeup: Writeup, key: str) -> int:
    for number, line in enumerate(writeup.lines, start=1):
        match = _FIELD_ROW.match(line)
        if match and match["key"].strip() == key:
            return number
    return 0


def _is_placeholder(value: str) -> bool:
    """Return true for values copied unchanged from the template."""
    stripped = value.strip()
    return (
        ("<" in stripped and ">" in stripped)
        or stripped.lower().startswith("e.g.")
        or stripped.upper() == "YYYY-MM-DD"
    )


def check_metadata(writeup: Writeup) -> list[Issue]:
    """Check the title and metadata table of ``writeup``."""
    issues: list[Issue] = []

    def add(line: int, code: str, message: str) -> None:
        issues.append(Issue(writeup.path, line, code, message))

    if not writeup.title or _is_placeholder(writeup.title):
        add(1, "META002", "title is missing or still the template placeholder")

    for key in REQUIRED_FIELDS:
        value = writeup.get(key)
        line = _field_line(writeup, key)
        if not value:
            add(line, "META001", f"missing required metadata field '{key}'")
        elif _is_placeholder(value):
            add(line, "META002", f"'{key}' still has the template placeholder {value!r}")
        elif key == "Platform" and value != writeup.platform:
            add(line, "META003", f"Platform is {value!r} but the writeup is in {writeup.platform}/")
        elif key == "Date" and not _valid_date(value):
            add(line, "META004", f"Date {value!r} is not a valid YYYY-MM-DD date")
        elif key == "Difficulty" and value not in DIFFICULTIES:
            add(line, "META005", f"Difficulty {value!r} is not one of: {', '.join(DIFFICULTIES)}")
        elif key == "Link" and not value.startswith("https://"):
            add(line, "META006", f"Link {value!r} should be an https:// URL")
    return issues


def _valid_date(value: str) -> bool:
    if not _ISO_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def check_sections(writeup: Writeup) -> list[Issue]:
    """Check that ``writeup`` has every section in :data:`REQUIRED_SECTIONS`."""
    present = {section.lower() for section in writeup.sections}
    return [
        Issue(writeup.path, 0, "SECT001", f"missing required section '## {section}'")
        for section in REQUIRED_SECTIONS
        if section.lower() not in present
    ]


# --------------------------------------------------------------------------- leaks


def _split_row(line: str) -> list[str]:
    inner = line.strip()
    inner = inner.removeprefix("|").removesuffix("|")
    return [cell.strip() for cell in _CELL_SPLIT.split(inner)]


def check_flags_table(writeup: Writeup) -> list[Issue]:
    """Check that every value in the ``## Flags`` table is ``REDACTED`` (or empty).

    The value column is the one headed ``Value``; if there is no such header,
    the last column is used.
    """
    issues: list[Issue] = []
    in_flags = False
    header: list[str] | None = None
    value_index = -1

    for number, line in iter_lines_outside_fences(list(writeup.lines)):
        if line.startswith("## "):
            in_flags = line[3:].strip().lower() == "flags"
            header = None
            continue
        if not in_flags:
            continue
        if not line.lstrip().startswith("|"):
            header = None  # any non-table line ends the current table
            continue
        if ALLOW_LEAK_MARKER in line:
            continue
        cells = _split_row(line)
        if header is None:
            header = [cell.lower() for cell in cells]
            value_index = header.index("value") if "value" in header else -1
            continue
        if _TABLE_SEPARATOR.match(line.strip()):
            continue
        value = cells[value_index] if -len(cells) <= value_index < len(cells) else ""
        value = value.strip("` *_")
        if value and value.upper() != REDACTED:
            issues.append(
                Issue(
                    writeup.path,
                    number,
                    "LEAK002",
                    f"Flags table value is not {REDACTED}; replace it before publishing",
                )
            )
    return issues


def _flag_is_redacted(inner: str) -> bool:
    stripped = inner.strip()
    return (
        stripped in {"", "...", "…"}
        or REDACTED in stripped.upper()
        or (stripped.startswith("<") and stripped.endswith(">"))
        or set(stripped) <= set(".xX*_-")
    )


def scan_leaks(path: Path, lines: Sequence[str]) -> list[Issue]:
    """Scan every line of a file (code blocks included) for unredacted secrets.

    Matched secrets are never echoed back, so CI logs don't re-leak them.
    """
    issues: list[Issue] = []
    for number, line in enumerate(lines, start=1):
        if ALLOW_LEAK_MARKER in line:
            continue
        for match in _FLAG.finditer(line):
            if not _flag_is_redacted(match["inner"]):
                issues.append(
                    Issue(
                        path,
                        number,
                        "LEAK001",
                        f"possible unredacted flag {match['prefix']}{{…}}; "
                        f"replace the value with {REDACTED}",
                    )
                )
        if _HEX32.search(line):
            issues.append(
                Issue(
                    path,
                    number,
                    "LEAK003",
                    "32-character hex string looks like a HackTheBox flag or a password "
                    f"hash; redact it or add '{ALLOW_LEAK_MARKER}' if it is safe",
                )
            )
    return issues


# --------------------------------------------------------------------------- links


def _link_targets(lines: Sequence[str]) -> Iterator[tuple[int, str]]:
    for number, line in iter_lines_outside_fences(list(lines)):
        text = _INLINE_CODE.sub("", line)
        for match in _INLINE_LINK.finditer(text):
            yield number, match["target"]
        reference = _REFERENCE_LINK.match(text)
        if reference:
            yield number, reference["target"]


def check_links(path: Path, lines: Sequence[str], root: Path) -> list[Issue]:
    """Check that relative links and images in a Markdown file resolve.

    External URLs (``https:``, ``mailto:``, ...) and in-page anchors are skipped.
    A leading ``/`` is resolved from the repository root, as GitHub does.
    """
    issues: list[Issue] = []
    resolved_root = root.resolve()
    for number, target in _link_targets(lines):
        if target.startswith("#") or _URL_SCHEME.match(target):
            continue
        relative = unquote(target.split("#", 1)[0].split("?", 1)[0])
        if not relative:
            continue
        base = resolved_root if relative.startswith("/") else (root / path).resolve().parent
        resolved = (base / relative.lstrip("/")).resolve()
        if not resolved.is_relative_to(resolved_root):
            issues.append(
                Issue(path, number, "LINK002", f"link {target!r} points outside the repository")
            )
        elif not resolved.exists():
            issues.append(Issue(path, number, "LINK001", f"broken link {target!r}"))
    return issues


# --------------------------------------------------------------------------- runner


def _skip_dir(name: str) -> bool:
    return name.startswith(".") or name in SKIP_DIRS or name.endswith(".egg-info")


def iter_scan_targets(root: Path) -> Iterator[Path]:
    """Yield files to scan: every file in platform folders, plus docs elsewhere.

    Hidden folders (``.git``, ``.venv``, ...), :data:`SKIP_DIRS`, and ``*.egg-info``
    build folders are pruned.
    """
    platform_dirs = {root / platform for platform in PLATFORMS}
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(d))
        in_platform = any(current.is_relative_to(p) for p in platform_dirs)
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = current / name
            if in_platform or path.suffix.lower() in DOC_SUFFIXES:
                yield path


def _read_for_scan(path: Path) -> tuple[list[str] | None, bool]:
    """Return ``(lines, decode_failed)``; ``lines`` is None for binary or huge files."""
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_SCAN_BYTES + 1)
    except OSError:
        return None, False
    if len(data) > MAX_SCAN_BYTES or b"\0" in data[:8192]:
        return None, False
    try:
        return data.decode("utf-8").splitlines(), False
    except UnicodeDecodeError:
        return None, True


def run_checks(root: Path) -> list[Issue]:
    """Run every check against the repository at ``root``; return sorted issues."""
    root = root.resolve()
    issues: list[Issue] = []
    for writeup in discover_writeups(root):
        issues += check_metadata(writeup)
        issues += check_sections(writeup)
        issues += check_flags_table(writeup)

    for path in iter_scan_targets(root):
        relative = path.relative_to(root)
        lines, decode_failed = _read_for_scan(path)
        if decode_failed:
            issues.append(
                Issue(relative, 0, "FILE001", "not valid UTF-8 text; could not scan for leaks")
            )
        if lines is None:
            continue
        issues += scan_leaks(relative, lines)
        if path.suffix.lower() == ".md":
            issues += check_links(relative, lines, root)

    return sorted(set(issues))
