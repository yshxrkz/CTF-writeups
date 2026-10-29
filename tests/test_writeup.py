from __future__ import annotations

from pathlib import Path

import pytest

from conftest import WriteFile, writeup_text
from ctfw.errors import CtfwError
from ctfw.writeup import (
    discover_writeups,
    find_writeup_paths,
    iter_lines_outside_fences,
    parse_writeup,
    platform_for,
)


def test_platform_for_is_case_insensitive() -> None:
    assert platform_for("tryhackme") == "TryHackMe"
    assert platform_for(" HACKTHEBOX ") == "HackTheBox"


def test_platform_for_rejects_unknown_platform() -> None:
    with pytest.raises(CtfwError, match="unknown platform"):
        platform_for("vulnhub")


def test_parse_writeup_reads_title_fields_and_sections(repo: Path, write: WriteFile) -> None:
    path = write("TryHackMe/example/README.md", writeup_text("Example Room"))

    writeup = parse_writeup(path, repo)

    assert writeup.path == Path("TryHackMe/example/README.md")
    assert writeup.platform == "TryHackMe"
    assert writeup.title == "Example Room"
    assert writeup.get("Difficulty") == "Easy"
    assert writeup.get("Date") == "2026-01-15"
    assert writeup.get("Missing") == ""
    assert writeup.sections == (
        "Summary",
        "Tools",
        "Enumeration",
        "Exploitation",
        "Flags",
        "Lessons Learned",
    )


def test_parse_writeup_ignores_headings_and_fields_inside_code_fences(
    repo: Path, write: WriteFile
) -> None:
    text = """\
# Real Title

```markdown
# Fake Title
| **Platform** | Fake |
## Fake Section
```

| **Platform** | TryHackMe |

## Real Section

| **Difficulty** | Hard |
"""
    writeup = parse_writeup(write("TryHackMe/x/README.md", text), repo)

    assert writeup.title == "Real Title"
    assert writeup.sections == ("Real Section",)
    # Metadata only counts above the first section.
    assert writeup.fields == {"Platform": "TryHackMe"}


def test_iter_lines_outside_fences_handles_tilde_and_longer_fences() -> None:
    lines = ["a", "~~~", "b", "~~~", "c", "````", "```", "d", "````", "e"]
    assert [line for _, line in iter_lines_outside_fences(lines)] == ["a", "c", "e"]


def test_parse_writeup_rejects_invalid_utf8(repo: Path) -> None:
    path = repo / "TryHackMe" / "bad" / "README.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"# Title\n\xff\xfe")

    with pytest.raises(CtfwError, match="not valid UTF-8"):
        parse_writeup(path, repo)


def test_parse_writeup_rejects_file_outside_root(
    repo: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    outside = tmp_path_factory.mktemp("elsewhere") / "README.md"
    outside.write_text("# x\n", encoding="utf-8")

    with pytest.raises(CtfwError, match="not inside repository root"):
        parse_writeup(outside, repo)


def test_find_writeup_paths_covers_nested_layouts_and_skips_platform_readmes(
    repo: Path, write: WriteFile
) -> None:
    write("TryHackMe/README.md", "# TryHackMe\n")
    write("TryHackMe/room/README.md", writeup_text())
    write("HackTheBox/Machines/lame/README.md", writeup_text(platform="HackTheBox"))
    write("HackTheBox/Challenges/web/templated/README.md", writeup_text(platform="HackTheBox"))
    write("PicoCTF/2024/web/cookies/README.md", writeup_text(platform="PicoCTF"))
    write("templates/README.md", "# not a writeup\n")
    write("TryHackMe/room/notes.md", "# not a writeup either\n")

    found = [p.relative_to(repo).as_posix() for p in find_writeup_paths(repo)]

    assert found == [
        "HackTheBox/Challenges/web/templated/README.md",
        "HackTheBox/Machines/lame/README.md",
        "PicoCTF/2024/web/cookies/README.md",
        "TryHackMe/room/README.md",
    ]


def test_discover_writeups_on_empty_repo_returns_nothing(repo: Path) -> None:
    assert discover_writeups(repo) == []
