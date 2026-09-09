# 19 — Ratect parity validation (adoption readiness)

**What to build:** run the consolidated executable-claims, stale-claims,
restatement, and spliced-docs checks — the four `ratect` already has as
standalone scripts — against `ratect`'s own repository history, and compare
findings against the four original scripts, with particular attention to
the historical failure instances already documented in this repo's
`doc-integrity-tooling.md` (the never-existed `--cleanup` flag, the "MCP
server" claim, the `docker network inspect` interface-name claim, and
similar). This is the acceptance gate for `ratect` retiring its own four
scripts in favour of this plugin — not a general release gate for every
consuming project.

**Blocked by:** 07, 08, 09, 11, 18.

**Status:** resolved

- [x] The consolidated checks, run against `ratect`'s history at the commits
      where each documented historical failure was introduced, catch what
      the original scripts caught.
- [x] Any finding produced by the original scripts but not reproduced by the
      consolidated checks (or vice versa) is explained explicitly — not left
      as an unremarked difference.
- [x] The comparison is published as a result (which checks matched, which
      diverged and why) rather than asserted as a bare "it works."
- [x] `ratect` installing this plugin (via ticket 18's mechanism) and running
      it once against its own current tree produces no unexpected gate
      failures **from the four checks in scope here** — see Item 4 below for
      the one gate-failing check that isn't (`check-links`, ticket 13), and
      why it doesn't bear on this ticket's retirement decision.

## Answer

Method: a disposable `git worktree` off `ratect`'s `main` (never the real
checkout), checked out at each commit under test; the consolidated checks run
via `PYTHONPATH=<claims repo> python3 -m claims.runner`-backed
`claims.cli`/direct `runner.run()` calls — the exact code path
`claims/skill/SKILL.md` and `claims/hooks.json` invoke through
`${CLAUDE_PLUGIN_ROOT}` (ticket 18); the four original scripts run from
`ratect`'s own `tools/`. The worktree was removed afterward; `ratect`'s real
checkout was never touched (confirmed via `git status`/`git reflog` before
and after).

Four named instances tracked below: (1) the never-existed `ratect-compat
--cleanup` flag, (2) the "run as an MCP server" claim — both introduced by
the same commit, `7db8c34`, and both fixed or not-fixed by the two commits
after it — (3) the `docker network inspect` interface-name claim, and (4) the
"0.5.0 ships two fixes" miscount.

**First finding, before any comparison: instances (1)–(3) predate the tool
that would catch their class.** `tools/echoed-claims.py` was added at
`c9f1b23` (2026-09-02 11:35); `7db8c34` → `d7e203a` (2026-09-01, instances 1–2)
and `3188961` → `c773384` (2026-09-02 09:12–09:16, instance 3) all landed
before it existed in `ratect`'s history. Neither the original nor the
consolidated tooling could have caught these — not a gap in either, a fact
about when the tool was written relative to when the bugs were.

### A fifth echo, not one of the four named instances, that `ratect`'s own tooling did catch — reproduced exactly

`8b105d1` ("correct the default-bridge claim, and stop scoping the entry to
Linux") fixes the self-contradiction behind instance (3)'s twin claim (see
below) and, separately, is the one commit in this history whose own message
reports `echoed-claims.py` catching something live: run over this diff, it
found `docs/config-reference.md` still describing the `host.docker.internal`
entry as Linux-only after `ROADMAP.md` had already recorded it landing on
every platform — a self-catch during authorship, folded into this same
commit, that isn't independently replayable (there's no prior commit state
where the fix was half-done).

What *is* independently replayable from this same commit: its `CHANGELOG.md`
edit separately reworded "the entry is added only when a URL was actually
rewritten" — a phrase from the same paragraph, describing when the
`host.docker.internal` entry is added rather than which platforms get it —
and that phrase still appears verbatim in `ROADMAP.md` and
`docs/differences-from-batect.md`, neither of which this commit touches.
Running the *actual* original tool's logic (copied from the commit that added
it) against `8b105d1`'s diff:

```
3 surviving echo(es) of prose this diff removed.
  ROADMAP.md:1201                       still says: ...when a url was actually rewritten...
  docs/differences-from-batect.md:253   still says: ...when a url was actually rewritten...
  docs/differences-from-batect.md:254   still says: ...actually rewritten so a run whose...
```

