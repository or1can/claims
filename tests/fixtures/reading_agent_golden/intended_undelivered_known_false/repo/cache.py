class Cache:
    def __init__(self, capacity):
        self._capacity = capacity
        self._entries = {}

    def get(self, key):
        return self._entries.get(key)

    def put(self, key, value):
        if key not in self._entries and len(self._entries) >= self._capacity:
            newest = next(reversed(self._entries))
            del self._entries[newest]
        self._entries[key] = value
