from __future__ import annotations

from pathlib import Path

import pytest

from conftest import WriteFile, writeup_text
from ctfw.checks import (
    Issue,
    check_flags_table,
    check_links,
    check_metadata,
    check_sections,
    iter_scan_targets,
    run_checks,
    scan_leaks,
)
from ctfw.writeup import parse_writeup

FAKE_HEX = "0123456789abcdef0123456789abcdef"


def _codes(issues: list[Issue]) -> list[str]:
    return [issue.code for issue in issues]


def test_valid_writeup_has_no_issues(repo: Path, write: WriteFile) -> None:
    write("TryHackMe/example/README.md", writeup_text())
    assert run_checks(repo) == []


# --------------------------------------------------------------------------- metadata


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"link": ""}, "META001"),
        ({"link": "<URL to the room, machine, or challenge>"}, "META002"),
        ({"category": "e.g. Web, Linux"}, "META002"),
        ({"date": "YYYY-MM-DD"}, "META002"),
        ({"platform": "HackTheBox"}, "META003"),
        ({"date": "2026-02-30"}, "META004"),
        ({"date": "20260101"}, "META004"),
        ({"difficulty": "Trivial"}, "META005"),
        ({"link": "http://tryhackme.com/room/x"}, "META006"),
    ],
)
def test_check_metadata_flags_bad_values(
    repo: Path, write: WriteFile, overrides: dict[str, str], code: str
) -> None:
    path = write("TryHackMe/example/README.md", writeup_text(**overrides))
    issues = check_metadata(parse_writeup(path, repo))
    assert _codes(issues) == [code]
    assert issues[0].line > 0  # points at the offending metadata row


def test_check_metadata_flags_placeholder_title(repo: Path, write: WriteFile) -> None:
    path = write("TryHackMe/example/README.md", writeup_text("<Room / Machine Name>"))
    assert _codes(check_metadata(parse_writeup(path, repo))) == ["META002"]


def test_unfilled_template_fails_metadata_checks(repo: Path, write: WriteFile) -> None:
    template = (repo / "templates" / "writeup-template.md").read_text(encoding="utf-8")
    path = write("TryHackMe/draft/README.md", template)
    codes = _codes(check_metadata(parse_writeup(path, repo)))
    assert codes.count("META002") >= 3  # title, link, category, date placeholders
    assert "META003" in codes  # "TryHackMe / HackTheBox / PicoCTF"
    assert "META005" in codes  # "Easy / Medium / Hard / Insane"


def test_check_sections_reports_each_missing_section(repo: Path, write: WriteFile) -> None:
    text = writeup_text().replace("## Tools", "## Toolbox").replace("## Flags", "### Flags")
    writeup = parse_writeup(write("TryHackMe/example/README.md", text), repo)
    messages = [issue.message for issue in check_sections(writeup)]
    assert messages == [
        "missing required section '## Tools'",
        "missing required section '## Flags'",
    ]


def test_check_sections_is_case_insensitive(repo: Path, write: WriteFile) -> None:
    text = writeup_text().replace("## Lessons Learned", "## lessons learned")
    assert check_sections(parse_writeup(write("TryHackMe/x/README.md", text), repo)) == []


# --------------------------------------------------------------------------- flags table


@pytest.mark.parametrize("value", ["`REDACTED`", "REDACTED", "**redacted**", ""])
def test_flags_table_accepts_redacted_or_empty_values(
    repo: Path, write: WriteFile, value: str
) -> None:
    writeup = parse_writeup(write("TryHackMe/x/README.md", writeup_text(flag_value=value)), repo)
    assert check_flags_table(writeup) == []


def test_flags_table_rejects_real_value_without_echoing_it(repo: Path, write: WriteFile) -> None:
    writeup = parse_writeup(
        write("TryHackMe/x/README.md", writeup_text(flag_value="`super secret ingredient`")), repo
    )
    issues = check_flags_table(writeup)
    assert _codes(issues) == ["LEAK002"]
    assert "super secret" not in issues[0].message


def test_flags_table_uses_value_column_not_last_column(repo: Path, write: WriteFile) -> None:
    text = writeup_text().replace(
        "| Flag   | Location   | Value |\n| ------ | ---------- | ----- |\n"
        "| User   | `/home/u`  | `REDACTED` |",
        "| Value | Notes |\n| ----- | ----- |\n| `REDACTED` | found via sudo |",
    )
    writeup = parse_writeup(write("TryHackMe/x/README.md", text), repo)
    assert check_flags_table(writeup) == []


def test_flags_table_check_ignores_tables_in_other_sections(repo: Path, write: WriteFile) -> None:
    extra = "\n## Notes\n\n| Flag | Value |\n| ---- | ----- |\n| x | not-a-flag |\n"
    writeup = parse_writeup(write("TryHackMe/x/README.md", writeup_text(extra=extra)), repo)
    assert check_flags_table(writeup) == []


# --------------------------------------------------------------------------- leaks


@pytest.mark.parametrize(
    "line",
    [
        "THM{real_flag_here}",
        "the answer was HTB{y0u_f0und_m3}",
        "picoCTF{b4by_st3ps}",
        "flag{abc}",
        "```FLAG{in code}```",
    ],
)
def test_scan_leaks_finds_unredacted_flags(line: str) -> None:
    issues = scan_leaks(Path("f.md"), ["ok", line])
    assert _codes(issues) == ["LEAK001"]
    assert issues[0].line == 2
    assert "{…}" in issues[0].message  # value is masked in the message


