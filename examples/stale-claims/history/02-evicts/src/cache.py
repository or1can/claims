LIMIT = 64
entries = {}


def get(path):
    if len(entries) >= LIMIT:
        entries.pop(next(iter(entries)))
    return entries.setdefault(path, open(path).read())
