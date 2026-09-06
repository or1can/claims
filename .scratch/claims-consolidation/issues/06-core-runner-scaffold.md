# 06 — Core runner scaffold + CLI adapter

**What to build:** the shared seam every check and every entry point (CLI,
hook, skill) will call: a `Finding` shape, a check-registration mechanism,
and a `run(repo_root, diff_range, config)` call that executes whatever
checks are currently registered (zero, today) and returns their findings. A
minimal CLI wraps this and reports a verdict.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] A `Finding` carries at minimum: citing `file:line`, a human-readable
      message, a mode/signal name, and a `gate: bool`.
- [ ] A check registers itself against the runner without the runner needing
      to know about it in advance (no hardcoded check list).
- [ ] The CLI runs with zero checks registered and reports "0 checked" as a
      failure — never a silent clean pass — matching the executable-claims
      precedent this repo's spec documents.
- [ ] The CLI accepts a `repo_root` and a `diff_range` (defaulting to the
      working tree against `HEAD`) and passes them through to every
      registered check unchanged.
- [ ] Config is per-project and per-check (a check can read its own config
      section without seeing anyone else's).
