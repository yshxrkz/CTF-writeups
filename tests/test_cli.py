from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import PROJECT_ROOT, WriteFile, writeup_text
from ctfw import __version__
from ctfw.cli import main


def run(repo: Path, *args: str) -> int:
    return main(["--root", str(repo), *args])


# --------------------------------------------------------------------------- new


def test_new_creates_writeup_and_prints_next_steps(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run(repo, "new", "hackthebox", "Lame", "--kind", "machine", "--date", "2026-03-14")

    assert code == 0
    assert (repo / "HackTheBox/Machines/lame/README.md").is_file()
    out = capsys.readouterr().out
    assert "Created HackTheBox/Machines/lame/README.md" in out
    assert "ctfw lint" in out


def test_new_reports_errors_with_exit_code_2(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(repo, "new", "HackTheBox", "Lame") == 2
    assert "ctfw: error: HackTheBox writeups need --kind" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["new", "vulnhub", "X"],
        ["new", "TryHackMe", "X", "--date", "14/03/2026"],
        ["new", "TryHackMe", "X", "--date", "20260314"],
        ["new", "HackTheBox", "X", "--kind", "fortress"],
        [],
    ],
)
def test_bad_arguments_exit_with_usage_error(repo: Path, args: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        run(repo, *args)
    assert exc_info.value.code == 2


# --------------------------------------------------------------------------- index


def test_index_check_then_update_then_check(
    repo: Path, write: WriteFile, capsys: pytest.CaptureFixture[str]
) -> None:
    write("TryHackMe/example/README.md", writeup_text())

    assert run(repo, "index", "--check") == 1
    assert "out of date" in capsys.readouterr().out

    assert run(repo, "index") == 0
    assert "Updated README.md index (1 writeup)." in capsys.readouterr().out

    assert run(repo, "index", "--check") == 0
    assert "up to date" in capsys.readouterr().out


def test_index_without_markers_is_an_error(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (repo / "README.md").write_text("# no markers\n", encoding="utf-8")
    assert run(repo, "index") == 2
    assert "marker" in capsys.readouterr().err


def test_missing_root_is_an_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path / "nope", "lint") == 2
    assert "is not a directory" in capsys.readouterr().err


# --------------------------------------------------------------------------- lint


def test_lint_clean_repo(repo: Path, write: WriteFile, capsys: pytest.CaptureFixture[str]) -> None:
    write("TryHackMe/example/README.md", writeup_text())
    assert run(repo, "lint") == 0
    assert "No problems found (1 writeup, 3 files scanned)." in capsys.readouterr().out


def test_lint_reports_problems(
    repo: Path, write: WriteFile, capsys: pytest.CaptureFixture[str]
) -> None:
    text = writeup_text(extra="\nTHM{oops}\n")
    write("TryHackMe/example/README.md", text)
    leak_line = text.splitlines().index("THM{oops}") + 1

    assert run(repo, "lint") == 1
    out = capsys.readouterr().out
    assert f"TryHackMe/example/README.md:{leak_line}: LEAK001" in out
    assert "THM{oops}" not in out
    assert "Found 1 problem in 1 file." in out


def test_lint_github_format(
    repo: Path, write: WriteFile, capsys: pytest.CaptureFixture[str]
) -> None:
    write("TryHackMe/example/README.md", writeup_text(link="http://x"))
    assert run(repo, "lint", "--format", "github") == 1
    assert "::error file=TryHackMe/example/README.md,line=6,title=META006::" in (
        capsys.readouterr().out
    )


# --------------------------------------------------------------------------- the real repo


def test_this_repository_passes_lint_and_index_check() -> None:
    """Guards the published writeups: no leaks, no broken links, index in sync."""
    assert main(["--root", str(PROJECT_ROOT), "lint"]) == 0
    assert main(["--root", str(PROJECT_ROOT), "index", "--check"]) == 0


def test_python_dash_m_entry_point() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ctfw", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == f"ctfw {__version__}"
