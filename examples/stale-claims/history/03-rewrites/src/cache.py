from functools import lru_cache


@lru_cache(maxsize=64)
def get(path):
    return open(path).read()
