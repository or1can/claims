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

"""`fold-approvals`: approve pending marks inside the commits that wrote
them, by one rebase of the branch
(`decisions/0017-an-approval-is-folded-into-the-commit-that-wrote-the-mark.md`).

The rebase runs two pieces of this module in processes of their own,
`python -m claims.fold merge` as `claims.checked.toml`'s merge driver and
`python -m claims.fold approve` as each named commit's `exec` step, both
switched on for that one rebase and documented nowhere else: neither is
a command a person runs."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path

from .checked import (
    CHECKED_FILENAME,
    Mark,
    _parse_marks,
    approve_marks,
    marks_at,
    own_pending,
    pending_marks,
    write_marks_file,
)
from .config import ConfigError
from .git import blob_text, resolve_commit, toplevel

DRIVER = "claims-fold"
_FIXUP = "fixup! "
# Folded by `git rebase --autosquash` with a message to edit, which a
# fold has nobody to do.
_UNFOLDABLE = ("squash! ", "amend! ")
_BY_LINE_RE = re.compile(r'^by = ".*"$')
_REVIEW_LINE = 'review = "pending"'


@dataclass(frozen=True)
class Commit:
    sha: str
    subject: str

    def __str__(self) -> str:
        return f"{self.sha[:7]} {self.subject}"


@dataclass
class Group:
    """A commit and the `fixup!` commits an autosquash folds into it."""

    root: Commit
    fixups: list[Commit] = field(default_factory=list)


class Refusal(Exception):
    """Why the fold won't start; nothing has changed."""


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args], capture_output=True, text=True, errors="replace"
    )


def _claims_command(*args: str) -> str:
    """A shell command running this module with `args`, importing this
    copy of `claims` whatever directory git runs it from."""

    package_parent = str(Path(__file__).resolve().parent.parent)
    return " ".join(
        [f"PYTHONPATH={shlex.quote(package_parent)}", shlex.quote(sys.executable), "-m", "claims.fold", *args]
    )


def driver_command() -> str:
    """The merge driver's command line, `%O %A %B` as git substitutes them."""

    return _claims_command("merge", "%O", "%A", "%B")


def _range(repo_root: Path, base: str) -> list[Commit]:
    result = _git(repo_root, "log", "--reverse", "--topo-order", "--format=%H %s", f"{base}..HEAD")
    if result.returncode != 0:
        raise Refusal(f"can't list {base}..HEAD: {result.stderr.strip()}")
    return [Commit(*line.split(" ", 1)) for line in result.stdout.splitlines()]


def _groups(repo_root: Path, commits: list[Commit]) -> list[Group]:
    """`commits` grouped as `git rebase --autosquash` groups them: a
    `fixup! X` joins the earliest commit before it whose subject is `X`,
    else the one `X` names when it is a single word, else the earliest
    whose subject starts with `X`; a fixup of a fixup joins that one's
    group."""

    groups: list[Group] = []
    group_of: dict[str, Group] = {}
    earlier: list[Commit] = []
    for commit in commits:
        if commit.subject.startswith(_UNFOLDABLE):
            raise Refusal(f"{commit} is not a fixup! commit; reword it as one, or squash it first")
        target_text = commit.subject
        while target_text.startswith(_FIXUP):
            target_text = target_text[len(_FIXUP) :]
        if target_text == commit.subject:
            group_of[commit.sha] = Group(commit)
            groups.append(group_of[commit.sha])
            earlier.append(commit)
            continue
        target = next((c for c in earlier if c.subject == target_text), None)
        if target is None and " " not in target_text:
            sha = resolve_commit(repo_root, target_text)
            target = next((c for c in earlier if c.sha == sha), None)
        if target is None:
            target = next((c for c in earlier if c.subject.startswith(target_text)), None)
        if target is None:
            raise Refusal(f"{commit} targets no commit before it in the range")
        group_of[target.sha].fixups.append(commit)
        group_of[commit.sha] = group_of[target.sha]
        earlier.append(commit)
    return groups


