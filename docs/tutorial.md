# Tutorial: documenting a release

In this tutorial you document how to cut a release of a small practice
project, make a mistake in the doc, and watch the real commit hook refuse
the commit. You type every command yourself, and every block of
output on this page is what those same commands print.

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

## Next

[Concepts](concepts.md) defines the vocabulary the rest of the site uses:
gate versus advisory, mode, candidate versus verdict, and what makes a
claim live or dated.
