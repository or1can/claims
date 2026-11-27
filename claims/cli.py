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
`pending-marks` and `approve-marks`, which list and approve the marks no
person has reviewed yet, and `fold-approvals` (`claims.fold`), which
approves them inside the commits that wrote them; and `tree-at` and
`claim-trees` (`claims.trees`), which name and copy the trees a past or
superseded claim is read at; and `check-reading` (`claims.reading`), which
checks a reading agent's output against the findings sent it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import checks  # noqa: F401
from .checked import (
    CHECKED_FILENAME,
    KINDS,
    ORPHAN_MODE,
    SETTLED,
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
from .fold import fold_approvals
from .git import resolve_commit
from .reading import check_reading, extract_array, load_sent
from .runner import format_findings, run
from .trees import TREE_KINDS, claim_trees, tree_copy


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
    parser.add_argument(
        "--kind",
        choices=KINDS,
        help="Record the kind of claim each unit holds (default: current).",
    )
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="PATH[#ANCHOR]",
        help=(
            "A file or section the kind rests on, hashed onto each mark; "
            "repeatable, past or superseded only, and required for superseded."
        ),
    )
    args = parser.parse_args(argv)
    if args.evidence and args.kind not in SETTLED:
        parser.error("--evidence needs --kind past or --kind superseded")
    if args.kind == "superseded" and not args.evidence:
        parser.error("--kind superseded needs --evidence")
    return args


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
        repo_root,
        result.findings + result.quiet,
        config,
        entries,
        args.by,
        partial=args.partial,
        pending=args.pending,
        claim_kind=args.kind,
        evidence=args.evidence,
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


_BASE_HELP = (
    "Flag a superseded or past mark whose evidence differs at REV, such as "
    "the pull request's base (default: %s)."
)


def _base_or_error(repo_root: Path, rev: str | None) -> tuple[bool, str | None]:
    """`(ok, commit)`: the commit a `--base` names, `None` when none was
    given; not ok once the reason it can't be resolved is printed."""

    if rev is None:
        return True, None
    commit = resolve_commit(repo_root, rev)
    if commit is None:
        print(f"{rev} names no commit", file=sys.stderr)
        return False, None
    return True, commit


def list_pending(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli pending-marks",
        description=(
            "List every pending checked mark as `<file>:<line> <mode> <note>`, "
            "then ` (by <by>)` where it names its reader; "
            "exit 1 while any exist. Runs no checks."
        ),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--at", metavar="REV", help="Read the file as committed at REV (default: the working tree).")
    parser.add_argument(
        "--own",
        action="store_true",
        help="With --at, list only the marks REV added or changed since its first parent.",
    )
    parser.add_argument(
        "--base", metavar="REV", help=_BASE_HELP % "HEAD, or with --at, its REV's first parent"
    )
    args = parser.parse_args(argv)
    if args.own and args.at is None:
        parser.error("--own needs --at")
    repo_root: Path = args.repo_root.resolve()
    commit = None
    if args.at is not None:
        commit = _commit_or_error(repo_root, args.at)
        if commit is None:
            return 2
    ok, base = _base_or_error(repo_root, args.base)
    if not ok:
        return 2
    try:
        pending = pending_marks(repo_root, commit, own=args.own, base=base)
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
        help="Name the approver in each approved entry's `approved_by`, leaving its `by`, the reader, as it is.",
    )
    parser.add_argument("--base", metavar="BASE", help=_BASE_HELP % "REV's first parent")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    commit = _commit_or_error(repo_root, args.rev)
    if commit is None:
        return 2
    ok, base = _base_or_error(repo_root, args.base)
    if not ok:
        return 2
    try:
        load_marks(repo_root)
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid: {e}", file=sys.stderr)
        return 2
    approved, left = approve_marks(repo_root, commit, args.rev, args.by, base=base)
    for line in approved:
        print(f"approved {line}")
    for line in left:
        print(f"left pending {line}")
    print(f"approved {len(approved)} mark(s), left {len(left)} pending")
    return 0


def tree_at(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli tree-at",
        description=(
            "Print the path of a read-only copy of the tracked files at REV, "
            "with no .git, made once per commit and reused after."
        ),
    )
    parser.add_argument("rev", metavar="REV")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        print(tree_copy(args.repo_root.resolve(), args.rev))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


def list_claim_trees(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli claim-trees",
        description=(
            "Print the trees a past or superseded claim is read at, one per "
            "line as `<role> <commit> <root>`: `written` and `before` for a "
            "past claim, read at both; `superseded`, with no root, and "
            "`before`, read there, for a superseded one. `working-tree` "
            "stands for the commit an uncommitted line has none of."
        ),
    )
    parser.add_argument(
        "line",
        metavar="FILE:LINE",
        help=(
            "The claim's own line for --kind past; for --kind superseded, the "
            "line of the Status note or record saying it is replaced or withdrawn."
        ),
    )
    parser.add_argument("--kind", choices=TREE_KINDS, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    rel, sep, number = args.line.rpartition(":")
    if not sep or not number.isdigit():
        parser.error(f"{args.line} is not FILE:LINE")
    repo_root: Path = args.repo_root.resolve()
    try:
        trees = claim_trees(repo_root, rel, int(number), args.kind)
        for tree in trees:
            commit = tree.commit or "working-tree"
            if tree.role == "superseded":
                print(f"{tree.role} {commit}")
            elif tree.commit is None:
                print(f"{tree.role} {commit} {repo_root}")
            else:
                print(f"{tree.role} {tree.commit} {tree_copy(repo_root, tree.commit)}")
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


def check_reading_output(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli check-reading",
        description=(
            "Check a reading agent's output against the findings sent it, "
            "and print each item it flags as `<file>:<line> <mode> <type>: "
            "<detail>`, `(not sent)` for an object naming no finding sent; "
            "exit 1 while any are flagged. Types: matching, read, cited, "
            "no-file, no-claims, not-checked."
        ),
    )
    parser.add_argument("output", type=Path, help="The agent's final message, the JSON array it returned.")
    parser.add_argument(
        "sent",
        type=Path,
        help=(
            "A JSON array of the findings sent, each an object with `finding`, "
            "the finding line verbatim, `subjects`, `root` and optionally "
            "`trees`, the lines claim-trees printed for it."
        ),
    )
    args = parser.parse_args(argv)
    try:
        output = args.output.read_text(encoding="utf-8")
        sent = load_sent(json.loads(args.sent.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f"can't read the output or the findings sent: {e}", file=sys.stderr)
        return 2
    reports, _ = extract_array(output)
    flags = check_reading(reports, sent)
    for flag in flags:
        print(flag)
    print(f"{len(flags)} item(s) flagged")
    return 1 if flags else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["mark-checked"]:
        return mark_checked(argv[1:])
    if argv[:1] == ["pending-marks"]:
        return list_pending(argv[1:])
    if argv[:1] == ["approve-marks"]:
        return approve(argv[1:])
    if argv[:1] == ["fold-approvals"]:
        return fold_approvals(argv[1:])
    if argv[:1] == ["tree-at"]:
        return tree_at(argv[1:])
    if argv[:1] == ["claim-trees"]:
        return list_claim_trees(argv[1:])
    if argv[:1] == ["check-reading"]:
        return check_reading_output(argv[1:])
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
