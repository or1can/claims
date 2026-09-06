# 07 — Port executable-claims check (gate)

**What to build:** a marker-based executable-claims check — a
`<!-- verify: cmd -->` marker above a fenced block runs `cmd` through a
shell and diffs its output (and exit code) against the block — registered
against the core runner as a **gate** check.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] A true claim (command output matches the block, exit code zero) passes.
- [ ] A false claim (output mismatch, or non-zero exit code even when text
      matches) fails.
- [ ] A sweep that finds zero markers, or a marker with a malformed block,
      is reported as a failure — never a silent "0 checked, 0 failures"
      clean pass.
- [ ] The command runs through a shell (not `shlex.split`), so a marker
      needing a pipe (`| tail -1`) works.
- [ ] Demonstrated end-to-end via the CLI from ticket 06 against a fixture
      repo with a true marker, a false marker, and a malformed marker.
