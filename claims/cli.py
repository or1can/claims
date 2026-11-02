# Copyright 2026 Orican Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Minimal CLI adapter over `claims.runner.run`, plus `mark-checked`,
which writes checked marks (`claims.checked`) for findings of one run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks  # noqa: F401
from .checked import CHECKED_FILENAME, load_marks, new_marks, write_marks
from .config import ConfigError, load_config
from .runner import format_findings, run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="claims")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to check (default: current directory).",
    )
    parser.add_argument(
        "--diff-range",
        default="HEAD",
        help="Diff range to check, working tree against this ref (default: HEAD).",
    )
    return parser.parse_args(argv)


def parse_mark_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli mark-checked",
        description=(
            "Record that advisory findings were read. One entry per line, "
            "`<file>:<line> <mode> <note>`, each naming a finding of a run "
            "over --diff-range."
        ),
    )
    parser.add_argument("entries", nargs="?", default="-", help="File of entries, or - for stdin (default).")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--diff-range", default="HEAD", help="Range to find the findings in (default: HEAD).")
    parser.add_argument("--by", help="Who read the findings, recorded on each mark.")
    return parser.parse_args(argv)


def mark_checked(argv: list[str]) -> int:
    args = parse_mark_args(argv)
    repo_root: Path = args.repo_root.resolve()
    try:
        config = load_config(repo_root)
    except ConfigError as e:
        print(f"claims.toml is invalid: {e}", file=sys.stderr)
        return 2
    try:
        load_marks(repo_root)
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid: {e}", file=sys.stderr)
        return 2
    if args.entries == "-":
        entries = sys.stdin.read().splitlines()
    else:
        try:
            entries = Path(args.entries).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            print(f"can't read entries from {args.entries}: {e}", file=sys.stderr)
            return 2

    result = run(repo_root, args.diff_range, config)
    marks, problems = new_marks(
        repo_root, result.findings + result.quiet, config, entries, args.by
    )
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"nothing marked: {len(problems)} bad entr{'y' if len(problems) == 1 else 'ies'}", file=sys.stderr)
        return 1
    if not marks:
        print("nothing marked: no entries given", file=sys.stderr)
        return 1
    write_marks(repo_root, marks)
    print(f"marked {len(marks)} finding(s) in {CHECKED_FILENAME}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["mark-checked"]:
        return mark_checked(argv[1:])
    args = parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    try:
        config = load_config(repo_root)
    except ConfigError as e:
        print(f"claims.toml is invalid: {e}", file=sys.stderr)
        return 2
    result = run(repo_root, args.diff_range, config)

    if not result.checks_run:
        print("0 checked — no checks registered (failure, not a clean pass)")
        return 1

    for line in format_findings(result.findings):
        print(line)

    gate_findings = [f for f in result.findings if f.gate]
    summary = (
        f"{len(result.checks_run)} checked, {len(result.findings)} finding(s), "
        f"{len(gate_findings)} gate failure(s)"
    )
    if result.quiet:
        summary += f", {len(result.quiet)} quiet while checked"
    print(summary)
    return 1 if gate_findings else 0


if __name__ == "__main__":
    sys.exit(main())
