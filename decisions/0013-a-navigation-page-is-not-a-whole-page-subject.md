# 0013. A navigation page is not a whole-page subject

## Status

Accepted. Issue #193. Amends how
`decisions/0010-checked-marks-expire-on-their-own.md`'s marks and
`decisions/0009-stale-claims-is-diff-scoped.md`'s churn treat a page
named whole; extends the `[subjects]` table of
`decisions/0011-append-only-is-a-property-of-the-file.md`.

## Context

A checked mark records a content hash of each subject its unit names, and
a Markdown page named without an anchor is hashed whole. A much-linked
page then expires every mark naming it on any edit anywhere in it, though
most of those sections depend on a different part of the page, or on none
of it: a link from a section to a page is often navigation ("see the
differences page"), not a claim about everything on it. On or1can/ratect,
one PR fixing six small claims in four hub pages expired about 45 marks,
and every finding behind them was still true. `stale-claims` reads the
same pages the same way, ranking every section that links a hub page as
moved.

An anchored link already records only its section, so linking the
relevant section is the precise fix wherever prose can be rewritten.

## Decision

A project lists the pages it links for navigation:

```toml
[subjects]
navigation = ["docs/differences-from-batect.md", "docs/how-it-works.md"]
```

A bare string is a one-element list. Nothing is a navigation page by
default.

A navigation page named **without an anchor** is not a subject: a
checked mark doesn't record it, so editing the page doesn't expire the
mark, and `stale-claims` doesn't count it, so the page's churn doesn't
rank the section. A link with an anchor into it still names that
section, hashed and counted as before. A code file, or any page not
listed, is unchanged.

The docs present anchored links as the precise fix, and `navigation` as
the blunt one for pages whose links can't all be anchored.

## Alternatives considered

- **Every whole-page Markdown subject stops counting, unconfigured.**
  Predictable, but it silently drops genuine whole-page claims ("the
  differences page lists every exit code").
- **Hashing only the sections whose words the unit shares.** It can't be
  made predictable: whether a mark survives an edit would depend on
  word overlap nobody can see.
- **Keeping the whole-file hash and only advising anchors.** Right where
  the prose can change, but some links are navigation by nature, and a
  hub page would keep expiring them.

## Consequences

- A sentence that makes a claim about a whole navigation page loses that
  page as a subject. Its mark covers its wording and its other subjects
  only. A project trading that away chose to by listing the page.
- `[subjects]` holds two properties of a file, `append_only` and
  `navigation`. They can apply to the same page.