@pytest.mark.parametrize(
    "line",
    [
        "picoCTF{REDACTED}",
        "Redact the `picoCTF{...}` flag value",
        "THM{<flag>}",
        "HTB{xxxxxxxx}",
        "THM{}",
        "${HOME}",
        "else{ return 0; }",
        f"md5: {FAKE_HEX}0",  # 33 chars: not a 32-char token
        f"{FAKE_HEX} <!-- ctfw: allow-leak -->",
        "THM{real} <!-- ctfw: allow-leak -->",
    ],
)
def test_scan_leaks_ignores_redacted_and_non_flags(line: str) -> None:
    assert scan_leaks(Path("f.md"), [line]) == []


def test_scan_leaks_finds_32_char_hex() -> None:
    issues = scan_leaks(Path("f.md"), [f"root.txt: {FAKE_HEX}"])
    assert _codes(issues) == ["LEAK003"]
    assert FAKE_HEX not in issues[0].message


def test_run_checks_scans_scripts_in_platform_folders_but_not_elsewhere(
    repo: Path, write: WriteFile
) -> None:
    write("TryHackMe/x/README.md", writeup_text())
    write("TryHackMe/x/exploit.py", 'print("THM{leaked_in_script}")\n')
    write("tools/helper.py", 'EXAMPLE = "THM{fixture}"\n')

    issues = run_checks(repo)

    assert [(i.path.as_posix(), i.code) for i in issues] == [("TryHackMe/x/exploit.py", "LEAK001")]


def test_run_checks_skips_binary_files_and_reports_undecodable_text(
    repo: Path, write: WriteFile
) -> None:
    write("TryHackMe/x/README.md", writeup_text())
    (repo / "TryHackMe/x/images").mkdir()
    (repo / "TryHackMe/x/images/shot.png").write_bytes(b"\x89PNG\r\n\x1a\n\0\0THM{binary}")
    (repo / "TryHackMe/x/notes.txt").write_bytes(b"caf\xe9")

    assert [(i.path.as_posix(), i.code) for i in run_checks(repo)] == [
        ("TryHackMe/x/notes.txt", "FILE001")
    ]


def test_iter_scan_targets_prunes_hidden_and_vendor_dirs(repo: Path, write: WriteFile) -> None:
    write(".git/notes.md", "THM{x}")
    write("node_modules/pkg/README.md", "THM{x}")
    write("TryHackMe/.venv/lib.txt", "THM{x}")
    write("src/pkg.egg-info/SOURCES.txt", "THM{x}")
    write("docs/guide.md", "ok")
    found = {p.relative_to(repo).as_posix() for p in iter_scan_targets(repo)}
    assert found == {"README.md", "templates/writeup-template.md", "docs/guide.md"}


# --------------------------------------------------------------------------- links


def test_check_links_resolves_relative_root_and_anchor_links(repo: Path, write: WriteFile) -> None:
    write("TryHackMe/x/images/nmap.png", "png")
    lines = [
        "![scan](images/nmap.png)",
        "[home](../../README.md#index)",
        "[root](/templates/writeup-template.md)",
        '[with title](images/nmap.png "Nmap")',
        "[ext](https://example.com/missing) [mail](mailto:a@b.c) [anchor](#flags)",
        "[ref]: images/nmap.png",
    ]
    assert check_links(Path("TryHackMe/x/README.md"), lines, repo) == []


def test_check_links_reports_broken_and_escaping_links(repo: Path) -> None:
    lines = [
        "![missing](images/nope.png)",
        "[escape](../../../etc/passwd)",
        "[ref]: missing.md",
    ]
    issues = check_links(Path("TryHackMe/x/README.md"), lines, repo)
    assert [(i.line, i.code) for i in issues] == [(1, "LINK001"), (2, "LINK002"), (3, "LINK001")]


def test_check_links_ignores_code_blocks_and_inline_code(repo: Path) -> None:
    lines = [
        "Reference images with `![nmap scan](images/nmap.png)`.",
        "```markdown",
        "![also ignored](images/nmap.png)",
        "```",
    ]
    assert check_links(Path("README.md"), lines, repo) == []


def test_check_links_decodes_percent_encoded_paths(repo: Path, write: WriteFile) -> None:
    write("TryHackMe/two words/README.md", "# x\n")
    assert check_links(Path("README.md"), ["[x](TryHackMe/two%20words/README.md)"], repo) == []


# --------------------------------------------------------------------------- formatting


def test_issue_formats() -> None:
    issue = Issue(Path("TryHackMe/x/README.md"), 12, "LEAK001", "100% bad")
    assert issue.format() == "TryHackMe/x/README.md:12: LEAK001 100% bad"
    assert issue.format_github() == (
        "::error file=TryHackMe/x/README.md,line=12,title=LEAK001::100%25 bad"
    )
    whole_file = Issue(Path("a.md"), 0, "SECT001", "m")
    assert whole_file.format() == "a.md: SECT001 m"
    assert whole_file.format_github() == "::error file=a.md,title=SECT001::m"
