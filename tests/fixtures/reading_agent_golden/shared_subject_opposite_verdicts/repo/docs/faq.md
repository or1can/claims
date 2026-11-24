## Eviction

When the cache is full, `put` of a new key evicts the newest entry
first. `get` never evicts anything.

## Restarts

A restart empties the cache.
