## Eviction

When the cache is full, `put` of a new key evicts the oldest entry
first. `get` never evicts anything.

## Storage

Nothing is written to disk.
