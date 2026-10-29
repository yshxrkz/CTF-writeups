from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ctfw.checks import run_checks
from ctfw.errors import CtfwError
from ctfw.scaffold import (
    WriteupRequest,
    create_writeup,
    render_template,
    slugify,
    target_dir,
)
from ctfw.writeup import parse_writeup

SOLVED = date(2026, 3, 14)


@pytest.mark.parametrize(
    ("text", "slug"),
    [
        ("Pickle Rick", "pickle-rick"),
        ("  Mr. Robot CTF!! ", "mr-robot-ctf"),
        ("Café Ünïcode", "cafe-unicode"),
        ("../../etc/passwd", "etc-passwd"),
        ("Blue_2", "blue-2"),
    ],
)
def test_slugify(text: str, slug: str) -> None:
    assert slugify(text) == slug


def test_slugify_rejects_input_with_nothing_usable() -> None:
    with pytest.raises(CtfwError, match="pass --slug"):
        slugify("!!!")


@pytest.mark.parametrize(
    ("request_", "expected"),
    [
        (WriteupRequest("tryhackme", "Pickle Rick"), "TryHackMe/pickle-rick"),
        (WriteupRequest("HackTheBox", "Lame", kind="machine"), "HackTheBox/Machines/lame"),
        (
            WriteupRequest("HackTheBox", "Templated", kind="Challenge", category="Web"),
            "HackTheBox/Challenges/web/templated",
        ),
        (
            WriteupRequest("PicoCTF", "Obedient Cat", category="General Skills", year="2021"),
            "PicoCTF/2021/general-skills/obedient-cat",
        ),
        (
            WriteupRequest("PicoCTF", "Cookies", category="web", date=SOLVED),
            "PicoCTF/2026/web/cookies",
        ),
        (WriteupRequest("TryHackMe", "Anything", slug="custom-slug"), "TryHackMe/custom-slug"),
    ],
)
def test_target_dir_follows_platform_layout(
    repo: Path, request_: WriteupRequest, expected: str
) -> None:
    assert target_dir(repo, request_) == (repo / expected).resolve()


@pytest.mark.parametrize(
    ("request_", "message"),
    [
        (WriteupRequest("HackTheBox", "Lame"), "--kind"),
        (WriteupRequest("HackTheBox", "X", kind="challenge"), "--category"),
        (WriteupRequest("PicoCTF", "X"), "--category"),
        (WriteupRequest("PicoCTF", "X", category="web", year="21"), "four digits"),
        (WriteupRequest("PicoCTF", "X", category="web", year="../.."), "four digits"),
        (WriteupRequest("TryHackMe", "X", slug="../escape"), "must match"),
        (WriteupRequest("TryHackMe", "X", slug="Upper"), "must match"),
        (WriteupRequest("VulnHub", "X"), "unknown platform"),
    ],
)
def test_target_dir_rejects_invalid_requests(
    repo: Path, request_: WriteupRequest, message: str
) -> None:
    with pytest.raises(CtfwError, match=message):
        target_dir(repo, request_)


def test_render_template_fills_given_fields_and_keeps_placeholders(repo: Path) -> None:
    template = (repo / "templates" / "writeup-template.md").read_text(encoding="utf-8")
    text = render_template(
        template, WriteupRequest("tryhackme", "Blue", difficulty="easy", date=SOLVED)
    )
    assert text.startswith("# Blue\n")
    assert "| **Platform**   | TryHackMe " in text
    assert "| **Difficulty** | Easy " in text
    assert "| **Date**       | 2026-03-14 " in text
    assert "<URL to the room, machine, or challenge>" in text  # link not given


@pytest.mark.parametrize(
    ("request_", "message"),
    [
        (WriteupRequest("TryHackMe", "  "), "name must not be empty"),
        (WriteupRequest("TryHackMe", "two\nlines"), "control characters"),
        (WriteupRequest("TryHackMe", "Blue", category="Web | Linux"), "'|'"),
        (WriteupRequest("TryHackMe", "Blue", difficulty="trivial"), "difficulty must be one of"),
        (WriteupRequest("TryHackMe", "Blue", link="http://insecure.example"), "https://"),
    ],
)
def test_render_template_rejects_unsafe_values(
    repo: Path, request_: WriteupRequest, message: str
) -> None:
    template = (repo / "templates" / "writeup-template.md").read_text(encoding="utf-8")
    with pytest.raises(CtfwError, match=message):
        render_template(template, request_)


def test_render_template_requires_title_and_field_rows() -> None:
    with pytest.raises(CtfwError, match="title"):
        render_template("no title\n", WriteupRequest("TryHackMe", "X"))
    with pytest.raises(CtfwError, match="Platform"):
        render_template("# T\n", WriteupRequest("TryHackMe", "X"))


def test_create_writeup_creates_files_that_pass_lint_when_complete(repo: Path) -> None:
    request = WriteupRequest(
        "TryHackMe",
        "Blue",
        difficulty="Easy",
        category="Windows",
        link="https://tryhackme.com/room/blue",
        os="Windows",
        date=SOLVED,
    )
    readme = create_writeup(repo, request)

    assert readme == (repo / "TryHackMe/blue/README.md").resolve()
    assert (readme.parent / "images" / ".gitkeep").is_file()
    writeup = parse_writeup(readme, repo)
    assert writeup.title == "Blue"
    assert writeup.get("OS") == "Windows"
    assert run_checks(repo) == []


def test_create_writeup_with_missing_fields_is_flagged_by_lint(repo: Path) -> None:
    create_writeup(repo, WriteupRequest("TryHackMe", "Draft", date=SOLVED))
    codes = {issue.code for issue in run_checks(repo)}
    assert {"META002", "META005"} <= codes


def test_create_writeup_never_overwrites(repo: Path) -> None:
    readme = create_writeup(repo, WriteupRequest("TryHackMe", "Blue"))
    readme.write_text("my notes", encoding="utf-8")

    with pytest.raises(CtfwError, match="already exists"):
        create_writeup(repo, WriteupRequest("TryHackMe", "Blue"))
    assert readme.read_text(encoding="utf-8") == "my notes"


def test_create_writeup_requires_template(tmp_path: Path) -> None:
    with pytest.raises(CtfwError, match="template not found"):
        create_writeup(tmp_path, WriteupRequest("TryHackMe", "Blue"))
