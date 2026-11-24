SETTINGS = ["timeout", "retries", "log_level"]

DEFAULTS = {
    "timeout": 30,
    "retries": 3,
}


def get(name, overrides):
    if name in overrides:
        return overrides[name]
    return DEFAULTS[name]
