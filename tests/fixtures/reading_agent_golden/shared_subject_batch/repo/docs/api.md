# API

The methods are on `Cache` in `cache.py`.
Every method of `Cache` leaves its entries unchanged.
A key is any hashable value.

`delete` now ignores a key the cache doesn't hold.
A value is any object.