The consolidated `restatement` check, same diff: **identical three hits, same
file:line, same run text**, plus two the original structurally cannot see —
`ratect-compat/tests/fixtures/proxy.yml:9` and `tools/echoed-claims.py:124`
(the latter quoting the *pre-`3188961`* wording — "for every network *it*
creates" — as its own worked example for why `NGRAM_WORDS` is 6, not 8). Both
extras are real, verbatim survivors of retracted prose; the original never had
a chance at either because it sweeps `git ls-files "*.md"` only, never `.yml`
or `.py`. This is `restatement`'s documented extension broadening (`DEFAULT_EXTENSIONS`
in `restatement.py`), not a bug, and the `tools/echoed-claims.py:124` hit is
itself the legitimate "appears twice on purpose" case the check's own
docstring names — a quoted historical example, not a live claim.

### The four named instances themselves: neither tool catches any of them, for reasons both state up front

- **(1) `ratect-compat --cleanup`** and **(2) "run as an MCP server"**
  (both `7db8c34`) are first appearances — nothing is retracted yet, so
  `restatement`/`echoed-claims.py` have nothing to diff against, and neither
  claim sits under a `<!-- verify: -->` marker, so `executable-claims`/
  `verify-docs.py` never see them either. Confirmed empirically: running the
  consolidated checks against `7db8c34`'s own diff produces zero
  `restatement` findings. Instance (1) is fixed atomically across `ROADMAP.md`,
  `CHANGELOG.md`, and `docs/differences-from-batect.md` in `d7e203a` — before
  either tool ever meets it, this echo across three files never exists as a
  visible git state to replay. Instance (2)'s wording was, by policy
  (`1889a18`, folded into `AGENTS.md`), never mechanically corrected at all —
  it's still there today, struck through, in `RELEASES.md:1030` — so there
  will never be a diff for either tool to catch it against.
- **(3) `docker network inspect` reports "both" the subnet and the interface
  name** (`3188961` → `c773384`) is the same shape: wrong on arrival, no
  verify marker. Confirmed empirically against `c773384`'s diff — no
  `executable-claims`/`restatement` finding names it (the only findings in
  that neighbourhood are unrelated `stale-claims` churn candidates pointing
  at `docs/config-reference.md` generally, which is exactly what that check
  claims to be — attention-ranking, not a verdict). Instance (3)'s twin
  self-contradiction ("Ratect never uses the default bridge... `--use-network`
  names," which allows naming the bridge it says it never uses) is what
  `8b105d1` above fixes; that fix itself is a live echo-catch, covered above.
- **(4) "ratect 0.5.0 ships 0.26.0's two fixes"**, actually three (`361b2fb` →
  `158a56d`) is a count-consistency claim across `CHANGELOG.md`'s unreleased
  section and `ROADMAP.md`'s prose. None of the four checks in scope here
  claims to reconcile a count; `doc-integrity-tooling.md`'s own §4 coverage
  table doesn't list it as covered by any of the five things it built either.
  This is exactly the class `map.md`/ticket 04 route to the judgment-agent,
  not a mechanical check — correctly out of scope for retiring these four
  scripts, and unrelated to whether they should be retired.

### `spliced-docs`: exact match on the shared rule, plus the union rule

`ratect`'s own two confirmed-real historical splices — `resize_tty`'s doc
stranded on `stream_logs_as_interleaved_events`, `labels_for`'s on
`network_labels` — were fixed in `3f40726`, one commit before the tool
(`59a7796`) was committed (message: "Found by the check added next"). Running
that commit's own script content against `3f40726~1` (the pre-fix tree):

```
ratect-core/src/docker.rs:989    documents: stream_logs_as_interleaved_events   (join_network — undocumented)
ratect-core/src/docker.rs:1538   documents: run_container                       (join_network — undocumented)  [known false positive]
ratect-core/src/engine_tests.rs:478  documents: network_labels                  (run_container, start_background_container — undocumented)
ratect-compat/src/main.rs:242    documents: engine_settings                     (run — undocumented)            [known false positive]
```

The consolidated check, same tree: **all four at the same file:line**, same
backticked names, same `-undocumented` mode — a perfect reproduction of
`ratect`'s only evidence rule ("stranded prose names an undocumented item in
this file"). It also reports 14 more, all `spliced-docs-unknown` — the second
evidence rule ("names nothing anywhere in the repo"), which `ratect`'s own
script explicitly says it doesn't have (`tools/spliced-docs.py`'s docstring:
"a splice whose stranded half names nothing about its own item is invisible
here"). That rule was ported from Project B's Swift tool by design
(`spliced-docs.py`'s module docstring, "the union of their evidence rules");
`ratect-compat/src/main.rs:241` (line shifted by one since `3f40726~1`) is
still the one unfixed false positive on both `main` today and `ratect`'s own
script's current output — same finding, same file, both tools agree it's
still there and still not real.

### `stale-claims`: same algorithm, numeric divergence fully accounted for

On `ratect`'s current `main` (`5aded18`): original (`python3 tools/stale-claims.py . 1000`,
overriding its default `top=15` cap) reports **32**; consolidated reports
**86**. Not a bug in either — three concrete, already-documented differences
account for it:

1. **Subject-path scope.** Original's `PATH_RE` only matches
   `(?:[a-z][a-z0-9-]*/)+src/[a-z_0-9]+\.rs` — `ratect`'s own three-crate
   `*/src/*.rs` layout. Consolidated's is generic
   (`\b(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+\b`), so it also picks up
   `ratect.toml`, `tasks.yml`, `include.yml`, `batect-config.schema.json` and
   similar as subjects — accounting for most of the 86.
2. **Bare-name index scope.** Original builds its stem index only from
   `root.glob("*/src/*.rs")`; consolidated builds it from every tracked file,
   any extension. This is the documented tradeoff in `stale_claims.py`'s own
   module docstring — "no per-language file-extension pattern and no
   per-project directory allowlist ... at the cost of the noise a
   project-specific allowlist would otherwise have filtered."
3. **That broadening also loses hits, not just gains them**, which is worth
   stating precisely rather than waving at "noise": both `resources` and
   `labels` are unique stems under `*/src/*.rs` (`ratect-core/src/resources.rs`,
   `ratect-core/src/labels.rs`), so original resolves them unambiguously. The
   same stems collide repo-wide (`ratect/tests/fixtures/resources.yml`,
   three files named `labels.*`), so consolidated's "a stem shared by more
   than one file names no single subject and is dropped" rule (also
   documented in its own module docstring) correctly drops both — costing it
   5 of original's 32 hits (`decisions/0002-runtime-ownership-labels.md`'s
   three sections, `decisions/0003-ratect-native-config-format.md`'s two).
   Consolidated is not a strict superset of original; it trades a handful of
   narrowly-resolvable hits for far broader subject coverage, exactly the
   tradeoff its own docstring names.
