# 0012. A CI run can fail on unmarked findings

## Status

Accepted. Issue #188; builds on
`decisions/0010-checked-marks-expire-on-their-own.md` and
`decisions/0011-append-only-is-a-property-of-the-file.md`.

## Context

An advisory finding is surfaced and never fails the run
(`docs/concepts.md`, "Gate versus advisory"). Checked marks (#156) made
every true advisory finding resolvable, either fixed or marked after a
reading, but nothing requires that it is. On or1can/ratect, the PRs that
applied a full read-and-mark pass's fixes wrote new prose, and its
findings merged unread. The pass had read 937 findings and found 46
wrong, so reading pays.

## Decision

A run can be told to fail on **unmarked findings**: advisory findings,
from a check whose findings can be marked, that no checked mark keeps
quiet.

- It is a CLI flag only. `--fail-on-unmarked` covers every markable check;
  `--fail-on-unmarked=restatement,judgment-agent` covers the named ones.
  No `claims.toml` key sets it, and the commit hook never applies it. A
  project passes the flag in CI, so a PR resolves the findings it brings
  in, and local commits stay advisory.
- An advisory finding from a check that can't be marked never fails the
  run. An orphaned mark does, under the flag, since deleting the entry
  resolves it.
- With the flag, unmarked findings in scope exit `3`. A gate failure still
  exits `1` and takes precedence, and bad configuration or input still
  exits `2`. The summary line counts the unmarked findings, and a run
  failing on them says so in one closing line.
- The summary line also counts the marks the range added to
  `claims.checked.toml`, so a reviewer sees a batch of new marks. That
  count is the only guard against marks written without a reading.

The severity of a finding doesn't change. An unmarked advisory finding is
still advisory; what changes is that a caller may decide an unread one
fails its run.

## Alternatives considered

- **A `claims.toml` key the hook also honours.** That moves the cost onto
  every local commit, where nobody chose to read findings. It can be added
  later if a project wants it.
- **A per-check `strict` key.** The flag's list covers per-check choice
  without making the same `claims.toml` read differently in CI and at
  commit time.
- **A warning on near-identical notes.** Any similarity threshold is
  arbitrary, and a count of new marks puts the judgment where it belongs,
  with the reviewer.

## Consequences

- `docs/concepts.md`'s "never fails the run" gains the exception.
- Precision becomes a cost: every false-positive class is a blocked PR
  for a project that sets the flag. That is why this waits on #187.
- A dependency bot can't mark. A person or agent marks on its behalf,
  which the docs say.
