# Comment-only changes as no movement

`stale-claims` counts every commit that touches a subject file, a change
only to its comments included. A checked mark expires on any change to
a subject's content, its comments included. Neither is going to tell
comment lines apart from code.

## Why this is out of scope

The request (#198) was to stop counting a commit whose diff touches only
comment lines, for ranking and for a mark's subject hash. Its motivating
case, or1can/ratect#812, changed four lines of Rust. Every one was a
`///` or `//!` doc comment:

```diff
-    /// can inherit. Applied in `TaskEngine::start_dependency`.
+    /// can inherit. Applied in `TaskEngine::ensure_container_created`.
```

That leaves two cuts, and neither works:

- **Plain comments only** (`//`, `#`, not doc comments). This is the
  safer cut the issue suggests, and it would have changed nothing for
  ratect#812. It also needs a comment grammar for every extension a
  subject can have. Today only `restatement` keeps a table of comment
  syntax, and only for the extensions it reads as source.
- **Doc comments too.** A doc comment is the item's own documentation.
  An edit to one is the code changing what it says about itself, and a
  prose section citing the same item is exactly the claim worth
  re-reading. Ignoring these would hide real drift, which goes against
  this project's recall-over-precision rule (`CLAUDE.md`).

Both cuts also cost checked marks something. A mark stores a content
hash per subject, so telling a comment-only change apart would mean
recording a blob id for every source subject and diffing it on every
run. That is ADR 0011's append-only machinery, applied to every file
instead of one listed changelog.

What the cost buys is the occasional re-read after a comment fix. In
ratect#812 that re-read was of a section that had just had the names it
cited changed. That is cheap, and sometimes it is not a false positive.

## Prior requests

- #198: "stale-claims: a comment-only change to a source file counts as movement"
