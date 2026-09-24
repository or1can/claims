# Caching

Reads go through `cache.py`, which keeps one entry per path and evicts
nothing until the process exits.

# Storage

Entries are written by src/store.py as one file per key, named for the
key's hash.

# Logging

Every write is logged through `log.py` at debug level.
