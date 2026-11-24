## Building a cache

`build` in `settings.py` makes a `Cache` from `cache.py`. Its capacity is
the `capacity` override when there is one, and 128 when there isn't.

## Logging

The log level is read at startup.
