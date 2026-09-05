Type: grilling
Status: open

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
