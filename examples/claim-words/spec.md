# Cache specification

Every request reads through the same cache.

## Backends

Every read goes through the cache, and nothing else touches the store.

Each of the three backends keeps its own copy.

Without `evict`, the cache would grow until restart.

The first full sweep took three seconds.

> Every backend shares a single lock.

*Every backend shares a single lock.*

Previously said: every backend shares a single lock.

We used to say "every backend shares a single lock".
