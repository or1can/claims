# Which hook installation can the tour's throwaway repo use?

Research for #214 (map #213). The question: which installation routes in
`docs/installation.md`'s "The git `pre-commit` hook" section can run **the
working tree's own** `claims`, with **no network at run time**, inside a
throwaway repo built in CI (GitHub Actions `ubuntu-latest`) and on a
reader's machine? For each route, what has to be installed, what does it
print around `claims`' own output, and where does the `pre-push` diff range
come from? Can a local bare remote make `origin/main...HEAD` resolve?

This branch is a context pointer. It is never merged.

## Method

- Local sources read: `docs/installation.md`, `.pre-commit-hooks.yaml`,
  this repo's own `.pre-commit-config.yaml`, `claims/pre_commit.py`,
  `claims/gate.py`, `claims/cli.py`, `scripts/capture.py`, `tests/support.py`,
  `pyproject.toml`, `.github/workflows/ci.yml`.
- External primary sources: git's `githooks(5)`
  (<https://git-scm.com/docs/githooks>), the GitHub runner image readme
  (<https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md>),
  and pre-commit 4.7.0's **installed source** (`run.py`,
  `hook_impl.py`, `try_repo.py` and `install_uninstall.py` from the
  `pre_commit.commands` package, plus `clientlib.py`, `color.py`,
  `repository.py` and `store.py` from `pre_commit` itself). pre-commit.com timed out twice when I fetched it,
  so every pre-commit claim below is cited from its source and not from the
  site.
