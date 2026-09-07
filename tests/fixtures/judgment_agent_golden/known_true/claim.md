See `Cache` in `cache.py:4` — every method acquires `self._lock`
before touching `self._store`, so `Cache` is safe to share across threads
without any external synchronization.
