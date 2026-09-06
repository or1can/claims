# 06 — Core runner scaffold + CLI adapter

**What to build:** the shared seam every check and every entry point (CLI,
hook, skill) will call: a `Finding` shape, a check-registration mechanism,
and a `run(repo_root, diff_range, config)` call that executes whatever
checks are currently registered (zero, today) and returns their findings. A
minimal CLI wraps this and reports a verdict.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] A `Finding` carries at minimum: citing `file:line`, a human-readable
      message, a mode/signal name, and a `gate: bool`.
- [x] A check registers itself against the runner without the runner needing
      to know about it in advance (no hardcoded check list).
- [x] The CLI runs with zero checks registered and reports "0 checked" as a
      failure — never a silent clean pass — matching the executable-claims
      precedent this repo's spec documents.
- [x] The CLI accepts a `repo_root` and a `diff_range` (defaulting to the
      working tree against `HEAD`) and passes them through to every
      registered check unchanged.
- [x] Config is per-project and per-check (a check can read its own config
      section without seeing anyone else's).

## Answer

Built as a Python package (`claims/`, stdlib-only — Python 3.11+ for
`tomllib`), matching this consolidation's prior art (all three source
projects' checks are Python) and the spec's testing decision to reuse their
`unittest`-based fixtures directly.

- `claims/runner.py` — `Finding` (frozen dataclass: `file`, `line`,
  `message`, `mode`, `gate`, plus a `citation` property for `file:line`),
  `register_check(name, fn=None)` (usable as a decorator or called
  directly; raises on a duplicate name), and
  `run(repo_root, diff_range, config) -> RunResult`. Each registered check
  receives only `config.get(check_name, {})` — never the full project
  config — satisfying the per-check isolation requirement.
- `claims/config.py` — `load_config(repo_root)` reads
  `<repo_root>/claims.toml` if present (each top-level table is one
  check's own section); returns `{}` if the file is absent; raises
  `ConfigError` (not a raw `tomllib.TOMLDecodeError`) on malformed TOML.
- `claims/cli.py` — `main()`/`parse_args()`. `--repo-root` (default cwd),
  `--diff-range` (default `HEAD`, i.e. working tree against `HEAD`). Exits
  1 with "0 checked" when no checks are registered, 1 when any gate
  finding is present, 2 on a malformed config file, 0 otherwise.
- 17 tests across `tests/test_runner.py`, `tests/test_cli.py`,
  `tests/test_config.py` (run via
  `python3 -m unittest discover -s tests -p 'test_*.py'` — no `pytest`
  available in this environment). All green.

Deferred, not this ticket's scope: no actual checks registered yet
(tickets 07–13), no plugin packaging (ticket 18) — this is only the seam
they'll all call.
