# Tutorial: documenting a release

In this tutorial you document how to cut a release of a small practice
project, make a mistake in the doc, watch the real commit hook refuse
the commit, fix it, watch the push hook refuse the push, then check the
claim, mark it checked and push again. You type every command yourself,
and every block of output on this page is what those same commands
print.

## Setting up

First you build the practice project, Acme, inside your clone of this
repository. You need git and uv and nothing else; the first run fetches
`hatchling`, which this repository builds with, so it needs a network
connection.

Run, from the root of your clone:

```sh
{{#include ../examples/tutorial/steps.sh:setup}}
```

Captured from a clone of this repository:

```
{{#include captures/tutorial/setup.txt}}
```

Then `cd .tutorial/acme`. Every later command on this page runs there.
`.tutorial/` is gitignored, so Acme never shows up in your clone's own
`git status`, and running setup again deletes Acme and builds it afresh
from the start, which is the way back from any mistake.

Acme starts with one doc, `RELEASING.md`:

```markdown
{{#include ../examples/tutorial/start/RELEASING.md}}
```

The `<!-- verify: cat VERSION -->` marker says the block beneath it is
what `cat VERSION` prints, and
[executable-claims](checks/executable-claims.md) runs the command and
compares on every commit. `VERSION` holds `1.0.0`, so it passes quietly.
A command runs only if this machine has granted it, in a
`claims.local.toml` that git does not track; setup copies one granting
`cat VERSION` into Acme, and Acme's `.gitignore` keeps it untracked. A
fresh clone of a real project has no grants until you write your own.

`claims.toml` turns the commit hook on, and names the one file
[claim-words](checks/claim-words.md) reads:

```toml
{{#include ../examples/tutorial/start/claims.toml}}
```

`scripts/release.sh` <!-- example --> is how Acme is released:

```sh
{{#include ../examples/tutorial/start/scripts/release.sh}}
```

Setup installs two hooks. `pre-commit` runs on every `git commit`:

```sh
{{#include ../examples/tutorial/hooks/pre-commit}}
```

`pre-push` runs on every `git push`:

```sh
{{#include ../examples/tutorial/hooks/pre-push}}
```

