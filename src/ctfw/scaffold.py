"""Create a new writeup from ``templates/writeup-template.md``.

Folder layout per platform::

    TryHackMe/<slug>/
    HackTheBox/Machines/<slug>/
    HackTheBox/Challenges/<category>/<slug>/
    PicoCTF/<year>/<category>/<slug>/

Every path component is reduced to ``[a-z0-9-]`` (or validated against it),
so user input can never escape the platform folder.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ctfw.checks import DIFFICULTIES
from ctfw.errors import CtfwError
from ctfw.writeup import platform_for, read_text

TEMPLATE_PATH = Path("templates") / "writeup-template.md"
HTB_KINDS = {"machine": "Machines", "challenge": "Challenges"}

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_YEAR = re.compile(r"^(?:\d{4}|practice)$")
_UNSAFE_VALUE = re.compile(r"[|\x00-\x1f\x7f]")


@dataclass(frozen=True)
class WriteupRequest:
    """What to scaffold. Only ``platform`` and ``name`` are required in general.

    Attributes:
        platform: ``TryHackMe``, ``HackTheBox`` or ``PicoCTF`` (any case).
        name: Display name, used as the title and (slugified) folder name.
        slug: Folder name override; must already be a valid slug.
        kind: HackTheBox only: ``machine`` or ``challenge``.
        category: Metadata category. Also the folder for HackTheBox
            challenges and PicoCTF, where it is required.
        year: PicoCTF only: event year or ``practice``; defaults to the year of ``date``.
        difficulty: One of :data:`ctfw.checks.DIFFICULTIES` (any case).
        link: ``https://`` URL of the room/machine/challenge.
        os: Target OS for the metadata table.
        date: Date solved; defaults to today.
    """

    platform: str
    name: str
    slug: str | None = None
    kind: str | None = None
    category: str | None = None
    year: str | None = None
    difficulty: str | None = None
    link: str | None = None
    os: str | None = None
    date: date | None = None


def slugify(text: str) -> str:
    """Turn ``text`` into a lowercase ASCII slug, e.g. ``"Pickle Rick!"`` → ``"pickle-rick"``.

    Raises:
        CtfwError: if nothing usable is left (e.g. the input was only punctuation).
    """
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        raise CtfwError(f"cannot make a folder name from {text!r}; pass --slug")
    return slug


def _clean_value(label: str, value: str) -> str:
    value = value.strip()
    if not value:
        raise CtfwError(f"{label} must not be empty")
    if _UNSAFE_VALUE.search(value):
        raise CtfwError(f"{label} must not contain '|' or control characters")
    return value


def _normalize_difficulty(value: str) -> str:
    for difficulty in DIFFICULTIES:
        if difficulty.lower() == value.strip().lower():
            return difficulty
    raise CtfwError(f"difficulty must be one of: {', '.join(DIFFICULTIES)}")


def target_dir(root: Path, request: WriteupRequest) -> Path:
    """Return the folder the writeup should be created in (not created yet).

    Raises:
        CtfwError: for missing platform-specific options or invalid names.
    """
    platform = platform_for(request.platform)
    if request.slug is not None:
        if not _SLUG.match(request.slug):
            raise CtfwError(f"slug {request.slug!r} must match {_SLUG.pattern}")
        slug = request.slug
    else:
        slug = slugify(request.name)

    if platform == "TryHackMe":
        parts = [slug]
    elif platform == "HackTheBox":
        kind = (request.kind or "").lower()
        if kind not in HTB_KINDS:
            raise CtfwError("HackTheBox writeups need --kind machine or --kind challenge")
        if kind == "machine":
            parts = [HTB_KINDS[kind], slug]
        else:
            if not request.category:
                raise CtfwError("HackTheBox challenges need --category (e.g. web, crypto)")
            parts = [HTB_KINDS[kind], slugify(request.category), slug]
    else:  # PicoCTF
        year = request.year or str((request.date or date.today()).year)
        if not _YEAR.match(year):
            raise CtfwError(f"year {year!r} must be four digits or 'practice'")
        if not request.category:
            raise CtfwError("PicoCTF writeups need --category (e.g. web, crypto, forensics)")
        parts = [year, slugify(request.category), slug]

    platform_root = (root / platform).resolve()
    directory = platform_root.joinpath(*parts).resolve()
    if not directory.is_relative_to(platform_root):  # defence in depth
        raise CtfwError(f"refusing to create a writeup outside {platform}/")
    return directory


def _set_field(text: str, key: str, value: str) -> str:
    """Replace the value cell of the ``**key**`` metadata row, keeping column width."""
    pattern = re.compile(rf"^(\|\s*\*\*{re.escape(key)}\*\*\s*\|)([^|\n]*)(\|)\s*$", re.MULTILINE)

    def replace(match: re.Match[str]) -> str:
        width = max(len(match[2]) - 2, len(value))
        return f"{match[1]} {value.ljust(width)} {match[3]}"

    updated, count = pattern.subn(replace, text, count=1)
    if count != 1:
        raise CtfwError(f"template has no '**{key}**' metadata row")
    return updated


def render_template(template: str, request: WriteupRequest) -> str:
    """Fill ``template`` with the values from ``request``.

    Fields that weren't provided keep their placeholder, so ``ctfw lint``
    keeps flagging them until they are filled in.
    """
    name = _clean_value("name", request.name)
    lines = template.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines[index] = f"# {name}\n"
            break
    else:
        raise CtfwError("template has no '# ' title line")
    text = "".join(lines)

    text = _set_field(text, "Platform", platform_for(request.platform))
    text = _set_field(text, "Date", (request.date or date.today()).isoformat())
    if request.difficulty:
        text = _set_field(text, "Difficulty", _normalize_difficulty(request.difficulty))
    if request.category:
        text = _set_field(text, "Category", _clean_value("category", request.category))
    if request.os:
        text = _set_field(text, "OS", _clean_value("os", request.os))
    if request.link:
        link = _clean_value("link", request.link)
        if not link.startswith("https://"):
            raise CtfwError("link must start with https://")
        text = _set_field(text, "Link", link)
    return text


def create_writeup(root: Path, request: WriteupRequest) -> Path:
    """Create the writeup folder, its ``README.md`` and an ``images/`` folder.

    Returns:
        Path to the new ``README.md``.

    Raises:
        CtfwError: if the writeup already exists, the template is missing, or
            the request is invalid.
    """
    template_path = root / TEMPLATE_PATH
    if not template_path.is_file():
        raise CtfwError(f"template not found at {template_path}")
    text = render_template(read_text(template_path), request)
    directory = target_dir(root, request)

    readme = directory / "README.md"
    try:
        (directory / "images").mkdir(parents=True, exist_ok=True)
        with readme.open("x", encoding="utf-8") as handle:  # "x": never overwrite
            handle.write(text)
        (directory / "images" / ".gitkeep").touch()
    except FileExistsError as exc:
        raise CtfwError(f"{readme} already exists") from exc
    except OSError as exc:
        raise CtfwError(f"cannot create {readme} ({exc.strerror})") from exc
    return readme
