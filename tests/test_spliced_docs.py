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

"""Tests for the `spliced-docs` check: `claims.checks.spliced_docs`.

Exercises the shared `run(repo_root, diff_range, config)` seam against a
fixture git repo — see spec.md's Testing Decisions — and, for attributes
spanning several lines, `_rust_bare_items` and `_swift_declarations`
directly. Ported from `ratect`'s
and Project B's own `tools/spliced-docs.py` (Rust, Swift; both Apache-2.0/
relicensed prior art).
"""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from claims.checks.spliced_docs import (
    MODE_UNDOCUMENTED,
    MODE_UNKNOWN,
    NAME,
    _rust_bare_items,
    _swift_declarations,
    check,
)
from claims.cli import main
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo

# A documented item under a `#[derive]` and a multi-line `#[serde]`, with a
# splice elsewhere naming it, so only a misread attribute would report it.
RUST_MULTILINE_ATTR: str = (
    "/// The parsed config.\n"
    "#[derive(Debug, Deserialize)]\n"
    "#[serde(\n"
    "    rename_all = \"kebab-case\",\n"
    "    deny_unknown_fields,\n"
    ")]\n"
    "pub struct Foo {}\n"
    "\n"
    "/// Loads `Foo` from disk.\n"
    "/// Returns the parsed `Bar`.\n"
    "fn load() -> Bar {}\n"
)


class SplicedDocsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(
        self, repo_root: Path, config: dict[str, object] | None = None
    ) -> list[Finding]:
        return list(run(repo_root, "HEAD", {NAME: config or {}}).findings)

    def test_a_rust_splice_naming_an_undocumented_item_in_file_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "src/lib.rs:4")
        self.assertEqual(findings[0].mode, MODE_UNDOCUMENTED)
        self.assertIn("load_project", findings[0].message)

    def test_a_bare_carriage_return_does_not_shift_a_later_lines_number(self) -> None:
        """The file is read with no newline translation, so a finding cites
        git's line number (#191)."""
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "// Intro\r page.\n"
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual([f.citation for f in findings], ["src/lib.rs:5"])

    def test_unknown_mode_is_opt_in_a_rust_splice_naming_nothing_is_not_flagged_by_default(
        self,
    ) -> None:
        # `unknown` mode is off by default (ticket #9) — this fixture is
        # shaped exactly like a real false positive on dense doc comments:
        # an ordinary paragraph naming a real-looking-but-undeclared
        # backtick term, no blank `///` separating it from the run above.
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_rust_splice_naming_nothing_in_the_repo_is_flagged_when_unknown_mode_enabled(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["unknown"]})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)
        self.assertIn("frobnicate_widget", findings[0].message)

    def test_modes_naming_both_restores_default_and_unknown_output(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.write(
                "src/other.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(
                repo.root, config={"modes": ["undocumented", "unknown"]}
            )

        self.assertEqual(
            {f.mode for f in findings}, {MODE_UNDOCUMENTED, MODE_UNKNOWN}
        )

    def test_modes_naming_only_unknown_suppresses_undocumented_findings(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["unknown"]})

        # `load_project` and `to_native_toml` are both real declarations in
        # this file, so with `undocumented` disabled and `unknown` finding
        # nothing unresolvable, no findings survive at all.
        self.assertEqual(findings, [])

    def test_an_unrecognized_mode_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/lib.rs", "fn save_config() {}\n")
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["bogus"]})

        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("'bogus' is not a known mode", findings[0].message)

    def test_a_bare_string_mode_is_treated_as_one_mode_not_a_list_of_characters(
        self,
    ) -> None:
        # `modes = "unknown"` is a one-character typo away from the correct
        # `modes = ["unknown"]` — mirrors `exclude_patterns`'s own guard
        # against the identical string-vs-list-of-characters footgun.
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": "unknown"})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)

    def test_a_non_list_mode_config_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/lib.rs", "fn save_config() {}\n")
            repo.commit()

            findings = self._findings(repo.root, config={"modes": 5})

        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("modes must be a list of strings", findings[0].message)

    def test_a_rust_doc_comment_correctly_attached_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the project's config from disk.\n"
                "///\n"
                "/// Returns the parsed `Config` struct.\n"
                "fn load_project() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_swift_splice_naming_an_undocumented_declaration_in_file_is_flagged(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "func canRestoreInPlace() -> Bool { true }\n\n"
                "/// Whether `canRestoreInPlace` allows an in-place restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "Sources/Room.swift:4")
        self.assertEqual(findings[0].mode, MODE_UNDOCUMENTED)
        self.assertIn("canRestoreInPlace", findings[0].message)

    def test_unknown_mode_is_opt_in_a_swift_splice_naming_nothing_is_not_flagged_by_default(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether `canRestore` allows a restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_swift_splice_naming_nothing_in_the_repo_is_flagged_when_unknown_mode_enabled(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether `canRestore` allows a restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["unknown"]})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)
        self.assertIn("canRestore", findings[0].message)

    def test_a_swift_unclosed_backtick_still_names_its_declaration(self) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "func canRestoreInPlace() -> Bool { true }\n\n"
                "/// Whether `canRestoreInPlace allows an in-place restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNDOCUMENTED)
        self.assertIn("canRestoreInPlace", findings[0].message)

    def test_a_swift_declaration_correctly_documented_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether the room can be restored.\n"
                "///\n"
                "/// Returns false once `restoreBlocker` is set.\n"
                "func canRestoreInPlace() -> Bool { true }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_findings_are_advisory_never_gating(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 0)

    def test_findings_have_gate_false(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertTrue(findings)
        self.assertTrue(all(not f.gate for f in findings))


    def test_a_rust_item_documented_above_a_multi_line_attribute_is_not_bare(
        self,
    ) -> None:
        self.assertNotIn("Foo", _rust_bare_items(RUST_MULTILINE_ATTR.splitlines()))

    def test_a_rust_item_documented_above_a_multi_line_attribute_is_not_flagged(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("src/lib.rs", RUST_MULTILINE_ATTR)
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_nested_brackets_in_a_multi_line_rust_attribute_are_balanced(
        self,
    ) -> None:
        lines = [
            "/// The parsed config.",
            "#[cfg_attr(",
            "    feature = \"x\",",
            "    derive(Debug, Clone),",
            "    doc(alias = [\"a\", \"b\"][0]),",
            ")]",
            "pub struct Foo {}",
        ]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_brackets_in_a_rust_attribute_string_do_not_unbalance_it(self) -> None:
        # Counting the `[` in the string would hold the attribute open
        # through the stray `]`, carrying `Foo`'s doc down to `Bar`.
        lines = [
            "/// The parsed config.",
            "#[doc(alias = \"[\")]",
            "pub struct Foo {}",
            "",
            "    a: u8,",
            "]",
            "pub struct Bar {}",
        ]
        self.assertEqual(set(_rust_bare_items(lines)), {"Bar"})

    def test_an_undocumented_rust_item_with_a_multi_line_attribute_is_still_bare(
        self,
    ) -> None:
        lines = [
            "fn other() {}",
            "#[serde(",
            "    deny_unknown_fields,",
            ")]",
            "pub struct Foo {}",
        ]
        self.assertIn("Foo", _rust_bare_items(lines))

    def test_a_rust_line_that_only_looks_like_an_attribute_tail_is_not_skipped(
        self,
    ) -> None:
        lines = [
            "/// Documents the array, not `Foo`.",
            "const XS: [u8; 1] = [",
            "    1,",
            ")]",
            "pub struct Foo {}",
        ]
        self.assertIn("Foo", _rust_bare_items(lines))

    def test_a_swift_declaration_documented_above_a_multi_line_attribute_is_documented(
        self,
    ) -> None:
        lines = [
            "/// Documented.",
            "@available(",
            "    iOS 15,",
            "    *",
            ")",
            "public func foo() {}",
        ]
        self.assertEqual(_swift_declarations(lines), [(5, "foo", True)])

    def test_a_swift_declaration_documented_above_a_multi_line_attribute_is_not_flagged(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether the room can be restored.\n"
                "@available(\n"
                "    iOS 15,\n"
                "    *\n"
                ")\n"
                "func canRestoreInPlace() -> Bool { true }\n\n"
                "/// Whether `canRestoreInPlace` allows an in-place restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_an_undocumented_swift_declaration_with_a_multi_line_attribute_is_not_documented(
        self,
    ) -> None:
        lines = [
            "func other() {}",
            "@available(",
            "    iOS 15,",
            ")",
            "public func foo() {}",
        ]
        self.assertIn((4, "foo", False), _swift_declarations(lines))

    def test_a_swift_line_that_only_looks_like_an_attribute_tail_is_not_skipped(
        self,
    ) -> None:
        lines = [
            "/// Documents the call, not `foo`.",
            "let x = f(",
            "    1",
            ")",
            "public func foo() {}",
        ]
        self.assertIn((4, "foo", False), _swift_declarations(lines))
    def test_an_unclosed_rust_attribute_does_not_hide_the_items_after_it(
        self,
    ) -> None:
        # The `'['` char literal is counted, so the attribute never balances;
        # it still ends at the next item rather than running to the end.
        lines = [
            "/// The parsed config.",
            "#[doc(alias = '[')]",
            "pub struct Foo {}",
            "fn z() {}",
            "pub struct Bar {}",
        ]
        self.assertEqual(set(_rust_bare_items(lines)), {"z", "Bar"})

    def test_a_swift_declaration_after_a_multi_line_attributed_signature_is_not_documented(
        self,
    ) -> None:
        lines = [
            "/// Documents `foo`.",
            "@objc func foo(",
            "    a: Int",
            ") {}",
            "func bar() {}",
        ]
        self.assertIn((4, "bar", False), _swift_declarations(lines))

    def test_an_unclosed_swift_attribute_does_not_hide_the_declarations_after_it(
        self,
    ) -> None:
        lines = [
            "/// Documented.",
            "@available(",
            "func a() {}",
            "func b() {}",
        ]
        self.assertEqual(
            _swift_declarations(lines), [(2, "a", True), (3, "b", False)]
        )

    def test_a_swift_attribute_ends_where_its_own_parentheses_close(self) -> None:
        # The `(` opening `foo`'s signature is not the attribute's: the
        # attribute closes at `)` after `fooWith:`, mid-line.
        lines = [
            "/// Documents `foo`.",
            "@objc(fooWith:) func foo(",
            "    a: Int",
            ") {}",
            "func bar() {}",
        ]
        self.assertIn((4, "bar", False), _swift_declarations(lines))

    def test_a_rust_attribute_ends_where_its_own_brackets_close(self) -> None:
        lines = [
            "/// Documents the array, not `Foo`.",
            "#[rustfmt::skip] const XS: [u8; 1] = [",
            "    1,",
            "];",
            "pub struct Foo {}",
        ]
        self.assertIn("Foo", _rust_bare_items(lines))

    def test_a_rust_item_on_an_attribute_closing_line_does_not_pass_its_doc_on(
        self,
    ) -> None:
        lines = [
            "/// The config.",
            "#[cfg_attr(feature = \"serde\",",
            "           derive(Serialize))] pub struct Foo;",
            "pub struct Bar;",
        ]
        self.assertIn("Bar", _rust_bare_items(lines))

    def test_a_swift_declaration_on_an_attribute_closing_line_does_not_pass_its_doc_on(
        self,
    ) -> None:
        lines = [
            "/// Documented.",
            "@available(iOS 13,",
            "  *) func foo()",
            "func bar()",
        ]
        self.assertIn((3, "bar", False), _swift_declarations(lines))

    def test_an_unclosed_rust_attribute_does_not_swallow_a_doc_comment_below_it(
        self,
    ) -> None:
        lines = [
            "#[cfg(x = '[')]",
            "/// The config.",
            "pub struct Foo;",
        ]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_a_plain_comment_between_a_rust_doc_and_its_attributes_does_not_detach_it(
        self,
    ) -> None:
        lines = [
            "/// Does a thing.",
            "// note",
            "#[instrument]",
            "#[allow(clippy::too_many_arguments)]",
            "async fn ensure_container_created() {}",
        ]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_a_blank_line_between_a_rust_doc_and_its_item_does_not_detach_it(
        self,
    ) -> None:
        lines = ["/// Doc.", "", "fn spaced() {}"]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_a_four_slash_line_is_a_plain_comment_rust_skips(self) -> None:
        lines = ["/// Doc.", "//// aside", "fn spaced() {}"]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_an_inner_doc_line_detaches_a_rust_doc_from_its_item(self) -> None:
        lines = ["/// Doc.", "//! Module doc.", "fn detached() {}"]
        self.assertIn("detached", _rust_bare_items(lines))

    def test_a_plain_block_comment_between_a_rust_doc_and_its_item_does_not_detach_it(
        self,
    ) -> None:
        comments = {
            "single line": ["/* note */"],
            "multi-line": ["/*", " * note", " */"],
            "nested": ["/* a /* b */ c */"],
            "nested across lines": ["/* a /* b", " */ c */"],
        }
        for shape, comment in comments.items():
            with self.subTest(shape):
                lines = ["/// Doc.", *comment, "fn a() {}"]
                self.assertEqual(_rust_bare_items(lines), {})

    def test_an_outer_block_doc_documents_a_rust_item(self) -> None:
        docs = {
            "single line": ["/** Doc. */"],
            "multi-line": ["/**", " * Doc.", " */"],
            "text on the opening line": ["/** Doc.", " * More.", " */"],
            "under a plain comment": ["/** Doc. */", "// note", "/* aside */"],
        }
        for shape, doc in docs.items():
            with self.subTest(shape):
                lines = [*doc, "#[inline]", "fn a() {}"]
                self.assertEqual(_rust_bare_items(lines), {})

    def test_an_inner_block_doc_detaches_a_rust_doc_from_its_item(self) -> None:
        shapes = {
            "single line": ["/*! inner */"],
            "multi-line": ["/*!", " * inner", " */"],
        }
        for shape, inner in shapes.items():
            with self.subTest(shape):
                lines = ["/// Doc.", *inner, "fn a() {}"]
                self.assertIn("a", _rust_bare_items(lines))

    def test_a_doc_marker_inside_a_plain_block_comment_is_not_a_rust_doc(self) -> None:
        comments = {
            "line doc": ["/*", "/// old", "*/"],
            "block doc": ["/* outer", "/** inner */", "*/"],
        }
        for shape, comment in comments.items():
            with self.subTest(shape):
                self.assertIn("a", _rust_bare_items([*comment, "fn a() {}"]))

    def test_an_inner_block_doc_nested_in_an_outer_one_does_not_detach_it(self) -> None:
        lines = ["/** Doc.", "/*! x */", "*/", "fn a() {}"]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_a_block_doc_on_another_items_line_does_not_document_the_next(self) -> None:
        lines = ["/** Doc. */ struct S;", "fn a() {}"]
        self.assertIn("a", _rust_bare_items(lines))

    def test_an_empty_or_banner_block_comment_is_not_a_rust_doc(self) -> None:
        for comment in ["/**/", "/*** banner ***/", "/* plain */"]:
            with self.subTest(comment):
                self.assertIn("a", _rust_bare_items([comment, "fn a() {}"]))

    def test_a_rust_outer_block_doc_is_not_checked_for_breaks(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn helper() {}\n\n"
                "/** Loads the config.\n"
                " * The `helper` result is cached. */\n"
                "fn load() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_struct_inside_a_rust_fn_body_is_not_bare(self) -> None:
        lines = [
            "/// Removes things.",
            "async fn remove() {",
            "    struct Reinsert<'a> {",
            "        a: &'a str,",
            "    }",
            "}",
        ]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_undocumented_top_level_rust_items_and_impl_methods_are_still_bare(
        self,
    ) -> None:
        lines = [
            "fn top() {}",
            "struct Plain {",
            "    a: u8,",
            "}",
            "impl Plain {",
            "    fn method(&self) {}",
            "}",
            "trait Shape {",
            "    fn area(&self) -> f64;",
            "}",
            "impl Shape for Plain {",
            "    fn area(&self) -> f64 { 0.0 }",
            "    fn later() {}",
            "}",
        ]
        self.assertEqual(
            set(_rust_bare_items(lines)), {"top", "Plain", "method", "Shape", "area", "later"}
        )

    def test_a_rust_impl_is_named_by_its_implementing_type(self) -> None:
        # Ticket #173: `impl fmt::Display for Text` was bare as `fmt`.
        lines = ["/// The text.", "struct Text;", "impl fmt::Display for Text {}"]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_items_nested_two_blocks_deep_in_a_rust_fn_body_are_not_bare(
        self,
    ) -> None:
        lines = [
            "/// Runs.",
            "fn outer(x: bool) {",
            "    if x {",
            "        struct Inner;",
            "        fn helper() {}",
            "    }",
            "}",
        ]
        self.assertEqual(_rust_bare_items(lines), {})

    def test_a_brace_in_a_string_in_a_rust_fn_body_does_not_shift_its_depth(
        self,
    ) -> None:
        lines = [
            "/// Runs.",
            "fn outer() {",
            "    let open = \"{\";",
            "    struct Inner;",
            "}",
            "fn after() {}",
        ]
        self.assertEqual(set(_rust_bare_items(lines)), {"after"})

    def test_braces_outside_rust_code_do_not_shift_a_fn_body_depth(self) -> None:
        # Each shape left a `{` counted in ratect, so the body never closed
        # and every top-level item below it read as function-local.
        bodies = {
            "line comment": ["    // opens { here"],
            "doc comment": ["    /// Anything after a `{` starts a name."],
            "block comment": ["    /* { */"],
            "byte literal": ["    if c == b'{' {", "    }"],
            "char literal": ["    let c = '{';"],
            "continued string": ["    let s = \"a = { b }\\n\\", "        c = {\\n\";"],
            "raw string": ["    let s = r#\"", "{ \"quoted", "\"#;"],
            "lifetime": ["    let s: &'static str = \"\";", "    struct Local<'a>(&'a str);"],
        }
        for shape, body in bodies.items():
            with self.subTest(shape):
                lines = ["/// Runs.", "fn outer() {", *body, "    struct Inner;", "}", "fn after() {}"]
                self.assertEqual(set(_rust_bare_items(lines)), {"after"})

    def test_a_brace_in_a_rust_fn_signature_does_not_open_its_body(self) -> None:
        signatures = {
            "array length": "fn f() -> [u8; { N }] {",
            "const generic": "fn f() -> Foo<{ N + 1 }> {",
            "parameter type": "fn f(x: [u8; { N }]) {",
        }
        for shape, signature in signatures.items():
            with self.subTest(shape):
                lines = ["/// Doc.", signature, "    struct In;", "}", "fn after() {}"]
                self.assertEqual(set(_rust_bare_items(lines)), {"after"})

    def test_a_rust_where_clause_leaves_the_body_on_its_own_line(self) -> None:
        lines = [
            "/// Doc.",
            "fn f<T>(x: T)",
            "where",
            "    T: Clone,",
            "{",
            "    struct In;",
            "}",
            "fn after() {}",
        ]
        self.assertEqual(set(_rust_bare_items(lines)), {"after"})

    def test_a_one_line_rust_fn_does_not_leave_its_body_pending(self) -> None:
        lines = ["/// Doc.", "fn a() { x }", "impl X {", "    fn m() {}", "}"]
        self.assertIn("m", _rust_bare_items(lines))

    def test_a_const_block_after_a_comma_in_rust_generics_opens_the_body(self) -> None:
        # An accepted gap, pinned so that changing it is deliberate: a comma
        # rule would also catch a body after a `where` clause's trailing comma.
        lines = ["/// Doc.", "fn f() -> Foo<A, { N }> {", "    struct In;", "}"]
        self.assertIn("In", _rust_bare_items(lines))

    def test_a_splice_naming_a_rust_fn_local_item_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Runs.\n"
                "fn outer(x: bool) {\n"
                "    if x {\n"
                "        struct Inner;\n"
                "    }\n"
                "}\n\n"
                "/// Loads `Inner` from disk.\n"
                "/// Returns the parsed config.\n"
                "fn load() {}\n",
            )
            repo.commit()

            findings = self._findings(
                repo.root, config={"modes": ["undocumented", "unknown"]}
            )

        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
