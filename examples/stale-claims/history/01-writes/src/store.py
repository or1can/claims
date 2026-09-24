import hashlib


def put(key, value):
    open(hashlib.sha1(key).hexdigest(), "w").write(value)