def _refuse_unless_ready(repo_root: Path, base: str) -> None:
    for name in ("rebase-merge", "rebase-apply"):
        path = _git(repo_root, "rev-parse", "--git-path", name).stdout.strip()
        if path and (repo_root / path).exists():
            raise Refusal("a rebase is in progress; finish or abort it first")
    if _git(repo_root, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise Refusal("the working tree has uncommitted changes")
    if _git(repo_root, "symbolic-ref", "-q", "HEAD").returncode != 0:
        raise Refusal("HEAD is detached; check out the branch to fold")
    merges = _git(repo_root, "rev-list", "--merges", f"{base}..HEAD").stdout.split()
    if merges:
        raise Refusal(f"{merges[0][:7]} is a merge commit, which a rebase would flatten")
    try:
        if any(m.pending for m in marks_at(repo_root, base)):
            raise Refusal(f"{CHECKED_FILENAME} already holds a pending mark at {base}")
    except ConfigError as e:
        raise Refusal(f"{CHECKED_FILENAME} is invalid at {base}: {e}") from e


def _named(repo_root: Path, groups: list[Group], revs: list[str]) -> set[str]:
    roots = {g.root.sha for g in groups}
    fixups = {f.sha: g.root for g in groups for f in g.fixups}
    named = set()
    for rev in revs:
        sha = resolve_commit(repo_root, rev)
        if sha in fixups:
            raise Refusal(f"{rev} is a fixup of {fixups[sha]}; name that commit instead")
        if sha not in roots:
            raise Refusal(f"{rev} names no commit in the range")
        named.add(sha)
    return named


def _own(repo_root: Path, commit: str) -> list[str]:
    return pending_marks(repo_root, commit, own=True)


def _preview(repo_root: Path, groups: list[Group], named: set[str], by: str) -> None:
    for group in groups:
        print(group.root)
        for entry in _own(repo_root, group.root.sha):
            print(f"    {entry}")
        for fixup in group.fixups:
            print(f"    fixup {fixup}")
            for entry in _own(repo_root, fixup.sha):
                print(f"        {entry}")
    for group in groups:
        if group.root.sha in named:
            print(f"plan: approve {group.root} and its {len(group.fixups)} fixup(s) --by {by}")
        elif group.fixups:
            print(f"plan: fold {len(group.fixups)} fixup(s) into {group.root}, approving nothing")


def _todo(groups: list[Group], named: set[str], by: str) -> str:
    lines = []
    for group in groups:
        lines.append(f"pick {group.root.sha}")
        lines.extend(f"fixup {f.sha}" for f in group.fixups)
        if group.root.sha in named:
            shas = [group.root.sha, *(f.sha for f in group.fixups)]
            lines.append("exec " + _claims_command("approve", "--by", shlex.quote(by), *shas))
    return "\n".join(lines) + "\n"


def _only_approvals(old: str | None, new: str | None) -> bool:
    """Whether `new` is `old` with `review = "pending"` lines removed and
    `by` lines replaced or added, each only in an entry it approves, and
    nothing else changed."""

    try:
        old_marks = {m.key: replace(m, line=0) for m in _parse_marks(old or "")}
        new_marks = {m.key: replace(m, line=0) for m in _parse_marks(new or "")}
    except ConfigError:
        return False
    if old_marks.keys() != new_marks.keys():
        return False
    for key, before in old_marks.items():
        after = new_marks[key]
        approved = before.pending and not after.pending
        if after != before and not (approved and replace(after, pending=True, by=before.by) == before):
            return False
    old_lines = (old or "").splitlines()
    new_lines = (new or "").splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if not all(line == _REVIEW_LINE or _BY_LINE_RE.match(line) for line in old_lines[i1:i2]):
            return False
        if not all(_BY_LINE_RE.match(line) for line in new_lines[j1:j2]):
            return False
    return True


def _check(repo_root: Path, old_tip: str, base: str, groups: list[Group]) -> str | None:
    """Why the folded branch isn't the old one with approvals added, or
    `None` when it is."""

    changed = _git(repo_root, "diff", "--name-only", "-z", old_tip, "HEAD").stdout.split("\0")
    others = sorted(p for p in changed if p and p != CHECKED_FILENAME)
    if others:
        return f"the fold changed {', '.join(others)}"
    if not _only_approvals(blob_text(repo_root, old_tip, CHECKED_FILENAME), blob_text(repo_root, "HEAD", CHECKED_FILENAME)):
        return f"the fold changed {CHECKED_FILENAME} beyond approving marks"
    count = len(_git(repo_root, "rev-list", f"{base}..HEAD").stdout.split())
    if count != len(groups):
        return f"the fold left {count} commit(s) where {len(groups)} were expected"
    return None


def _apply(repo_root: Path, base: str, groups: list[Group], named: set[str], by: str) -> int:
    old = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    branch = _git(repo_root, "symbolic-ref", "--short", "HEAD").stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        todo = Path(tmp) / "todo"
        todo.write_text(_todo(groups, named, by), encoding="utf-8")
        attributes = Path(tmp) / "attributes"
        attributes.write_text(f"/{CHECKED_FILENAME} merge={DRIVER}\n", encoding="utf-8")
        driver = [
            "-c",
            f"core.attributesFile={attributes}",
            "-c",
            f"merge.{DRIVER}.name=claims fold-approvals",
            "-c",
            f"merge.{DRIVER}.driver={driver_command()}",
        ]
        # The repository's own attributes outrank `core.attributesFile`.
        attribute = _git(repo_root, *driver, "check-attr", "merge", "--", CHECKED_FILENAME).stdout
        if not attribute.rstrip().endswith(f": merge: {DRIVER}"):
            print(
                f"refusing: the repository's own merge attribute for {CHECKED_FILENAME} "
                f"overrides the fold's: {attribute.strip()}",
                file=sys.stderr,
            )
            return 1
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                *driver,
                "rebase",
                "-i",
                "--no-autosquash",
                "--no-update-refs",
                base,
            ],
            capture_output=True,
            text=True,
            errors="replace",
            # The environment's editors outrank any `-c`, so these are set here.
            env={**os.environ, "GIT_SEQUENCE_EDITOR": f"cp {shlex.quote(str(todo))}", "GIT_EDITOR": "true"},
        )
    if result.returncode != 0:
        _git(repo_root, "rebase", "--abort")
        _git(repo_root, "reset", "-q", "--hard", old)
        print(f"the rebase stopped; {branch} is back at {old}", file=sys.stderr)
        print(result.stdout + result.stderr, file=sys.stderr, end="")
        return 1
    problem = _check(repo_root, old, base, groups)
    if problem is not None:
        _git(repo_root, "reset", "-q", "--hard", old)
        print(f"{problem}; {branch} is back at {old}", file=sys.stderr)
        return 1
    new_commits = _git(repo_root, "rev-list", "--reverse", "--topo-order", f"{base}..HEAD").stdout.split()
    for group, new in zip(groups, new_commits):
        if group.root.sha not in named:
            continue
        print(f"approved in {new[:7]} {group.root.subject}")
        for entry in _own(repo_root, new):
            print(f"    left pending {entry}")
    print(f"old tip: {old}")
    print(f"to publish: git push --force-with-lease={branch}:{old}")
    return 0


