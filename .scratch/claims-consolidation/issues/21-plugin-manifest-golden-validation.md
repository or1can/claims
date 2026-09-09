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

**Status:** ready-for-agent

- [ ] A test invokes `claude plugin validate .` (or the equivalent
      programmatic entry point, if one exists) against this repo's real
      `.claude-plugin/` manifests and asserts it exits successfully.
- [ ] The test skips cleanly (not a failure) when the `claude` CLI isn't
      available, rather than breaking the suite in an environment without
      it.
- [ ] Reverting `plugin.json`'s `agents` field to `["./claims/subagent"]`
      (the exact bug ticket 19 found and fixed) makes this new test fail,
      where the pre-existing structural tests didn't.
