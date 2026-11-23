# 0001. The cache

## Status

Accepted.

Amended by `0002-no-disk.md`: the two storage bullets are replaced.

## Decision

`get` returns `None` for a key it doesn't hold.

`Cache` in `cache.py` gains two methods, which keep it on disk:

- `save` writes every entry to disk as it is stored.
- `load` reloads every entry from disk on a restart.

## Consequences

A restart keeps the cache.
