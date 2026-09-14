# Contributing to `claims`

Thanks for your interest! A few things to know before diving in.

## Project stage

`claims` is pre-1.0 and evolving alongside the two consuming projects that
exercise it in practice. **Please open an issue to discuss non-trivial work
before starting** — a change to a check's behavior can have knock-on
effects on every repo that's already installed the plugin.

## Development setup

```bash
uv sync                                            # install (dev group: pyright)
python3 -m unittest discover -s tests -p 'test_*.py'   # tests (no pytest binary here)
PYRIGHT_PYTHON_IGNORE_WARNINGS=1 uv run pyright claims tests  # typecheck
```

Before submitting, make sure both pass — CI enforces them. The typecheck
must read exactly:

```
0 errors, 0 warnings, 0 informations
```

`PYRIGHT_PYTHON_IGNORE_WARNINGS=1` silences pyright-python's own "newer
pyright on PyPI" nag, which would otherwise break that exact-match check —
see `AGENTS.md`'s Typechecking section.

## Conventions

- **Commits**: imperative summary, present tense (`Fix ...`, `Add ...`), a
  body only when it explains non-obvious *why*. Reference the GitHub issue
  a change resolves where one exists (`Fix #42: ...`) — this repo doesn't
  use Conventional Commits prefixes.
- **Repo conventions in depth** live in `AGENTS.md` — the change-loop
  (specification → red → code → green → prose), surgical-changes and
  constant-gardening principles, and the versioning policy for
  `.claude-plugin/plugin.json`. Both human and AI contributors follow it.
- **Checks**: each check under `claims/checks/` documents what it verifies
  and, as importantly, what it doesn't, in its own module docstring — read
  that before assuming a gap is a bug.

## Developer Certificate of Origin

Every commit must be **signed off**:

```bash
git commit -s
```

This appends a `Signed-off-by: Your Name <you@example.com>` trailer to the
commit message. It is not a signature or an identity check — it's your
affirmation of the [Developer Certificate of
Origin](https://developercertificate.org): that you wrote the change (or
otherwise have the right to submit it), and that you're submitting it under
the project's license.

CI checks every pull-request commit for a sign-off matching its author. If
you forgot one, fix up your branch with `git rebase --signoff` and
force-push.

## License

`claims` is licensed under the [Apache License 2.0](LICENSE), and
contributions are accepted under the same license (inbound = outbound).
There is no CLA — the DCO sign-off above is all that's asked.
