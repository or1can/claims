import threading


class Cache:
    """Thread-safety claim under test: every method locks before touching
    self._store — see claim.md."""

    def __init__(self):
        self._lock = threading.Lock()
        self._store = {}

    def get(self, key):
        with self._lock:
            return self._store.get(key)

    def set(self, key, value):
        with self._lock:
            self._store[key] = value

    def clear(self):
        with self._lock:
            self._store.clear()
