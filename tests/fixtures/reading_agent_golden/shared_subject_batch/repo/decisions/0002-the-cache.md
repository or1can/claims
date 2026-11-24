# 0002. The cache

## Status

Accepted.

Amended by `0003-no-disk.md`, which replaces the sentence on
writing to disk.

## Decision

`get` returns `None` for a key it doesn't hold. Every entry is written
to disk as it is stored.

## Consequences

A restart keeps the cache.