- Experiments: bounded shell scripts in `/tmp`, run on macOS (git 2.54,
  Python 3.15, pre-commit 4.7.0 with pre-commit-uv, uv 0.13.7, lefthook
  2.2.2 and husky from npm installed into a temp prefix). Each script
  builds `work/` plus a bare `remote.git` in a fresh `mktemp -d`, with
  `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, a fixed
  author/committer and `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE=@1700000000`.
  The fixture is a `README.md` (a `check-file-refs` gate when it names a
  missing `scripts/deploy.py` <!-- example -->), a `spec.md` swept by `claim-words` (the
  advisory), a `claims.toml`, and a verify marker granted in an untracked
  `claims.local.toml`. Without the marker, `executable-claims` gates every
  commit with "no verify markers found in repo", which the tour's fixture
  will have to deal with as well.

## The shared facts every route rests on

**The diff range on push.** `githooks(5)`: pre-push "is called with two
parameters which provide the name and location of the destination remote",
and on stdin, one line per ref,
`<local-ref> SP <local-object-name> SP <remote-ref> SP <remote-object-name> LF`.
The remote object is all zeroes when "the foreign ref does not yet exist".
Observed:

```
pre-push args: origin ../remote.git
refs/heads/main 6dff4423... refs/heads/main 651247aa...
```

**A local bare remote works, and `origin/main...HEAD` resolves.** After
`git init --bare remote.git`, `git remote add origin ../remote.git` and an
initial `git push -u origin main`, `origin/main` is a remote-tracking ref.
While pre-push runs it still names the old remote tip. It moved only after
a push the hook let through: `origin/main now: 651247a HEAD 6dff442` after
the refused push. So inside the hook `origin/main...HEAD` is exactly the
commits being pushed, and for this single-user throwaway repo it equals the
`<remote-object-name>...<local-object-name>` pair from stdin.
`claims.git` hands the range to `git diff` unchanged, and three dots there
means merge base to `HEAD`. Two caveats:

- The **initial** push has to happen before the pre-push hook is installed,
  or with `--no-verify`. Until then `origin/main` does not exist.
- `githooks(5)` does not say when remote-tracking refs are updated. The
  "old tip during the hook, new tip after" behaviour above is observed, not
  cited.

**Byte-exact capture is achievable from git's side.** With the fixed
identity and dates, commit SHAs repeated across runs (`[main 6dff442] fixed`,
`[main aa94d5f] mark`, on every run). The remote URL is printed exactly as
configured, so a relative `../remote.git` keeps temp paths out of
`error: failed to push some refs to '../remote.git'` and
`To ../remote.git` / `   651247a..aa94d5f  main -> main`. `git init -b
main` avoids the default-branch hint. `claims.checked.toml` as
`mark-checked` writes it holds no timestamp or path.

**Isolation is not optional on a reader's machine.** A global
`core.hooksPath` (set by some hook managers) silently replaces
`.git/hooks` (`githooks(5)`: "the hooks directory is `$GIT_DIR/hooks`, but
that can be changed via the `core.hooksPath` configuration variable"). A
global `commit.gpgsign` would prompt or fail. The tour script should run git
with `GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1`, as `tests/support.py`
does for its fixtures, or set the repo-local config it depends on.

**Hooks run at the worktree root** (`githooks(5)`: git "changes its working
directory to ... the root of the working tree in a non-bare repository";
pre-push is not among the exceptions). `claims-pre-commit` takes no
arguments and uses `Path.cwd()` (`claims/pre_commit.py`), so this is what
it needs.

## Route by route

### 1. Plain hook script (`core.hooksPath` or `.git/hooks`), `PYTHONPATH` at the checkout. Viable.

```sh
# pre-commit
#!/bin/sh
PYTHONPATH="<checkout>" exec python3 -m claims.pre_commit
# pre-push
#!/bin/sh
PYTHONPATH="<checkout>" exec python3 -m claims.cli --diff-range origin/main...HEAD --fail-on-unmarked
```

- **Needs:** git and Python 3.11 or later. Nothing else. CI's `Test` job
  already has both (`actions/setup-python` with 3.11). The runner image
  also ships Python 3.12.3 and Git 2.56.0. No network, because nothing is
  built or fetched. It runs the checkout's code as it sits on disk, edits
  not yet committed included, which is the same principle as this repo's own
  `.pre-commit-config.yaml` `repo: local` hook.
- **Prints:** nothing of its own. A blocked commit is only claims' stderr:
  ```
  [GATE] README.md:3 (check-file-refs) `scripts/deploy.py` does not resolve to a tracked file
  ```
  A refused push is claims' stdout, then git's own line:
  ```
  [advisory] spec.md:3 (claim-words-totalising) Every read goes through the cache.
  13 checked, 1 finding(s), 0 gate failure(s), 1 unmarked
  failing: 1 unmarked advisory finding(s); fix or mark each
  error: failed to push some refs to '../remote.git'
  ```
  After `mark-checked`, a commit and a push:
  ```
  13 checked, 0 finding(s), 0 gate failure(s), 1 quiet while checked, 0 unmarked, 1 mark(s) added in range
  To ../remote.git
     651247a..aa94d5f  main -> main
  ```
  No timings, colours or absolute paths. The whole two-beat arc ran end to
  end like this, deterministically.
- **Diff range:** `origin/main...HEAD` as written. It resolves, as shown
  above. The stdin SHAs are there if the tour wants to show where a real
  setup gets its range.
- **Caveats:**
  - The script names the checkout's absolute path, so the tour script
    writes it at setup time. A hooks directory checked in under
    `examples/tour/` could instead find the path from its own `$0`, pointed
    at with `git config core.hooksPath`.
  - `python3 -m` puts the cwd (the throwaway repo) ahead of `PYTHONPATH`,
    so a fixture with a top-level `claims/` directory would shadow the
    package. `-P` (3.11+) prevents that.
  - The fail-open in `claims/pre_commit.py` only covers errors after
    `python3 -m claims.pre_commit` starts. A wrong `PYTHONPATH` exits 1
    with Python's "No module named claims", which blocks the commit.
  - It is not what `docs/installation.md` tells a consuming project to
    install (`uvx --from git+...@<tag>`). The tour has to say it runs the
    checkout's own `claims` the same way and changes only how the command
    is found.

### 2. pre-commit.com, `repo: local`, `language: system`. Viable, noisier.

```yaml
default_install_hook_types: [pre-commit, pre-push]
repos:
  - repo: local
    hooks:
      - id: claims
        entry: python3 -m claims.pre_commit
        language: system      # pre-commit 4.x silently maps this to `unsupported` (clientlib.py `_translate_language`)
        pass_filenames: false
        always_run: true
        verbose: true
        stages: [pre-commit]
      - id: claims-push
        entry: sh -c 'exec python3 -m claims.cli --diff-range "$PRE_COMMIT_FROM_REF...$PRE_COMMIT_TO_REF" --fail-on-unmarked'
        language: system
        pass_filenames: false
        always_run: true
        stages: [pre-push]