4. Separately: original's CLI defaults to `top=15`; the raw "32" only shows
   uncapped (`... . 1000`). Not a functional gap, just a display cap to
   remember when comparing counts.

### `executable-claims`: identical behaviour, both empty by construction

`ratect` has exactly one `<!-- verify: -->` marker in the whole repo
(`AGENTS.md:362`). Both `verify-docs.py` and the consolidated
`executable-claims` check pass it silently on current `main` — "1 documented
command(s) checked, 0 out of date" and zero findings respectively. Neither
tool has ever had, or could have had, anything to say about the four named
class-A prose failures above, for the same reason restated once more: none of
them was ever wrapped in a verify marker.

### Item 4: running the plugin once against `ratect`'s current tree

Full `claims.cli` run (all registered checks, not just these four — this is
what installing the plugin actually runs) against `ratect`'s real `main`
checkout: **0 gate failures from the four checks this ticket is about**
(`executable-claims`, `restatement`, `stale-claims`, `spliced-docs` — the
latter three are advisory-only by design and can never gate; `executable-claims`
gates and found nothing to fail on). The only gate failures were 12 from
`check-links` (ticket 13, not blocked-by this ticket), traced to one root
cause: `check_links.py`'s `SLUG_STRIP_RE` (`[^a-z0-9 -]`) strips underscores,
which GitHub's real anchor slugger keeps — so any heading containing one
(`` `RUST_LOG` ``, `additional_args`, `run_as_current_user`) never matches its
own real anchor. Noted in `TODO.md` (separate gardening commit) rather than
fixed here: out of this ticket's scope (checks 07/08/09/11 only), and
`check_links.py` isn't a file this ticket touches.

What wasn't exercised: a live, nested Claude Code session in `ratect`
registering this repo as a plugin source and confirming the `PreToolUse` hook
fires on `git commit`. That glue (`plugin.json`/`hooks.json` shape, matcher/`if`
wiring) was already unit-tested structurally in ticket 18
(`tests/test_plugin_manifest.py`); this ticket instead exercised the exact
code path both the skill and the hook call into
(`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.cli`), which is where
"no unexpected gate failures" actually lives. A live install is the one thing
an offline validation run can't spawn on itself.

### Verdict

Consolidation holds. Every real historical catch `ratect`'s own tooling
recorded (`8b105d1`'s echo, `3f40726`'s two splices) is reproduced exactly by
the consolidated checks, plus documented, deliberate broadenings. Every named
failure neither original tool could have caught, the consolidated checks
can't either, for the same structural reasons — no regression, and no false
claim of coverage past what the four scripts ever had. `ratect` retiring
`tools/echoed-claims.py`, `tools/verify-docs.py`, `tools/stale-claims.py`,
`tools/spliced-docs.py` in favour of this plugin is supported by this result.
