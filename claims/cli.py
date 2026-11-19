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
which writes checked marks (`claims.checked`) for findings of one run,
and `pending-marks` and `approve-marks`, which list and approve the
marks no person has reviewed yet."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks  # noqa: F401
from .checked import (
    CHECKED_FILENAME,
    ORPHAN_MODE,
    UNITS,
    approve_marks,
    failing_unmarked,
    load_marks,
    markable_check,
    marks_added,
    marks_at,
    new_marks,
    orphaned_marks,
    pending_marks,
    unmarkable_names,
    write_marks,
)
from .config import ConfigError, load_config
from .git import resolve_commit
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
    parser.add_argument(
        "--fail-on-unmarked",
        nargs="?",
        const=",".join(UNITS),
        metavar="CHECK,...",
        help=(
            "Exit 3 on an advisory finding no checked mark keeps quiet, from "
            "the named markable checks (default: every one), or on an orphaned mark."
        ),
    )
    args = parser.parse_args(argv)
    if args.fail_on_unmarked is not None:
        names = [n.strip() for n in args.fail_on_unmarked.split(",") if n.strip()]
        if not names:
            parser.error(f"--fail-on-unmarked= names no check (one of {', '.join(UNITS)})")
        problem = unmarkable_names(names)
        if problem is not None:
            parser.error(f"--fail-on-unmarked: {problem}")
        args.fail_on_unmarked = frozenset(names)
    return args


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
    parser.add_argument(
        "--prune",
        action="store_true",
        help=(
            "Also remove every orphaned mark, one a run reports as checked-mark; "
            "entries are then optional."
        ),
    )
    parser.add_argument(
        "--partial",
        action="store_true",
        help=(
            "Record that only part of each section or doc comment was read "
            "(stale-claims and spliced-docs findings only)."
        ),
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help="Record each mark as pending a person's review (see approve-marks).",
    )
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
        pruned = orphaned_marks(repo_root, config) if args.prune else []
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid: {e}", file=sys.stderr)
        return 2
    # One entry per line, never numbered against a file: `splitlines()` will do.
    if args.entries == "-" and args.prune and sys.stdin.isatty():
        # `--prune` alone at a terminal: no entries, rather than a wait for them.
        entries = []
    elif args.entries == "-":
        entries = sys.stdin.read().splitlines()
    else:
        try:
            entries = Path(args.entries).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as e:
            print(f"can't read entries from {args.entries}: {e}", file=sys.stderr)
            return 2

    result = run(repo_root, args.diff_range, config)
    marks, problems = new_marks(
        repo_root, result.findings + result.quiet, config, entries, args.by, partial=args.partial, pending=args.pending
    )
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"nothing marked: {len(problems)} bad entr{'y' if len(problems) == 1 else 'ies'}", file=sys.stderr)
        return 1
    if not marks and not args.prune:
        print("nothing marked: no entries given", file=sys.stderr)
        return 1
    if marks or pruned:
        write_marks(repo_root, marks, pruned)
    if marks:
        print(f"marked {len(marks)} finding(s) in {CHECKED_FILENAME}")
    if args.prune:
        print(f"pruned {len(pruned)} orphaned mark(s) from {CHECKED_FILENAME}")
    return 0


def _commit_or_error(repo_root: Path, rev: str) -> str | None:
    """The commit `rev` names, its file valid there, or `None` once the
    reason it can't be read is printed."""

    commit = resolve_commit(repo_root, rev)
    if commit is None:
        print(f"{rev} names no commit", file=sys.stderr)
        return None
    try:
        marks_at(repo_root, commit)
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid at {rev}: {e}", file=sys.stderr)
        return None
    return commit


def list_pending(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli pending-marks",
        description=(
            "List every pending checked mark as `<file>:<line> <mode> <note>`; "
            "exit 1 while any exist. Runs no checks."
        ),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--at", metavar="REV", help="Read the file as committed at REV (default: the working tree).")
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    commit = None
    if args.at is not None:
        commit = _commit_or_error(repo_root, args.at)
        if commit is None:
            return 2
    try:
        pending = pending_marks(repo_root, commit)
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid: {e}", file=sys.stderr)
        return 2
    for line in pending:
        print(line)
    print(f"{len(pending)} pending mark(s)")
    return 1 if pending else 0


def approve(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli approve-marks",
        description=(
            "Approve every pending checked mark that was pending, and otherwise "
            "the same, in the file as committed at REV."
        ),
    )
    parser.add_argument("rev", metavar="REV", help="The commit whose pending marks were reviewed.")
    parser.add_argument(
        "--by",
        metavar="NAME",
        help="Name the approver on each approved entry, replacing any existing `by` value.",
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    commit = _commit_or_error(repo_root, args.rev)
    if commit is None:
        return 2
    try:
        load_marks(repo_root)
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid: {e}", file=sys.stderr)
        return 2
    approved, left = approve_marks(repo_root, commit, args.rev, args.by)
    for line in approved:
        print(f"approved {line}")
    for line in left:
        print(f"left pending {line}")
    print(f"approved {len(approved)} mark(s), left {len(left)} pending")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["mark-checked"]:
        return mark_checked(argv[1:])
    if argv[:1] == ["pending-marks"]:
        return list_pending(argv[1:])
    if argv[:1] == ["approve-marks"]:
        return approve(argv[1:])
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
        if result.quiet_partly:
            summary += f", {len(result.quiet_partly)} of them partly"
        if result.quiet_pending:
            summary += f", {len(result.quiet_pending)} of them pending"
    covered: frozenset[str] | None = args.fail_on_unmarked
    unmarked = []
    if covered is not None:
        unmarked = [
            f
            for f in result.findings
            if not f.gate and (f.mode == ORPHAN_MODE or markable_check(f.mode) in covered)
        ]
        summary += f", {len(unmarked)} unmarked"
    added, added_pending = marks_added(repo_root, args.diff_range)
    if added:
        summary += f", {added} mark(s) added in range"
        if added_pending:
            summary += f", {added_pending} of them pending"
    print(summary)
    if gate_findings:
        return 1
    if unmarked:
        print(failing_unmarked(len(unmarked)))
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
