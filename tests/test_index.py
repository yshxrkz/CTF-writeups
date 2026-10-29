from __future__ import annotations

from pathlib import Path

import pytest

from conftest import WriteFile, writeup_text
from ctfw.errors import CtfwError
from ctfw.index import (
    EMPTY_INDEX,
    END_MARKER,
    START_MARKER,
    render_index,
    replace_index,
    update_readme,
)
from ctfw.writeup import Writeup, discover_writeups


def _writeup(title: str, date: str, platform: str = "TryHackMe", **fields: str) -> Writeup:
    return Writeup(
        path=Path(platform) / title.lower().replace(" ", "-") / "README.md",
        platform=platform,
        title=title,
        fields={"Date": date, "Difficulty": "Easy", "Category": "Web", **fields},
    )


def test_render_index_orders_newest_first_then_platform_then_title() -> None:
    table = render_index(
        [
            _writeup("Old", "2025-01-01"),
            _writeup("beta", "2026-02-01"),
            _writeup("Alpha", "2026-02-01"),
            _writeup("Lame", "2026-02-01", platform="HackTheBox"),
        ]
    )
    names = [line.split("|")[2].strip() for line in table.splitlines()[2:]]
    assert names == [
        "[Lame](HackTheBox/lame/README.md)",
        "[Alpha](TryHackMe/alpha/README.md)",
        "[beta](TryHackMe/beta/README.md)",
        "[Old](TryHackMe/old/README.md)",
    ]


def test_render_index_aligns_columns() -> None:
    lines = render_index([_writeup("A Much Longer Room Name", "2026-01-01")]).splitlines()
    assert len({len(line) for line in lines}) == 1
    assert lines[0].startswith("| Platform  | Name ")
    assert set(lines[1]) <= {"|", "-", " "}


def test_render_index_escapes_pipes_and_encodes_spaces_in_links() -> None:
    writeup = Writeup(
        path=Path("TryHackMe/two words/README.md"),
        platform="TryHackMe",
        title="A | B",
        fields={"Category": "Web | Linux"},
    )
    row = render_index([writeup]).splitlines()[2]
    assert "[A \\| B](TryHackMe/two%20words/README.md)" in row
    assert "Web \\| Linux" in row


def test_render_index_falls_back_to_folder_name_without_title() -> None:
    writeup = Writeup(path=Path("TryHackMe/untitled/README.md"), platform="TryHackMe", title="")
    assert "[untitled](TryHackMe/untitled/README.md)" in render_index([writeup])


def test_render_index_with_no_writeups() -> None:
    assert render_index([]) == EMPTY_INDEX


def test_replace_index_only_touches_text_between_markers() -> None:
    readme = f"before\n{START_MARKER}\nold table\n{END_MARKER}\nafter\n"
    assert replace_index(readme, "NEW") == f"before\n{START_MARKER}\nNEW\n{END_MARKER}\nafter\n"


@pytest.mark.parametrize(
    "readme",
    [
        "no markers",
        f"{START_MARKER} only start",
        f"{START_MARKER}{START_MARKER}{END_MARKER}",
        f"{END_MARKER} reversed {START_MARKER}",
    ],
)
def test_replace_index_rejects_bad_markers(readme: str) -> None:
    with pytest.raises(CtfwError):
        replace_index(readme, "table")


def test_update_readme_writes_then_reports_up_to_date(repo: Path, write: WriteFile) -> None:
    write("TryHackMe/example/README.md", writeup_text("Example Room"))
    readme = repo / "README.md"
    writeups = discover_writeups(repo)

    assert update_readme(readme, writeups, check=True) is False  # stale
    assert START_MARKER + "\n" + END_MARKER in readme.read_text(encoding="utf-8")  # untouched

    assert update_readme(readme, writeups) is False  # rewritten
    assert "[Example Room](TryHackMe/example/README.md)" in readme.read_text(encoding="utf-8")

    assert update_readme(readme, writeups, check=True) is True
