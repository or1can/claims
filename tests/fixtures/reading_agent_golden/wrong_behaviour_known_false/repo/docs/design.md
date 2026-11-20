## Caching

`Cache` in `cache.py` holds at most `capacity` entries. `get` returns
`None` for a key it doesn't hold. When the cache is full, `put` of a new
key evicts the oldest entry first. Storing a key the cache already holds
evicts nothing.

## Storage

Nothing is written to disk.
