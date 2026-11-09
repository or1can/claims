# ADR Status notes as no movement

A note added to a decision record's Status section (such as "Amended by
…" or "Since …") counts as a change to the record. Every section
that links the record whole is re-ranked by `stale-claims`, and a
checked mark on such a section expires.

## Why this is out of scope

#200 asked to treat growth of a Status section as no movement, much
like an append-only file (ADR 0011). Two things stand in the way.

The notes aren't appends at line level. On or1can/ratect (`467dd051`),
each note re-wrapped the Status line it followed:

```diff
-Accepted — implemented (ratect-compat 0.28.0 · ratect 0.7.0).
+Accepted — implemented (ratect-compat 0.28.0 · ratect 0.7.0). Since ratect#801,
+`tools/changelog-section.py` is given the binary as well as the version, and
```

So catching them would need a word-level rule, scoped to one heading
of a record.

More importantly, a rule loose enough to ignore "Amended by …" would
ignore "Superseded by …" too. That's a word-level append to the same
section, and it's the most important reason to re-read a section that
cites a decision as its authority. A missed supersession stays
invisible. The re-reads this costs (8 findings over two ratect PRs, none
leading to a fix) are visible and cheap.

A project that never links records as authorities can list them under
`[subjects] navigation` (ADR 0013), knowing it gives up that signal.

## Prior requests

- #200: "stale-claims: a Status note on an ADR raises every section that links to it"
