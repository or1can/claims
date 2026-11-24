# Configuration

Settings are read by `get` in `settings.py`.
Every name in `SETTINGS` has an entry in `DEFAULTS`.
An override always wins over a default.

`retries` now defaults to 3.
A missing override falls back to the default.