def fold_approvals(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m claims.cli fold-approvals",
        description=(
            "Approve the pending marks each named commit in BASE..HEAD wrote, "
            "inside that commit, by one autosquash rebase. Previews unless --apply."
        ),
    )
    parser.add_argument("base", metavar="BASE", help="The commit the branch is folded onto.")
    parser.add_argument(
        "--approve",
        metavar="REV",
        action="append",
        default=[],
        help="A commit whose own marks, and its fixups', were reviewed (repeatable).",
    )
    parser.add_argument("--by", metavar="NAME", required=True, help="Name the approver on each approved entry.")
    parser.add_argument("--apply", action="store_true", help="Rewrite the branch (default: preview only).")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    if "\n" in args.by or "\r" in args.by:
        # Each step is one line of the rebase's todo.
        parser.error("--by can't hold a line break")
    repo_root: Path = args.repo_root.resolve()
    base = resolve_commit(repo_root, args.base)
    if base is None:
        print(f"{args.base} names no commit", file=sys.stderr)
        return 2
    try:
        _refuse_unless_ready(repo_root, base)
        groups = _groups(repo_root, _range(repo_root, base))
        try:
            if not any(_own(repo_root, c.sha) for g in groups for c in (g.root, *g.fixups)):
                raise Refusal(f"nothing is pending in {args.base}..HEAD")
        except ConfigError as e:
            raise Refusal(f"{CHECKED_FILENAME} is invalid in the range: {e}") from e
        named = _named(repo_root, groups, args.approve)
    except Refusal as e:
        print(f"refusing: {e}", file=sys.stderr)
        return 1
    if not args.apply or not named:
        _preview(repo_root, groups, named, args.by)
        print("nothing changed: this was a preview; add --apply to fold")
        return 0
    return _apply(repo_root, base, groups, named, args.by)


