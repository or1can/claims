# 1. One cache per process

Every request reads through the same cache.

## Revisited

Every read goes through the cache, and nothing else touches the store.

The cache has three backends.

Without `evict`, the cache would grow until restart.

The first full sweep took three seconds.

> Every backend shares a single lock.

*Every backend shares a single lock.*

Previously said: every backend shares a single lock.

We used to say "every backend shares a single lock".
