## Eviction order

When the cache is full, `put` of a new key evicts the oldest entry first.
Before this page was added, it evicted the newest entry first.

## Reads

A read leaves the order alone.
