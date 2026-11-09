# Generated subjects and history-weighted scores

`stale-claims` has no `[subjects]` list for generated output, such as
captured terminal output. Its score stays a plain percentage of each
subject's history, with no weighting by how long that history is.

## Why this is out of scope

#199 put unrelated sections at the top of the ranking after a capture,
`docs/captures/doctor.ansi`, gained a line. It asked for three things.

**A `generated` subject list, so regeneration isn't churn.** When a
capture is regenerated, the output it records has changed. A section
that quotes that output, or links the capture explicitly, is the one
that should be re-read. The noisy sections in #199 never cited the
capture. They reached it through a bare backtick name, `` `doctor` ``,
which resolved to the capture because it was the only tracked file
with that stem. A project fixes that with the check's `exclude`: an
excluded file is left out of the bare-name lookup, while an explicit
path still reaches it.

```toml
[stale-claims]
exclude = ["docs/captures/*"]
```

**Weighting the percentage by history length.** Since ADR 0009, every
section in scope is reported, so the score decides only the order, never
whether a section is shown. "100% of 7 commits" and "50% of 100 commits"
are both worth reading, and there is no principled answer to which is
staler. Any weighting would be a guessed constant. Whether the output
needs a floor at all is tracked in `TODO.md`, beside the caps and floors
ADR 0009 deferred.

**Whether a bare stem should name a file.** It should, but only where a
project's `module_reference_scope` and `exclude` allow it, as today.
The docs part of #199 covers that.

## Prior requests

- #199: "stale-claims: a regenerated capture counts as movement, and a short history's percentage tops the ranking"
