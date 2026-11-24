from cache import Cache

SETTINGS = ["capacity", "timeout", "log_level"]

DEFAULTS = {
    "capacity": 128,
    "timeout": 30,
}


def build(overrides):
    return Cache(overrides.get("capacity", DEFAULTS["capacity"]))
