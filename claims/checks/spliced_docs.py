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

"""The `spliced-docs` check: a `///` doc comment an insertion has pushed onto
the wrong declaration. `docs/checks/spliced-docs.md` is the account of
runs, breaks, evidence, the two modes and the `modes` key; this docstring
is why the code is shaped the way it is.

Advisory (spec.md's check inventory): a break in a doc run is common (an
ordinary second sentence), and only some are splices. Nothing catches a
splice mechanically otherwise — the compiler/doc-renderer is happy, and
the text ends up rendered under whichever declaration ends up last.

Ported from `ratect`'s `tools/spliced-docs.py` (Rust) and Project B's
`tools/spliced-docs.py` (Swift) — same author, both Apache-2.0/relicensed
prior art for this consolidation — onto the *union* of their evidence
rules (spec.md's "stronger variant" applied to both languages, not just
Swift's). No adapter interface is introduced for this — spec.md defers
that design; the two languages are handled by two concrete, independent
functions.

Only `undocumented` mode runs by default. `unknown`'s weaker rule ("names a
backtick term that resolves to nothing") fires on ordinary technical prose
almost as often as it fires on a real splice, on a codebase with dense,
cross-referencing doc comments (confirmed against a real Rust project: 15
`unknown` findings to 1 `undocumented` finding, all 15 false positives) —
so it is opt-in via `modes` once that noise level is checked to be
acceptable for a given project.

The break rule leans on each source codebase's own house style (a
summary, a blank `///`, then detail): that is what makes a summary
mid-run mean two documents. Evidence beyond the break is required because
a break alone is far too noisy.

Not diff-scoped: every tracked `*.rs`/`*.swift` file is swept, matching the
source tools' whole-tree behaviour — a splice can predate the diff being
checked.

`SWIFT_DECL_RE` and `RUST_ITEM_RE` are the "what does this repository
declare" answer `judgment-agent` imports rather than redefines, as
`check-citations` does `SWIFT_DECL_RE` — see `check_citations.py` for why
that answer must not exist twice.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from ..config import ConfigError
from ..git import tracked_files
from ..lines import git_lines, tracked_text
from ..runner import Finding, register_check

NAME = "spliced-docs"

MODE_UNDOCUMENTED = "spliced-docs-undocumented"
MODE_UNKNOWN = "spliced-docs-unknown"

# Config-facing mode names (`claims.toml`'s `modes = [...]`), distinct from
# the `MODE_*` finding-mode strings above.
UNDOCUMENTED = "undocumented"
UNKNOWN = "unknown"
KNOWN_MODES = frozenset({UNDOCUMENTED, UNKNOWN})
DEFAULT_MODES = frozenset({UNDOCUMENTED})

DOC_RE = re.compile(r"^\s*///")


def _enabled_modes(config: Mapping[str, object]) -> frozenset[str]:
    """This check's own `modes` list, from its `claims.toml` section —
    default `{"undocumented"}` (see the module docstring's opt-in note).

    Raises `ConfigError` naming any mode that isn't `undocumented` or
    `unknown`, rather than silently ignoring it or letting it pass through
    to fail confusingly later.
    """

    configured = config.get("modes")
    if configured is None:
        return DEFAULT_MODES
    # A one-character typo away from a list (`modes = "unknown"` instead of
    # `modes = ["unknown"]`) — treated as a bare iterable of characters
    # instead, per-character `ConfigError`s would mask the actual mistake.
    # Mirrors `exclude_patterns`'s own guard against the same typo shape.
    if isinstance(configured, str):
        configured = [configured]
    if not isinstance(configured, (list, tuple, set, frozenset)):
        raise ConfigError(f"[{NAME}] modes must be a list of strings, got {configured!r}")
    modes = frozenset(configured)  # type: ignore[arg-type]
    bad = modes - KNOWN_MODES
    if bad:
        raise ConfigError(
            f"[{NAME}] modes: {sorted(bad, key=str)[0]!r} is not a known mode "
            f'(expected "undocumented" or "unknown")'
        )
    return modes


def _finding(file: str, line: int, mode: str, names: list[str], where: str) -> Finding:
    quoted = ", ".join(f"`{name}`" for name in names)
    return Finding(
        file=file,
        line=line,
        message=f"stranded doc comment names {quoted}, {where}",
        mode=mode,
        gate=False,
    )


def _emit(
    rel: str,
    line_no: int,
    named: frozenset[str],
    bare: dict[str, set[str]],
    all_names: set[str],
    enabled_modes: frozenset[str],
) -> list[Finding]:
    findings: list[Finding] = []
    if UNDOCUMENTED in enabled_modes:
        owners = sorted(name for name, idents in bare.items() if named & idents)
        if owners:
            findings.append(
                _finding(rel, line_no, MODE_UNDOCUMENTED, owners, "undocumented in this file")
            )
    if UNKNOWN in enabled_modes:
        unknown = sorted(name for name in named if name not in all_names)
        if unknown:
            findings.append(
                _finding(rel, line_no, MODE_UNKNOWN, unknown, "resolves to nothing in the repo")
            )
    return findings


# Ignores only double-quoted strings, escapes included: a bracket inside a
# char literal, raw string or string spanning lines still counts.
DOUBLE_QUOTED_RE = re.compile(r'"(?:[^"\\]|\\.)*"')


def _attribute_lines(
    lines: list[str],
    start_re: re.Pattern[str],
    opener: str,
    closer: str,
    item_re: re.Pattern[str],
) -> set[int]:
    """Every index in `lines` that is part of an attribute.

    An attribute runs from a line `start_re` matches through the line where
    its first `opener` is closed again, however many lines that spans;
    whatever follows on that line, such as a signature's own `(`, is not
    counted. A closing line with code after the attribute holds an item,
    so is not attribute. A line `item_re` or `DOC_RE` matches ends an
    attribute unbalanced, so a miscounted bracket cannot carry it over the
    items or doc comments below.
    """

    inside: set[int] = set()
    i = 0
    while i < len(lines):
        if not start_re.match(lines[i]):
            i += 1
            continue
        first = i
        depth = 0
        while True:
            code = DOUBLE_QUOTED_RE.sub("", lines[i])
            rest = ""
            for at, char in enumerate(code):
                if char == opener:
                    depth += 1
                elif char == closer:
                    depth -= 1
                    if depth == 0:
                        rest = code[at + 1 :].strip()
                        break
            if i == first or not rest or rest.startswith("//"):
                inside.add(i)
            i += 1
            if depth <= 0 or i == len(lines):
                break
            if item_re.match(lines[i]) or DOC_RE.match(lines[i]):
                break
    return inside


# --- Rust -------------------------------------------------------------

RUST_ATTR_RE = re.compile(r"^\s*#\[")
# Generic parameters or arguments, `<…>`, nested three deep; `->` inside
# them, `Fn() -> u8`, closes nothing.
_RUST_GENERICS = r"<(?:->|[^<>]|<(?:->|[^<>]|<(?:->|[^<>])*>)*>)*>"
# An item's `kind` and `name`. An `impl` names its implementing type, the
# last path segment of the type after `for`, with the trait it implements
# as `trait`, or of the type after `impl`/`impl<…>` when there is no `for`.
# Only the line before any `{` is read for `for`. One whose type after `for`
# has no name, `(A, B)`, matches nothing.
RUST_ITEM_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+|unsafe\s+|const\s+)*"
    r"(?P<kind>fn|struct|enum|trait|type|mod|impl)"
    rf"(?:(?<=impl)(?:\s*{_RUST_GENERICS}\s*|\s+)"
    r"(?:(?P<trait>[^\s{][^{]*?)\s+for\s+|(?![^{]*\sfor\s))"
    r"&?(?:'[A-Za-z_]\w*\s+)?(?:mut\s+)?(?:dyn\s+)?(?:[A-Za-z_][A-Za-z_0-9]*::)*"
    r"|(?<!impl)\s+)"
    r"(?P<name>[A-Za-z_][A-Za-z_0-9]*)"
)
RUST_SUMMARY_RE = re.compile(
    r"^\s*/// (?:The|A|An) \S|^\s*/// [A-Z][a-z]+(?:s|es) [`\w]"
)
RUST_PARAM_RE = re.compile(r"^\s*(?:mut\s+)?([a-z_][a-z_0-9]*)\s*:")
RUST_BACKTICKED = re.compile(r"`([A-Za-z_][A-Za-z_0-9]*)`")
# `//` not followed by `/` or `!`, or four or more slashes: rustdoc reads
# both as plain comments, so neither detaches a doc comment from its item.
RUST_PLAIN_COMMENT_RE = re.compile(r"^\s*(?://(?:[^/!]|$)|////)")


def _rust_runs(lines: list[str]):
    """Every `(doc_start, doc_end)` in `lines`, doc lines only."""

    i = 0
    while i < len(lines):
        if not DOC_RE.match(lines[i]):
            i += 1
            continue
        start = i
        while i < len(lines) and DOC_RE.match(lines[i]):
            i += 1
        yield start, i


# `/**` opening an outer block doc. `/**/` and `/***…` are plain comments.
RUST_BLOCK_DOC_RE = re.compile(r"^\s*/\*\*(?![*/])")
# `//!` or `/*!`: an inner doc, which documents the enclosing module.
RUST_INNER_DOC_RE = re.compile(r"^\s*/[/*]!")


def _rust_documented(
    lines: list[str], code: list[tuple[bool, str]], i: int, attributes: set[int]
) -> bool:
    """Whether the item on line `i` has a `///` or `/** */` doc comment above
    it, with only attributes, plain comments and blank lines between.

    `code` is `_rust_code(lines)`: a line with no code left in it is a
    comment or blank, and skipped unless it opens a doc comment outside
    any other.
    """

    for above in range(i - 1, -1, -1):
        line = lines[above]
        opens_in_code, rest = code[above]
        if rest.strip():
            if above in attributes:
                continue
            return False
        if not opens_in_code:
            continue
        if RUST_INNER_DOC_RE.match(line):
            return False
        if RUST_BLOCK_DOC_RE.match(line) or (
            DOC_RE.match(line) and not RUST_PLAIN_COMMENT_RE.match(line)
        ):
            return True
    return False


# A raw string's opening, `r"`, `r#"` or `br##"`, not the tail of an
# identifier such as `for"`.
RUST_RAW_OPEN_RE = re.compile(r"(?<![A-Za-z0-9_])b?r(#*)\"")
# A char or byte literal: `'{'`, `b'{'`, `'\''`, `'\u{7b}'`. A lifetime,
# `'a`, has no closing quote one character on, so never matches.
RUST_CHAR_RE = re.compile(r"'(?:[^'\\]|\\(?:x[0-9A-Fa-f]{2}|u\{[0-9A-Fa-f]+\}|.))'")


def _rust_code(lines: list[str]):
    """Each of `lines` with its comments, strings and char literals removed,
    carrying an open string or block comment from one line to the next, as
    `(opens_in_code, code)`: `opens_in_code` is false for a line that starts
    inside a string or block comment.

    Not a full lexer: enough that a brace count over what is left balances.
    """

    raw_close = None  # the `"#…` that ends the raw string we are inside
    in_string = False
    comment_depth = 0
    for line in lines:
        opens_in_code = raw_close is None and not in_string and not comment_depth
        code = []
        j = 0
        while j < len(line):
            if raw_close is not None:
                end = line.find(raw_close, j)
                if end < 0:
                    break
                j = end + len(raw_close)
                raw_close = None
            elif in_string:
                if line[j] == "\\":
                    j += 2
                    continue
                in_string = line[j] != '"'
                j += 1
            elif comment_depth:
                if line.startswith("/*", j):
                    comment_depth += 1
                    j += 2
                elif line.startswith("*/", j):
                    comment_depth -= 1
                    j += 2
                else:
                    j += 1
            elif line.startswith("//", j):
                break
            elif line.startswith("/*", j):
                comment_depth = 1
                j += 2
            elif raw := RUST_RAW_OPEN_RE.match(line, j):
                raw_close = '"' + raw.group(1)
                j = raw.end()
            elif line[j] == '"':
                in_string = True
                j += 1
            elif char := RUST_CHAR_RE.match(line, j):
                j = char.end()
            else:
                code.append(line[j])
                j += 1
        yield opens_in_code, "".join(code)


def _rust_fn_local_lines(lines: list[str]) -> set[int]:
    """Every index in `lines` that starts inside a `fn` body, however deep.

    A rough brace count over `_rust_code`: the first `{` after a `fn` item
    opens its body, and a `}` closing a block opened before it (a bodiless
    trait method's trait closing) cancels that. A `{` in the signature is an
    ordinary block when it sits inside a `(` or `[` opened since the item, or
    straight after a `<`; one after a comma in generics, `Foo<A, { N }>`, still
    opens the body.
    """

    local: set[int] = set()
    fn_bodies: list[bool] = []
    fn_pending = False
    signature_base = 0  # len(fn_bodies) when the pending `fn` item began
    groups = 0  # `(` and `[` left open since then
    previous = ""  # the last non-space code character
    for i, (_, code) in enumerate(_rust_code(lines)):
        if any(fn_bodies):
            local.add(i)
        matched = RUST_ITEM_RE.match(code)
        if matched and matched.group("kind") == "fn":
            fn_pending = True
            signature_base = len(fn_bodies)
            groups = 0
        for char in code:
            if char in "([":
                groups += 1
            elif char in ")]":
                groups = max(groups - 1, 0)
            elif char == "{":
                opens_body = fn_pending and not groups and previous != "<"
                fn_bodies.append(opens_body)
                if opens_body:
                    fn_pending = False
            elif char == "}":
                if len(fn_bodies) <= signature_base:
                    fn_pending = False
                if fn_bodies:
                    fn_bodies.pop()
            if not char.isspace():
                previous = char
    return local


def _rust_bare_items(lines: list[str]) -> dict[str, set[str]]:
    """Undocumented declarations in `lines`, as `name -> {name, param names}`.

    By *name*, not by position: a trait method is documented once on the
    trait and appears bare on every impl, which is not a stranding. An item
    inside a `fn` body is never bare: rustdoc does not render it.
    """

    attributes = _attribute_lines(lines, RUST_ATTR_RE, "[", "]", RUST_ITEM_RE)
    code: list[tuple[bool, str]] = list(_rust_code(lines))
    documented_names = set()
    for i, line in enumerate(lines):
        matched = RUST_ITEM_RE.match(line)
        if matched and _rust_documented(lines, code, i, attributes):
            documented_names.add(matched.group("name"))

    local = _rust_fn_local_lines(lines)
    bare: dict[str, set[str]] = {}
    for i, line in enumerate(lines):
        matched = RUST_ITEM_RE.match(line)
        if not matched or i in local:
            continue
        name = matched.group("name")
        if name in documented_names:
            continue
        idents = {name}
        for follow in lines[i : i + 12]:
            param = RUST_PARAM_RE.match(follow)
            if param:
                idents.add(param.group(1))
            if ")" in follow and follow.strip() != "(":
                break
        bare[name] = idents
    return bare


def _rust_all_names(all_lines: list[list[str]]) -> set[str]:
    names = set()
    for lines in all_lines:
        for line in lines:
            matched = RUST_ITEM_RE.match(line)
            if matched:
                names.add(matched.group("name"))
    return names


def _rust_breaks(lines: list[str]):
    """Every `(break_line, {backticked names above it})` in `lines`."""

    for start, end in _rust_runs(lines):
        for i in range(start + 1, end):
            previous = lines[i - 1].rstrip()
            if not previous.endswith(".") or not RUST_SUMMARY_RE.match(lines[i]):
                continue
            stranded = " ".join(lines[start:i])
            named = frozenset(RUST_BACKTICKED.findall(stranded))
            if named:
                yield i + 1, named


def _check_rust(repo_root: Path, enabled_modes: frozenset[str]) -> list[Finding]:
    files = {
        rel: git_lines(tracked_text(repo_root / rel, errors="replace"))
        for rel in tracked_files(repo_root, "*.rs")
    }
    all_names = _rust_all_names(list(files.values())) if UNKNOWN in enabled_modes else set()

    findings: list[Finding] = []
    for rel, lines in sorted(files.items()):
        if not lines:
            continue
        bare = _rust_bare_items(lines) if UNDOCUMENTED in enabled_modes else {}
        for line_no, named in _rust_breaks(lines):
            findings.extend(_emit(rel, line_no, named, bare, all_names, enabled_modes))
    return findings


# --- Swift --------------------------------------------------------------

SWIFT_ATTR_RE = re.compile(r"^\s*@")
# Only an attribute with arguments, `@available(`, can span lines; a line
# such as `@objc func foo(` opens a signature, not an attribute.
SWIFT_ATTR_ARGS_RE = re.compile(r"^\s*@[A-Za-z_][A-Za-z_0-9]*\(")
# Ported from Project B's `tools/claims.py::DECL_RE` — the one answer to "what
# is a declaration" shared by that repo's own spliced-docs and check-citations
# tools, kept as one regex there specifically to avoid two answers drifting.
SWIFT_DECL_RE = re.compile(
    r"^\s*(?:(?:public|internal|private|fileprivate|open)(?:\(set\))?\s+)*"
    r"(?:(?:static|class|final|mutating|nonmutating|override|convenience|"
    r"required|lazy|weak|indirect)\s+)*"
    r"(?:func|var|let|struct|class|enum|protocol|actor|typealias|case|init)"
    r"\s+([A-Za-z_][A-Za-z_0-9]*)"
)
SWIFT_SUMMARY_RE = re.compile(
    r"^\s*/// (?:The|A|An|Whether|Why|What|Where|One|Every)\s\S"
    r"|^\s*/// [A-Z][a-z]+(?:s|es)\s[`\w]"
)
SWIFT_SENTENCE_END_RE = re.compile(r"[.!?][)`\"']?\s*$")
# Ported from Project B's `tools/spliced-docs.py::NAME_RE` — deliberately has
# no closing-backtick requirement (unlike Rust's `RUST_BACKTICKED`), so a
# malformed/unclosed backtick reference still names its declaration.
SWIFT_NAME_RE = re.compile(r"`([A-Za-z_][A-Za-z_0-9]*)")


def _swift_declarations(lines: list[str]):
    """Every `(line_index, name, documented)` declaration in `lines`."""

    found = []
    documented = False
    attributes = _attribute_lines(lines, SWIFT_ATTR_ARGS_RE, "(", ")", SWIFT_DECL_RE)
    for i, line in enumerate(lines):
        if DOC_RE.match(line):
            documented = True
            continue
        if SWIFT_ATTR_RE.match(line) or i in attributes or not line.strip():
            continue
        match = SWIFT_DECL_RE.match(line)
        if match:
            found.append((i, match.group(1), documented))
        documented = False
    return found


def _swift_runs(lines: list[str]):
    """Every contiguous block of `///` lines, as `(start, end)` exclusive."""

    start = None
    for i, line in enumerate(lines):
        if DOC_RE.match(line):
            if start is None:
                start = i
        elif start is not None:
            yield start, i
            start = None
    if start is not None:
        yield start, len(lines)


def _swift_breaks(lines: list[str]):
    """Every `(break_line, {backticked names above it})` in `lines`."""

    for start, end in _swift_runs(lines):
        for i in range(start + 1, end):
            previous = lines[i - 1]
            if not SWIFT_SENTENCE_END_RE.search(previous) or previous.strip() == "///":
                continue
            if not SWIFT_SUMMARY_RE.match(lines[i]):
                continue
            stranded = " ".join(lines[start:i])
            named = frozenset(SWIFT_NAME_RE.findall(stranded))
            if named:
                yield i + 1, named


def _check_swift(repo_root: Path, enabled_modes: frozenset[str]) -> list[Finding]:
    files = {
        rel: git_lines(tracked_text(repo_root / rel, errors="replace"))
        for rel in tracked_files(repo_root, "*.swift")
    }

    declarations = {rel: _swift_declarations(lines) for rel, lines in files.items()}

    all_names: set[str] = set()
    if UNKNOWN in enabled_modes:
        for found in declarations.values():
            for _, name, _ in found:
                all_names.add(name)

    findings: list[Finding] = []
    for rel, lines in sorted(files.items()):
        if not lines:
            continue
        bare = (
            {name: {name} for _, name, documented in declarations[rel] if not documented}
            if UNDOCUMENTED in enabled_modes
            else {}
        )
        for line_no, named in _swift_breaks(lines):
            findings.extend(_emit(rel, line_no, named, bare, all_names, enabled_modes))
    return findings


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    enabled_modes = _enabled_modes(config)
    return _check_rust(repo_root, enabled_modes) + _check_swift(repo_root, enabled_modes)


register_check(NAME, check)
