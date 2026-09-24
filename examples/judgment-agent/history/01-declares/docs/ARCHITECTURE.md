# Architecture

Every read goes through `Store.fetchRecord`, which checks the cache
before touching disk.

A `Store` owns one cache and one disk handle.
