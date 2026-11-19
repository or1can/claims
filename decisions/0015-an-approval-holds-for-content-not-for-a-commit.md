# 0015. An approval holds for content, not for a commit

## Status

Accepted. Issue #247; amends
`decisions/0014-a-pending-mark-quiets-until-a-person-approves-it.md`.

Amended by `decisions/0016-an-approval-can-name-its-approver-in-the-entry.md`
(#253): `approve-marks --by` names the approver in each approved entry's
`by`. That supersedes this record's "No code changes" and its
suggestion of a commit-message line naming the approver when an
approval is folded.

Amended by `decisions/0017-an-approval-is-folded-into-the-commit-that-wrote-the-mark.md`
(#255): an approval is of a mark as written in its commit, read against
that commit's tree, and `fold-approvals` folds each into that commit.

## Context

ADR 0014's consequences say that approving is a commit of its own and
that git history records who approved. or1can/ratect read those as
rules: the commit holding the pending marks had to stay reachable, every
pull request ended in a separate approval commit, and a rewritten branch
needed a fresh approval.

The code never promised that. `approve-marks REV` compares each pending
entry in the working tree with the same entry in `claims.checked.toml`
as committed at `REV`, and approves it only if every other key,
subject hashes included, is identical. `REV` is recorded nowhere
afterwards, and `pending-marks` in CI checks only whether anything is
still pending. So what an approval guarantees is fixed at the moment
`approve-marks` runs, and it is about the entry's content.

## Decision

`claims` guarantees **content** only. An approved entry is exactly the
entry the reviewer read at `REV`, compared when `approve-marks` runs. It
does not prove afterwards which commit was read, and it does not prove a
person rather than an agent approved. Those rest on the project's own
process, and any forge-specific enforcement, such as requiring a GitHub
review, stays outside `claims`.

- An approval holds for the entry's content. A rebase, amend or squash
  that leaves every key of each approved entry identical needs no
  re-approval.
  Re-approve only what `approve-marks` would leave pending, as `changed
  since REV` or `not in REV`.
- How the approval shows in history is the project's choice: a separate
  commit, or folded into the commit that holds the marks (for example
  with `git commit --fixup=amend:<commit>` and an autosquash rebase).
  Folding loses only the record that one party marked pending and
  another approved; a line in the folded commit's message naming the
  approver can carry that by convention.
- An agent marks the findings its own pre-commit run shows in the same
  commit as the change that raises them, not in a separate marks commit
  at the end of a branch, so each mark sits beside the edit it is about
  and the approval can be folded into that one commit.

No code changes. `approve-marks`, `pending-marks` and the
`claims.checked.toml` format stay as ADR 0014 left them.

## Alternatives considered

- **Recording the approved-at commit in the entry** (an `approved_at =
  "<sha>"` key). A rebase rewrites the SHA, so the entry would name a
  commit that no longer exists, or every rewrite would need a
  re-approval that changes nothing about what was read. It proves
  nothing an agent couldn't write.
- **A `Claims-Approved:` commit trailer read by `pending-marks`.** It
  ties approval to one commit's message, which a squash or reword
  drops, and an agent can type a trailer as easily as a person can.
- **`git notes`.** Notes aren't fetched or pushed by default and don't
  follow a rebase without extra configuration, so CI would see a
  different answer from the reviewer's clone. Anyone with push access
  can write one.
- **A forge review**, such as a required GitHub approval. This is the
  only option that would stop an agent forging an approval, since the
  forge knows who clicked. It is also specific to one forge, and
  `claims` reads only git and files. A project that wants it sets it up
  on the forge, outside `claims`.

A tool that reads only git and files can guarantee content and nothing
more, so content is what this decision promises.

## Consequences

- ADR 0014's "approving is a commit of its own" becomes one of two
  routes a project may choose, and "who approved is recorded by git
  history" holds only by the project's own convention, such as a commit
  message naming the approver.
- A branch can be rebased, amended or squashed after approval without a
  second review, so long as the approved entries come through unchanged.
- The plugin skill tells an agent to mark its findings in the commit
  that raises them. It still never runs `approve-marks` unless told to.