Both run the `claims` in your clone, through uv, so the tutorial needs
no release installed. They are not the hook
[Installation](installation.md#the-git-pre-commit-hook) tells a real
project to install, which pins a tagged release; don't copy them into
one.

Setup writes three git settings, all in Acme's own configuration and
none in yours:

- `core.hooksPath` points git at the two hooks above, where they sit in
  your clone.
- `commit.gpgsign=false`, so that a global setting to sign every commit
  doesn't stop a practice commit to ask for a key.
- The repository is created with `-b main`, so its branch is `main`
  whatever your `init.defaultBranch` says.

## Committing a wrong doc

Now you add two lines to `RELEASING.md` and try to commit them. Make your
copy match this.

`RELEASING.md` now reads:

```markdown
{{#include ../examples/tutorial/states/commit/RELEASING.md}}
```

Run:

```sh
{{#include ../examples/tutorial/steps.sh:commit}}
```

Captured from a fresh `.tutorial/acme` after the steps above:

```
{{#include captures/tutorial/commit.txt}}
```

The commit hashes and git's own messages you see will differ from this
page, as your identity, dates and git version differ. The `claims` lines,
the ones starting `[GATE]` and `[advisory]`, should match.

The commit is refused by the first of them, a gate finding from
[check-file-refs](checks/check-file-refs.md). A gate finding is a claim
`claims` has proved false, and it blocks the commit until the doc is
fixed. The second line is an advisory finding from
[claim-words](checks/claim-words.md): "Every release" is a sweeping
claim that may well be true, so it is printed for someone to check, and
it blocks nothing.

## Fixing it

Now you correct the script's name to the one Acme has, and commit again.

`RELEASING.md` now reads:

```markdown
{{#include ../examples/tutorial/states/fix/RELEASING.md}}
```

Run:

```sh
{{#include ../examples/tutorial/steps.sh:fix}}
```

Captured from a fresh `.tutorial/acme` after the steps above:

```
{{#include captures/tutorial/fix.txt}}
```

`git diff`, without `--cached`, compares your copy with what you staged
in the last step, so it shows only the correction. The refused commit
staged the rest, and nothing has been committed since.

With `scripts/release.sh` <!-- example --> tracked,
[check-file-refs](checks/check-file-refs.md) has nothing to report, and
the commit lands. The [claim-words](checks/claim-words.md) advisory
finding prints again, because the sentence is unchanged, and this time
it is the only finding, so nothing stops the commit. That is the
difference between the two severities, which
[Concepts](concepts.md#gate-versus-advisory) sets out in full.

## Pushing

Now you push the commit to Acme's remote.

Run:

```sh
{{#include ../examples/tutorial/steps.sh:push}}
```

Captured from a fresh `.tutorial/acme` after the steps above:

```
{{#include captures/tutorial/push.txt}}
```

The push is refused. The pre-push hook runs `claims` with
`--fail-on-unmarked`, over `origin/main...HEAD`, the commits the push
would send, and that switch fails the run on an [unmarked
finding](checked-marks.md#failing-a-run-on-unmarked-findings): an
advisory finding, from a check whose findings can be marked, that no
checked mark keeps quiet. The `claim-words` finding the commit let
through is one.

The summary line counts, in order, the checks that ran, the findings
they reported, how many of those are gate findings, and, because of
`--fail-on-unmarked`, how many are unmarked. The `failing:` line after
it is printed only when unmarked findings fail the run.

`claims` itself exits `3` on a run that fails this way, as
[the command line](installation.md#the-command-line) lists. git reports
any refusing pre-push hook as its own failure, so the exit code you see
from `git push` is `1`.

## Marking the claim checked

Now you read the script the sentence is about, and, finding the sentence
true, record a checked mark that says so.

Run:

```sh
{{#include ../examples/tutorial/steps.sh:mark}}
```

Captured from a fresh `.tutorial/acme` after the steps above:

```
{{#include captures/tutorial/mark.txt}}
```

`scripts/release.sh` <!-- example --> runs `git tag` before `git push
--follow-tags`, so a release cut with it is tagged before it is pushed,
and the note in the entry piped to `mark-checked` records that. An entry
is the finding's citation and mode, as the finding line printed them,
then what you verified; `mark-checked` refuses an entry without a note.

`mark-checked` runs the checks itself and marks only a finding of that
run. By default it runs over `HEAD`, the changes not yet committed, and
the sentence was committed in the last step, so
[claim-words](checks/claim-words.md), which reads only what a diff
added, would find nothing there to mark. `--diff-range origin/main`
compares with the remote's tip instead, so the run covers the commits
not yet pushed, where the push found the finding.

The mark is written to `claims.checked.toml`, which the `cat` shows. Its
`unit` is a fingerprint of the marked sentence, not something to read or
write by hand: the mark follows the sentence rather than its line, and
stops applying once a word of it changes, as
[Units](checked-marks.md#units) sets out. The file is committed like any
other, and the commit hook has nothing to say about it.

## Pushing again

Now you push again.

Run:

```sh
{{#include ../examples/tutorial/steps.sh:push-again}}
```

Captured from a fresh `.tutorial/acme` after the steps above:

```
{{#include captures/tutorial/push-again.txt}}
```

The push lands. The `claim-words` finding is still there, but the mark
keeps it quiet, so the summary line counts it as `1 quiet while checked`
rather than printing it, and `0 unmarked` lets the push through. `1
mark(s) added in range` says the push carries a new mark, which is the
thing for a reviewer to read, as [What a run
shows](checked-marks.md#what-a-run-shows) explains.

## Going further

- [`[hook] fail_on_unmarked`](configuring.md#blocking-a-commit-on-unmarked-findings) blocks the commit itself, not only the push, on unmarked findings from the checks it lists.
- The [Claude Code plugin](installation.md#install) adds the `check-claims` skill, and [judgment-agent](checks/judgment-agent.md), whose subagent reads the code a claim cites.

## Next

[Concepts](concepts.md) defines the vocabulary the rest of the site uses:
gate versus advisory, mode, candidate versus verdict, and what makes a
claim live or dated.
