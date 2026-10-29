"""Build the README index table from writeup metadata.

The table lives between two marker comments in the root ``README.md``::

    <!-- index:start -->
    | Platform | Name | ... |
    <!-- index:end -->

Everything between the markers is regenerated; everything else is untouched.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from ctfw.errors import CtfwError
from ctfw.writeup import Writeup, read_text

START_MARKER = "<!-- index:start -->"
END_MARKER = "<!-- index:end -->"
EMPTY_INDEX = "_No writeups yet._"

_HEADERS = ("Platform", "Name", "Difficulty", "Category", "Date")


def _cell(value: str) -> str:
    """Make ``value`` safe to place in a Markdown table cell."""
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()


def _link_target(path: Path) -> str:
    """Return a Markdown link target for ``path`` (spaces percent-encoded)."""
    return path.as_posix().replace(" ", "%20")


def render_index(writeups: Sequence[Writeup]) -> str:
    """Render the index as an aligned Markdown table.

    Rows are ordered newest first; writeups with the same date are ordered by
    platform, then title.
    """
    if not writeups:
        return EMPTY_INDEX

    ordered = sorted(writeups, key=lambda w: (w.platform, w.title.lower()))
    ordered.sort(key=lambda w: w.get("Date"), reverse=True)  # stable sort keeps the tie order

    rows = [
        (
            _cell(w.platform),
            f"[{_cell(w.title or w.path.parent.name)}]({_link_target(w.path)})",
            _cell(w.get("Difficulty")),
            _cell(w.get("Category")),
            _cell(w.get("Date")),
        )
        for w in ordered
    ]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(_HEADERS)]

    def line(cells: Sequence[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths, strict=True)) + " |"

    separator = "| " + " | ".join("-" * w for w in widths) + " |"
    return "\n".join([line(_HEADERS), separator, *(line(r) for r in rows)])


def _marker_line(marker: str) -> re.Pattern[str]:
    return re.compile(rf"^[ \t]*{re.escape(marker)}[ \t]*$", re.MULTILINE)


_START_LINE = _marker_line(START_MARKER)
_END_LINE = _marker_line(END_MARKER)


def replace_index(readme: str, table: str) -> str:
    """Return ``readme`` with the text between the index markers replaced by ``table``.

    Each marker must be on a line of its own, so the README can mention the
    markers in prose or inline code without confusing the generator.

    Raises:
        CtfwError: if the markers are missing, duplicated, or out of order.
    """
    starts = list(_START_LINE.finditer(readme))
    ends = list(_END_LINE.finditer(readme))
    if len(starts) != 1 or len(ends) != 1:
        raise CtfwError(
            f"README must contain exactly one {START_MARKER} and one {END_MARKER} marker, "
            "each on its own line"
        )
    start, end = starts[0].end(), ends[0].start()
    if end < start:
        raise CtfwError(f"{END_MARKER} appears before {START_MARKER} in README")
    return f"{readme[:start]}\n{table}\n{readme[end:]}"


def update_readme(readme_path: Path, writeups: Sequence[Writeup], *, check: bool = False) -> bool:
    """Regenerate the index in ``readme_path``.

    Args:
        readme_path: The root ``README.md``.
        writeups: Writeups to list.
        check: If true, only report whether the file is up to date; never write.

    Returns:
        ``True`` if the README already matched (nothing to change), else ``False``.
        In write mode a ``False`` return means the file was updated.

    Raises:
        CtfwError: if the README cannot be read/written or has bad markers.
    """
    current = read_text(readme_path)
    updated = replace_index(current, render_index(writeups))
    if updated == current:
        return True
    if not check:
        try:
            readme_path.write_text(updated, encoding="utf-8")
        except OSError as exc:
            raise CtfwError(f"{readme_path}: cannot write file ({exc.strerror})") from exc
    return False
