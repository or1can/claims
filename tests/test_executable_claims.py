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

"""Tests for the `executable-claims` check: `claims.checks.executable_claims`.

Exercises the shared `run(repo_root, diff_range, config)` seam against a
fixture git repo, asserting on the returned `Finding` list — see spec.md's
Testing Decisions. Ported from `verify-docs.py`'s own test suite
(Apache-2.0 prior art), adapted for the new shell-execution and exit-code
requirements this check adds.
"""

from __future__ import annotations

import contextlib
import io
import os
import shlex
import subprocess
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path

from claims.checks.executable_claims import NAME, check
from claims.cli import main
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


def marked(command: str, body: str) -> str:
    return f"<!-- verify: {command} -->\n```\n{body}\n```\n"


def _toml_string(value: str) -> str:
    # Mirrors executable_claims._toml_string: TOML basic-string escaping,
    # since a `shlex.quote`-produced command routinely contains a single
    # quote (which a TOML literal string can't represent) and sometimes a
    # double quote (`shlex.quote`'s own `'"'"'` escaping for an embedded
    # single quote).
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def grant(repo_root: Path, *, allow: Sequence[str] = (), deny: Sequence[str] = ()) -> None:
    """Writes `claims.local.toml` granting/denying exact commands — the
    fixture every test exercising real execution needs since ticket #15's
    deny-by-default local grant.
    """

    lines = ["[executable-claims]"]
    if allow:
        lines.append("allowed = [" + ", ".join(_toml_string(c) for c in allow) + "]")
    if deny:
        lines.append("denied = [" + ", ".join(_toml_string(c) for c in deny) + "]")
    (repo_root / "claims.local.toml").write_text("\n".join(lines) + "\n")


def nested_marker_example() -> str:
    """Documentation illustrating the marker syntax itself — the marker
    line is inside an already-open fence, not directly above one."""

    return (
        "Example of the marker syntax:\n"
        "\n"
        "```\n"
        "<!-- verify: some-command -->\n"
        "```\n"
        "\n"
        "```\n"
        "expected output shown here\n"
        "```\n"
    )


def python(source: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(source)}"


def echo(text: str) -> str:
    return python(f"import sys; sys.stdout.write({text!r})")


class ExecutableClaimsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path, *, allow: Sequence[str] = ()) -> list[Finding]:
        if allow:
            grant(repo_root, allow=allow)
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_config(
        self, repo_root: Path, claims_toml: str, *, allow: Sequence[str] = ()
    ) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        if allow:
            grant(repo_root, allow=allow)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_an_excluded_path_is_skipped_entirely(self) -> None:
        with Repo() as repo:
            repo.write("skip.md", "just prose, no markers here\n")
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["skip.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_exclude_does_not_affect_a_non_matching_path(self) -> None:
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("keep.md", marked(command, "hello"))
            repo.write("skip.md", "just prose, no markers here\n")
            findings = self._findings_with_config(
                repo.root,
                '[executable-claims]\nexclude = ["skip.md"]\n',
                allow=[command],
            )
        self.assertEqual(findings, [])

    def test_excluding_one_alias_of_a_symlinked_pair_excludes_both(self) -> None:
        # AGENTS.md/CLAUDE.md is this file's own documented symlink
        # convention (the `seen`-by-real-path dedup exists because of it).
        # Naming only one alias in `exclude` must not leave its content
        # checked, and reported, under the other alias instead.
        with Repo() as repo:
            repo.write(
                "AGENTS.md", "<!-- verify: false -->\n```\nnever matches\n```\n"
            )
            os.symlink("AGENTS.md", repo.root / "CLAUDE.md")
            subprocess.run(
                ["git", "-C", str(repo.root), "add", "CLAUDE.md"], check=True
            )
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["AGENTS.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_an_unrelated_exclusion_does_not_mask_a_real_zero_marker_failure(
        self,
    ) -> None:
        # `docs/history.md` opting out of the sweep must not be why the
        # gate goes quiet about `real.md` genuinely carrying no marker —
        # only excluding *everything* earns the exception.
        with Repo() as repo:
            repo.write("docs/history.md", "historical notes, no markers\n")
            repo.write("real.md", "no marker in this file either\n")
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["docs/history.md"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("no verify markers found", findings[0].message)

    def test_a_command_exceeding_the_configured_timeout_is_advisory(self) -> None:
        command = python("import time; time.sleep(1)")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "irrelevant"))
            findings = self._findings_with_config(
                repo.root, "[executable-claims]\ntimeout = 0.05\n", allow=[command]
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("timed out after 0.05s", findings[0].message)
        self.assertFalse(findings[0].gate)

    def test_a_non_numeric_timeout_config_is_a_clear_crash_finding(self) -> None:
        # `runner.run()` catches any exception a check raises and turns it
        # into one gate finding (see its own docstring) — asserting the
        # message names `ConfigError` and the bad value pins this as that
        # documented path, not an opaque `TypeError` from `subprocess.run`.
        with Repo() as repo:
            repo.write("doc.md", marked(echo("hello\n"), "hello"))
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\ntimeout = "30"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("timeout must be a number", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_boolean_timeout_config_is_a_clear_crash_finding(self) -> None:
        # `bool` is an `int` subclass in Python, so a plain
        # `isinstance(value, (int, float))` check would silently accept
        # `timeout = true` and pass it straight to `subprocess.run` as a
        # 1-second timeout — misreporting any slower command as an
        # advisory timeout instead of rejecting the config outright.
        with Repo() as repo:
            repo.write("doc.md", marked(echo("hello\n"), "hello"))
            findings = self._findings_with_config(
                repo.root, "[executable-claims]\ntimeout = true\n"
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("timeout must be a number", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_true_claim_passes(self) -> None:
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_false_claim_with_mismatched_output_fails(self) -> None:
        command = echo("actual\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "documented"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "doc.md:1")
        self.assertTrue(findings[0].gate)

    def test_a_false_claim_with_matching_text_but_nonzero_exit_fails(self) -> None:
        command = python("import sys; sys.stdout.write('hello'); sys.exit(1)")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(len(findings), 1)
        self.assertIn("exited 1", findings[0].message)

    def test_a_malformed_marker_not_above_a_fenced_block_fails(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "<!-- verify: some-command -->\n\nordinary prose\n")
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("not above a fenced block", findings[0].message)

    def test_a_marker_shown_as_literal_text_inside_a_fence_is_not_live(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", nested_marker_example())
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("no verify markers found", findings[0].message)

    def test_a_nested_marker_example_does_not_interfere_with_a_real_marker(self) -> None:
        command = echo("hello\n")
        doc = nested_marker_example() + "\n" + marked(command, "hello")
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_marker_example_nested_in_a_longer_outer_fence_is_not_live(self) -> None:
        # CommonMark's real nesting rule: a fence only closes on a
        # same-or-longer run of backticks. A 3-backtick example nested
        # inside a 4-backtick outer fence is the documented way to show
        # fence syntax itself — the inner ``` lines are literal content,
        # not real delimiters, so the marker between them must stay dead.
        doc = (
            "Example of the marker syntax, inside a longer outer fence so\n"
            "its own ``` lines aren't mistaken for real ones:\n"
            "\n"
            "````\n"
            "```\n"
            "<!-- verify: echo nested-should-not-run -->\n"
            "```\n"
            "\n"
            "```\n"
            "expected output shown here\n"
            "```\n"
            "````\n"
        )
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("no verify markers found", findings[0].message)

    def test_a_live_markers_own_block_may_nest_a_fenced_example(self) -> None:
        # The documented output legitimately contains a fenced block of
        # its own (e.g. output that is itself markdown) — wrapped in a
        # longer outer fence, per CommonMark's own nesting convention.
        # The nested lines must not truncate the captured expected block.
        command = echo("```\ninner\n```\n")
        doc = f"<!-- verify: {command} -->\n" "````\n" "```\n" "inner\n" "```\n" "````\n"
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_an_unclosed_fenced_block_is_reported_not_silently_mishandled(self) -> None:
        # A genuinely live marker (its own fence pair closes cleanly)
        # still runs and passes on its own merits; a separate, later,
        # never-closed fence elsewhere in the file must still be a loud
        # finding of its own, not silently swallow anything before it.
        command = echo("hello\n")
        doc = marked(command, "hello") + "```\n"
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(len(findings), 1)
        self.assertIn("never closed", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_sweep_finding_zero_markers_is_a_failure(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "just prose, no markers here\n")
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].gate)

    def test_a_semicolon_chained_marker_is_rejected_without_running(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("exit 1; " + echo("hello\n"), "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("chains commands via `;`", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_double_ampersand_chained_marker_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("true && " + echo("hello\n"), "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("chains commands via `&&`", findings[0].message)

    def test_a_double_pipe_chained_marker_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("false || " + echo("hello\n"), "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("chains commands via `||`", findings[0].message)

    def test_a_bare_ampersand_backgrounded_marker_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("true & " + echo("hello\n"), "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("chains commands via `&`", findings[0].message)

    def test_an_output_redirect_marker_is_rejected(self) -> None:
        # Redirecting output writes to an arbitrary file — exactly the
        # "more than the one thing pinned" this blocklist exists to stop,
        # not merely a chained command.
        with Repo() as repo:
            repo.write("doc.md", marked("echo hi > /tmp/claims-test-marker-out", "hi"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("redirects file I/O via `>`", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_an_input_redirect_marker_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("cat < /dev/null", ""))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("redirects file I/O via `<`", findings[0].message)

    def test_a_leading_redirect_before_the_command_is_still_rejected(self) -> None:
        # `> file cmd` is valid shell syntax — the redirect can precede the
        # command name it applies to, not just follow it.
        with Repo() as repo:
            repo.write("doc.md", marked("> /tmp/claims-test-marker-out echo hi", "hi"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("redirects file I/O via `>`", findings[0].message)

    def test_a_combined_stdout_stderr_pipe_still_trips_the_pipe_blocklist(self) -> None:
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} |& grep -c b"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "1"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `grep`", findings[0].message)

    def test_a_command_substitution_marker_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("echo $(true)", "true"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("substitutes a command", findings[0].message)

    def test_a_backtick_substitution_marker_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("echo `true`", "true"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("substitutes a command", findings[0].message)

    def test_a_double_quoted_substitution_is_still_rejected(self) -> None:
        # Unlike single quotes, double quotes don't suppress `$(...)` —
        # `echo "$(cat secrets)"` genuinely expands. A masking approach
        # that treats every quoted span as inert would miss exactly this.
        with Repo() as repo:
            repo.write("doc.md", marked('echo "$(true)"', "true"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("substitutes a command", findings[0].message)

    def test_a_single_quoted_dollar_paren_is_not_a_real_substitution(self) -> None:
        # Single quotes fully suppress `$(...)` — the literal text
        # '$(not a substitution)' is inert prose, not a real one.
        command = echo("$(not a substitution)")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "$(not a substitution)"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_semicolon_inside_a_python_one_liner_is_not_chaining(self) -> None:
        # The exact false positive naive substring matching hits: the `;`
        # is part of the quoted Python source, not a real shell separator.
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_find_exec_escaped_semicolon_is_not_chaining(self) -> None:
        # `find ... -exec ... \;` is find's own single-command terminator
        # syntax, not a shell-level chain — a common, legitimate idiom.
        command = r"find . -name f.txt -exec cat {} \;"
        with Repo() as repo:
            repo.write("f.txt", "hello\n")
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_quoted_tool_name_still_trips_the_pipe_blocklist(self) -> None:
        # Quoting only removes the quote characters at the shell level —
        # `'grep'` still runs grep. A check that just strips quoted spans
        # to a placeholder before checking the pipe segment's head word
        # would miss this; tokenizing (which reduces `'grep'` to the word
        # `grep`, same as the shell does) must not.
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} | 'grep' -c b"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "1"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `grep`", findings[0].message)

    def test_a_backslash_escaped_tool_name_still_trips_the_pipe_blocklist(self) -> None:
        # `\grep` is a common way to bypass a shell alias/function named
        # `grep` — the shell still runs the real `grep` binary. Replacing
        # the whole escape with a placeholder (rather than keeping the
        # escaped character's own identity) would corrupt this into
        # something that no longer matches the tool blocklist at all.
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} | \\grep -c b"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "1"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `grep`", findings[0].message)

    def test_a_subshell_wrapped_tool_still_trips_the_pipe_blocklist(self) -> None:
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} | (grep -c b)"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "1"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `grep`", findings[0].message)

    def test_an_unparseable_command_is_rejected_rather_than_run_unchecked(self) -> None:
        # An unbalanced quote means the blocklist can't be checked at all
        # — this check's whole job is deciding whether a command is safe
        # to run, so "couldn't tell" must reject, not wave it through.
        with Repo() as repo:
            repo.write("doc.md", marked("echo 'unbalanced", "irrelevant"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("could not be parsed as a shell command", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_marker_piping_through_grep_past_the_first_segment_is_rejected(
        self,
    ) -> None:
        # The exact shape that defeated a prefix-only check upstream: the
        # command as a whole doesn't start with `grep`, so a
        # `command.startswith(...)` test alone would miss it.
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} | grep -c b"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "1"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `grep`", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_marker_piping_through_sed_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked(f"{echo('a')} | sed 's/a/b/'", "b"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `sed`", findings[0].message)

    def test_a_marker_piping_through_awk_is_rejected(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked(f"{echo('a b')} | awk '{{print $1}}'", "a"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("pipes through `awk`", findings[0].message)

    def test_head_is_not_in_the_blocklist(self) -> None:
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} | head -1"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "a"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_permitted_prefixes_rejects_a_non_matching_command(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked(echo("hello\n"), "hello"))
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\npermitted_prefixes = ["npm test"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("does not match a configured permitted_prefixes entry", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_permitted_prefixes_allows_a_matching_command(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked("true", ""))
            findings = self._findings_with_config(
                repo.root,
                '[executable-claims]\npermitted_prefixes = ["true"]\n',
                allow=["true"],
            )
        self.assertEqual(findings, [])

    def test_matching_permitted_prefixes_alone_does_not_satisfy_the_local_grant(
        self,
    ) -> None:
        # `permitted_prefixes` narrows which commands may run; it isn't
        # itself the trust boundary ticket #15 introduced — a committed
        # `claims.toml` entry must not be sufficient to run anything.
        with Repo() as repo:
            repo.write("doc.md", marked("true", ""))
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\npermitted_prefixes = ["true"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("has no local grant", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_permitted_prefixes_does_not_override_the_blocklist(self) -> None:
        # A command matching a configured prefix is still checked against
        # the fixed blocklist first — `permitted_prefixes` narrows which
        # commands may run, it doesn't re-permit an otherwise-forbidden
        # construct.
        with Repo() as repo:
            repo.write("doc.md", marked("true; " + echo("hello\n"), "hello"))
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\npermitted_prefixes = ["true"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("chains commands via `;`", findings[0].message)

    def test_no_permitted_prefixes_config_means_blocklist_only(self) -> None:
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_the_command_runs_through_a_shell_so_a_pipe_works(self) -> None:
        write_three_lines = python(
            'import sys; sys.stdout.write(chr(10).join(["a", "b", "c"]) + chr(10))'
        )
        command = f"{write_three_lines} | tail -1"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "c"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_the_prompt_line_of_a_transcript_is_not_compared(self) -> None:
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "$ some-command\nhello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_tracked_filename_containing_a_space_is_still_swept(self) -> None:
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("release notes.md", marked(command, "hello"))
            findings = self._findings(repo.root, allow=[command])
        self.assertEqual(findings, [])

    def test_a_command_with_no_local_grant_is_a_gate_finding_and_never_runs(self) -> None:
        # Deny by default (ticket #15): a command clearing the blocklist
        # still may not run without an exact-string grant in
        # claims.local.toml. No claims.local.toml exists in this fixture
        # at all — the same as a fresh checkout — not merely an empty one.
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].gate)
        self.assertIn(f"`{command}` has no local grant", findings[0].message)
        self.assertIn("claims.local.toml", findings[0].message)
        self.assertIn(f"allowed = [{_toml_string(command)}]", findings[0].message)

    def test_a_denied_command_is_skipped_as_an_advisory_not_silence(self) -> None:
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            grant(repo.root, deny=[command])
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].gate)
        self.assertIn("is denied in claims.local.toml", findings[0].message)

    def test_a_one_character_different_command_is_not_matched_by_a_prior_grant(
        self,
    ) -> None:
        granted = echo("hello\n")
        different = echo("hellox\n")
        with Repo() as repo:
            repo.write("doc.md", marked(different, "hellox"))
            grant(repo.root, allow=[granted])
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].gate)
        self.assertIn("has no local grant", findings[0].message)

    def test_a_tracked_local_grant_file_is_ignored_not_honored(self) -> None:
        # `.gitignore` only stops git from ever *adding* claims.local.toml
        # — it does nothing once one is already tracked, e.g. committed by
        # an attacker's own PR alongside a planted marker specifically to
        # defeat this gate. A tracked grant file must not authorize
        # anything: its own presence is the finding, not a free pass.
        command = echo("hello\n")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            repo.write(
                "claims.local.toml", f'[executable-claims]\nallowed = ["{command}"]\n'
            )
            findings = self._findings(repo.root)
        messages = [f.message for f in findings]
        self.assertTrue(any("is tracked by git" in m for m in messages))
        self.assertTrue(any("has no local grant" in m for m in messages))
        self.assertTrue(all(f.gate for f in findings))

    def test_an_ungranted_command_containing_a_double_quote_escapes_cleanly(self) -> None:
        # A `shlex.quote`-produced command embedding a single quote inserts
        # literal double quotes via `'"'"'` — the remediation TOML snippet
        # must escape those, not emit invalid TOML.
        command = python("it's a test")
        self.assertIn('"', command)
        with Repo() as repo:
            repo.write("doc.md", marked(command, "irrelevant"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        message = findings[0].message
        self.assertIn(f"`{command}`", message)
        expected_literal = '"' + command.replace("\\", "\\\\").replace('"', '\\"') + '"'
        self.assertIn(f"allowed = [{expected_literal}]", message)


class ExecutableClaimsCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_end_to_end_via_the_cli(self) -> None:
        true_command = echo("hello\n")
        false_command = echo("actual\n")
        with Repo() as repo:
            repo.write("true.md", marked(true_command, "hello"))
            repo.write("false.md", marked(false_command, "documented"))
            repo.write("malformed.md", "<!-- verify: some-command -->\n\nprose\n")
            grant(repo.root, allow=[true_command, false_command])

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--repo-root", str(repo.root)])
            output = out.getvalue()

        self.assertEqual(code, 1)
        self.assertIn("false.md:1", output)
        self.assertIn("malformed.md:1", output)
        self.assertNotIn("true.md", output)


if __name__ == "__main__":
    unittest.main()
