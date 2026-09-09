# 21 — Validate the plugin manifest against the real `claude plugin validate`

**What to build:** `tests/test_plugin_manifest.py`'s structural assertions
(paths exist, name each other consistently) didn't catch `plugin.json`'s
`agents` field pointing at a directory instead of a file — because
`test_agent_directory_has_an_agent_file_with_required_frontmatter` (as it
was before ticket 19's fix) *encoded the same wrong assumption* the manifest
bug had, globbing `*.md` under `agents[i]` rather than treating it as a
file. Only running `claude plugin validate .` directly, live, in ticket 19,
caught it — and that's exactly the kind of check a test suite should own
rather than rely on a human (or agent) remembering to run by hand.

Add a test that shells out to the real `claude` CLI's `plugin validate`
against this repo's own manifests and asserts it passes (accept warnings,
fail only on errors — `--strict` may be too strict for the existing
`author`-missing warning). Guard it to skip cleanly, not fail, in an
environment where the `claude` CLI isn't on `PATH` — this repo's other tests
already tolerate a missing `pytest` binary (ticket 18's Answer) by falling
back to direct script invocation; this is the same shape of environment
dependency.

**Blocked by:** 18.

**Status:** resolved

- [x] A test invokes `claude plugin validate .` (or the equivalent
      programmatic entry point, if one exists) against this repo's real
      `.claude-plugin/` manifests and asserts it exits successfully.
- [x] The test skips cleanly (not a failure) when the `claude` CLI isn't
      available, rather than breaking the suite in an environment without
      it.
- [x] Reverting `plugin.json`'s `agents` field to `["./claims/subagent"]`
      (the exact bug ticket 19 found and fixed) makes this new test fail,
      where the pre-existing structural tests didn't.

## Answer

Added `test_claude_plugin_validate_passes_against_the_real_manifests` to
`tests/test_plugin_manifest.py`: `shutil.which("claude")` gates the test —
`self.skipTest(...)` when absent, matching the missing-`pytest` tolerance
pattern already used for the test runner. When present, it shells out to
`claude plugin validate .` from `REPO_ROOT` and asserts `returncode == 0`
(no `--strict`, so the pre-existing `author`-missing warning stays a pass).
30s `timeout=` guards the call, matching `executable_claims.py`'s own
subprocess-hang guard for shelling out to an external command
(`code-review` caught the initial version's missing timeout).

Verified red independently of the fix: reverted `plugin.json`'s `agents` to
`["./claims/subagent"]` (ticket 19's exact bug) and reran the file directly —
the new test failed with `plugin.json → agents: Invalid input`
(`Validation failed`, exit 1), confirming it (and, incidentally, the
already-fixed `test_agent_entry_is_a_file_with_required_frontmatter`) catches
what the ticket described. Reverted back to green before committing.
