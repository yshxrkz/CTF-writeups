"""Command-line interface: ``ctfw new | index | lint``.

Exit codes:
    0  success / no problems
    1  checks failed (lint problems, or ``index --check`` found a stale README)
    2  usage or runtime error (bad arguments, unreadable files, ...)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from ctfw import __version__
from ctfw.checks import DIFFICULTIES, iter_scan_targets, run_checks
from ctfw.errors import CtfwError
from ctfw.index import update_readme
from ctfw.scaffold import HTB_KINDS, WriteupRequest, create_writeup
from ctfw.writeup import PLATFORMS, discover_writeups, platform_for


def _platform_arg(value: str) -> str:
    try:
        return platform_for(value)
    except CtfwError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _date_arg(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD")
    return parsed


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser (exposed for testing and docs)."""
    parser = argparse.ArgumentParser(
        prog="ctfw",
        description="Scaffold CTF writeups, keep the README index in sync, "
        "and catch leaked flags before they are published.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="repository root (default: current directory)",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    new = commands.add_parser("new", help="create a writeup from the template")
    new.add_argument("platform", type=_platform_arg, help=" | ".join(PLATFORMS))
    new.add_argument("name", help='display name, e.g. "Pickle Rick"')
    new.add_argument("--slug", help="folder name (default: derived from NAME)")
    new.add_argument(
        "--kind", choices=sorted(HTB_KINDS), help="HackTheBox only: machine or challenge"
    )
    new.add_argument(
        "--category",
        help="e.g. Web, Crypto (also the subfolder for HackTheBox challenges and PicoCTF)",
    )
    new.add_argument("--year", help="PicoCTF only: event year or 'practice' (default: this year)")
    new.add_argument("--difficulty", help=" | ".join(DIFFICULTIES))
    new.add_argument("--link", help="https:// URL of the room, machine, or challenge")
    new.add_argument("--os", help="target OS, e.g. Linux")
    new.add_argument("--date", type=_date_arg, help="date solved, YYYY-MM-DD (default: today)")

    index = commands.add_parser("index", help="regenerate the README index table")
    index.add_argument(
        "--check",
        action="store_true",
        help="don't write; exit 1 if the index is out of date (for CI)",
    )

    lint = commands.add_parser("lint", help="check writeups for leaks, broken links, and gaps")
    lint.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="'github' emits workflow annotations that show inline on pull requests",
    )
    return parser


def _cmd_new(root: Path, args: argparse.Namespace) -> int:
    request = WriteupRequest(
        platform=args.platform,
        name=args.name,
        slug=args.slug,
        kind=args.kind,
        category=args.category,
        year=args.year,
        difficulty=args.difficulty,
        link=args.link,
        os=args.os,
        date=args.date,
    )
    readme = create_writeup(root, request).relative_to(root)
    print(f"Created {readme.as_posix()}")
    print("Next steps:")
    print(f"  1. Write it up (screenshots go in {readme.parent.as_posix()}/images/)")
    print("  2. ctfw lint     # catches leaked flags and unfilled placeholders")
    print("  3. ctfw index    # adds it to the README index")
    return 0


def _cmd_index(root: Path, args: argparse.Namespace) -> int:
    writeups = discover_writeups(root)
    up_to_date = update_readme(root / "README.md", writeups, check=args.check)
    count = _plural(len(writeups), "writeup")
    if up_to_date:
        print(f"README.md index is up to date ({count}).")
        return 0
    if args.check:
        print("README.md index is out of date; run `ctfw index` and commit the result.")
        return 1
    print(f"Updated README.md index ({count}).")
    return 0


def _cmd_lint(root: Path, args: argparse.Namespace) -> int:
    issues = run_checks(root)
    for issue in issues:
        print(issue.format_github() if args.format == "github" else issue.format())

    if issues:
        files = len({issue.path for issue in issues})
        print(f"\nFound {_plural(len(issues), 'problem')} in {_plural(files, 'file')}.")
        return 1
    scanned = sum(1 for _ in iter_scan_targets(root))
    writeups = len(discover_writeups(root))
    print(
        f"No problems found ({_plural(writeups, 'writeup')}, {_plural(scanned, 'file')} scanned)."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()
    handlers = {"new": _cmd_new, "index": _cmd_index, "lint": _cmd_lint}
    try:
        if not root.is_dir():
            raise CtfwError(f"repository root {root} is not a directory")
        return handlers[args.command](root, args)
    except CtfwError as exc:
        print(f"ctfw: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
