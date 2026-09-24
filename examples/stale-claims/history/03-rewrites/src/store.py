import hashlib
import os


def put(key, value):
    name = hashlib.sha1(key).hexdigest()
    os.makedirs(name[:2], exist_ok=True)
    open(os.path.join(name[:2], name[2:]), "w").write(value)