def merge(base: Path, ours: Path, theirs: Path) -> int:
    """Merge `claims.checked.toml` three-way by entry, writing `ours`: each
    side's own additions, deletions and edits apply, and where both
    changed one entry, `theirs`, the commit being replayed, wins. Exits
    1, a conflict, when any side doesn't parse."""

    def read(path: Path) -> dict[tuple[str, str, str], Mark]:
        return {m.key: replace(m, line=0) for m in _parse_marks(path.read_text(encoding="utf-8"))}

    try:
        in_base, in_ours, replayed = read(base), read(ours), read(theirs)
    except (ConfigError, OSError, UnicodeDecodeError):
        return 1
    marks: list[Mark] = []
    pruned: list[Mark] = []
    for key in in_base.keys() | in_ours.keys() | replayed.keys():
        replayed_changed = replayed.get(key) != in_base.get(key)
        result = replayed.get(key) if replayed_changed else in_ours.get(key)
        if result == in_ours.get(key):
            continue
        if result is None:
            pruned.append(in_ours[key])
        else:
            marks.append(result)
    write_marks_file(ours, marks, pruned)
    return 0


def approve_step(by: str, shas: list[str]) -> int:
    """Approve, in the commit being rewritten, the marks `shas` (a commit
    and its fixups, as originally committed) wrote, against each in turn,
    and amend `claims.checked.toml` into the commit."""

    repo_root = toplevel(Path.cwd())
    if repo_root is None:
        return 1
    try:
        own = {m.key for sha in shas for m in own_pending(repo_root, sha)}
        for sha in shas:
            approve_marks(repo_root, sha, sha[:7], by, own)
    except ConfigError as e:
        print(f"{CHECKED_FILENAME} is invalid: {e}", file=sys.stderr)
        return 1
    if _git(repo_root, "diff", "--quiet", "HEAD", "--", CHECKED_FILENAME).returncode == 0:
        return 0
    amend = _git(repo_root, "commit", "-q", "--amend", "--no-edit", "--no-verify", "--", CHECKED_FILENAME)
    if amend.returncode != 0:
        print(amend.stdout + amend.stderr, file=sys.stderr, end="")
    return amend.returncode


def main(argv: list[str]) -> int:
    if argv[:1] == ["merge"] and len(argv) == 4:
        return merge(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    if argv[:2] == ["approve", "--by"] and len(argv) > 3:
        return approve_step(argv[2], argv[3:])
    print(f"not a fold step: {' '.join(argv)}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
