Type: grilling
Status: resolved

## Question

Decide how `ratect`, the other two source projects (private, not named in
this repo — see map.md's Out of scope), and future consuming projects
actually pull in the unified skill+subagent once it exists in this repo:
a Claude Code plugin published to a marketplace, a plugin referenced directly
by git URL/path (matching how e.g. `mattpocock-skills` is already installed in
this session — see `.claude/plugins/cache/claude-plugins-official/...`),
vendored/submoduled scripts invoked CLI-style, or some other mechanism.

Consider: how do the currently-installed plugins in this environment get
updated when the source changes — is there a pinned version, or always-latest?
Each consuming repo is a different language (Rust/Swift/Python) but the
skill/subagent itself is language-agnostic at the invocation layer (it shells
out to per-language adapters) — does the distribution mechanism need to bundle
adapters per language, or can they be fetched/selected separately?

## Answer

**Direct git-URL plugin, no marketplace.** Checked this environment's own
installed plugins as the fact-finding basis: `mattpocock-skills` is
marketplace-installed, pinned to a specific commit SHA and cached under a
version-numbered directory (`.../mattpocock-skills/1.2.3/...`); `caveman` is
installed straight from a git URL registered as its own entry in
`extraKnownMarketplaces` in `settings.json` — no central marketplace listing
required for either to work. Once this repo is public, a consuming project
adds one `extraKnownMarketplaces` entry pointing at this repo's git URL and
enables it — caveman's exact precedent. Publishing to a marketplace later
remains possible without changing the plugin itself; not needed at launch.

**Pinned at install, explicit update step** — matching the observed default
(mattpocock-skills is pinned to a SHA, not floating), not always-latest.
Important specifically because this plugin can gate a commit (ticket 02): an
unreviewed upstream change shouldn't silently alter what blocks someone's
commit mid-project.

**Bundle everything in one plugin repo** — the skill, the subagent, the
`PreToolUse` hook, and every language adapter (Rust/Swift/Python) ship
together from one install. Matches the map's destination text directly: "a
Claude Code skill... consolidated... into this repo, installable by any
consuming project" — one thing to install, not a core-plus-fetch-adapters
model.

**Hook opt-out is a config toggle inside the installed plugin, not
all-or-nothing.** Installing the plugin always gets the on-demand
skill/subagent; a project that wants to suppress the auto-hook specifically
(per ticket 02's framing of opt-out) sets a per-project config value the hook
script checks before running, rather than needing to avoid installing the
plugin altogether.

This resolves the map's "Versioning/update mechanism for consuming repos once
packaged" fog item (pinned-at-install, explicit update, as above) — see
map.md's Not yet specified section, now updated.
