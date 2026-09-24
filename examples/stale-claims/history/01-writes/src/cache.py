entries = {}


def get(path):
    return entries.setdefault(path, open(path).read())