```

- **Needs:** pre-commit itself. It is **not** on the ubuntu-24.04 runner
  image (the readme lists none of pre-commit, lefthook or husky; pipx 1.16.7
  is there), so CI would `pip install pre-commit` at setup, which needs the
  network then but not when the hooks run. A reader needs it installed too.
  `repo: local` skips cloning and environment building
  (`repository.py`: `if repo_config['repo'] in {LOCAL, META}:
  _non_cloned_repository_hooks`), so there is no network at run time.
  `PYTHONPATH` has to come from the environment `git commit` runs in, or
  from an `env PYTHONPATH=...` entry. pre-commit writes to `PRE_COMMIT_HOME`
  (default `~/.cache/pre-commit`, `store.py`) even for local hooks.
  `pre-commit install` refuses if any `core.hooksPath` is set, the global
  one included ("Cowardly refusing to install hooks with `core.hooksPath`
  set.", `install_uninstall.py`).
- **Prints:**
  ```
  claims...................................................................Failed
  - hook id: claims
  - duration: 0.17s
  - exit code: 1

  [GATE] README.md:3 (check-file-refs) `scripts/deploy.py` does not resolve to a tracked file

  ```
  - The `- duration:` line varies from run to run. `run.py` prints it
    whenever `verbose or hook.verbose`, and the published hook is
    `verbose: true` (`.pre-commit-hooks.yaml`), because a passing hook's
    output, the advisory findings included, is hidden otherwise. Without
    `verbose` there is no duration line, but the advisory on the commit
    that lands disappears.
  - The dot leader is padded to a width computed from hook names, not the
    terminal, so it is stable.
  - Colour comes from `--color` / `PRE_COMMIT_COLOR` (`pre_commit.color`, default
    `auto`). It was absent when piped. Set `PRE_COMMIT_COLOR=never` to be
    sure.
  - An unstaged change prints `[INFO] Stashing unstaged files to
    /Users/.../.cache/pre-commit/patch1794311216-97271.`, an absolute,
    time-stamped path. The fixture must stage everything.
  - A byte-exact capture needs a `sed` over the duration line, or no
    `verbose`.
- **Diff range:** environment variables set by `hook_impl.py`
  `_pre_push_ns` and `run.py`. Observed: `PRE_COMMIT_FROM_REF` (remote's
  old SHA), `PRE_COMMIT_TO_REF` (local SHA), `PRE_COMMIT_REMOTE_NAME=origin`,
  `PRE_COMMIT_REMOTE_URL=../remote.git`, `PRE_COMMIT_LOCAL_BRANCH`,
  `PRE_COMMIT_REMOTE_BRANCH`, and the legacy `PRE_COMMIT_ORIGIN` /
  `PRE_COMMIT_SOURCE`. `_pre_push_ns` reads only the **first** stdin line
  that has something to push. For a new remote branch it falls back to
  `rev-list --not --remotes=<remote>`, and to `all_files` when the root
  commit is included, in which case `FROM_REF`/`TO_REF` are not set.
  `origin/main...HEAD` works in the entry too, as in route 1.

### 3. pre-commit.com, `repo: <local path>` or `try-repo <path>`. Not viable offline.

- `try-repo` with a clean checkout uses `rev = HEAD`, the **committed**
  code (observed `rev: 4fe19c6...`). It snapshots uncommitted changes into a
  shadow clone only when `git.has_diff('HEAD')` (`try_repo.py`
  `_repo_ref`). A plain `repo: <path>` needs a `rev:` and clones at that
  commit, so working-tree edits are never seen.
- Either way pre-commit builds a `language: python` environment.
  - Offline with an empty `PRE_COMMIT_HOME` it failed: `uv venv --seed` ...
    "pip was not found in the cache ... the network was disabled". That was
    via pre-commit-uv. Plain pre-commit would `pip install` the package,
    which needs `hatchling` from `[build-system] requires`.
  - It also prints `[INFO] Initializing environment for <path>` /
    `Installing environment` lines on first use, with the path in them.

### 4. `uvx --from <checkout> claims-pre-commit`. Not viable offline, and can run stale code.

- With an empty `UV_CACHE_DIR` and `--offline` it fails: "hatchling was not
  found in the cache". With the network it built in about 1s and then ran.
- **Stale code:** after the first build I edited a `.py` file in the
  source directory. The next `uvx --offline --from <dir>` still ran the old
  code (the inserted `EDITED` line never printed). uv keys a local
  directory build on its project metadata files, not the package's sources.
  `--refresh-package` fixes this but cannot be combined with `--offline`.
  A tour that must track the working tree cannot use this route.

### 5. lefthook. Works, but adds a toolchain and noisy output.

- **Needs:** the lefthook binary (Go, distributed via npm, brew, go
  install). It is not on the runner image. I installed it via npm into a
  temp prefix, which needs the network at setup. `PYTHONPATH` comes from the
  environment.
- **Prints:** a boxed banner with the version and an emoji, `┃  claims ❯`,
  `exit status 3`, `summary: (done in 0.18 seconds)`, `🥊 claims (0.18
  seconds)`. 24-bit colour escapes were emitted **even when piped**
  (`\e[38;2;56;56;56m`). `output: [failure]` trims the banner and summary,
  but the per-command timing line stays. A capture would need several
  normalisations.
- **Diff range:** `{1}` `{2}` are the remote name and URL. Stdin needs
  `use_stdin: true` (observed working). `origin/main...HEAD` works as in
  route 1.

### 6. husky. Works, thin wrapper, but needs Node and an npm install.

- **Needs:** Node and `npm install husky`. The runner image has Node 22.23.4
  and npm 10.9.9, but husky itself needs the network at install time.
  Running `husky` sets `core.hooksPath=.husky/_`. Its hook files are plain
  `sh`.
- **Prints:** claims' own output, plus one line of husky's on failure,
  `husky - pre-commit script failed (code 1)` /
  `husky - pre-push script failed (code 3)`, from `.husky/_/h`. That line is
  deterministic. `h` also sources `~/.config/husky/init.sh` if the reader
  has one, and exits early when `HUSKY=0`. Those are two reader-environment
  inputs a capture does not control.
- **Diff range:** `h` runs `sh -e "$s" "$@"` with stdin inherited, so it is
  git's own arguments and stdin. `origin/main...HEAD` works as in route 1.

## Recommendation

Use **route 1**: a plain hook script that runs `python3 -m claims.pre_commit`
and, on pre-push, `python3 -m claims.cli --diff-range origin/main...HEAD
--fail-on-unmarked`, with `PYTHONPATH` at the checkout.

- **Why route 1:**
  - It is the only route that needs nothing beyond what the `Test` job
    already has (git, Python 3.11).
  - It needs no network at any point.
  - It runs the checkout's working tree, uncommitted edits included.
  - It prints nothing around claims' own output except git's own
    deterministic lines.
  - It was demonstrated end to end: gate blocks the commit, fix lands with
    the advisory shown, push refused with exit 3, `mark-checked`, push
    accepted. Byte-identical across runs, given:
    - isolated git config (`GIT_CONFIG_GLOBAL=/dev/null`,
      `GIT_CONFIG_NOSYSTEM=1`);
    - fixed identity and dates;
    - `git init -b main`;
    - a relative `../remote.git` URL;
    - an initial push before the pre-push hook exists.
- **Hook installation:** install the hooks with `git config core.hooksPath`
  pointing at a directory the tour script controls, so a reader's own
  global `core.hooksPath` cannot pre-empt `.git/hooks`.
- **What the page must explain:** the tour's hook *is* `claims-pre-commit`'s
  code, found through `PYTHONPATH` rather than `uvx --from git+...@<tag>`.
  Point readers at `docs/installation.md` for the real setup.
- **If the tour wants to show pre-commit.com:** `repo: local` +
  `language: system` (route 2) is the only workable variant. It costs a
  `pip install pre-commit` in CI and a `- duration:` line to normalise.
- **Rule out:**
  - routes 3 and 4: they need the network or run stale or committed code;
  - routes 5 and 6: they add a toolchain, and in lefthook's case output
    that can't be captured as is.
