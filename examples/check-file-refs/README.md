# Widget

Build it with `scripts/build.py`, then deploy it with `scripts/deploy.py`.
The [release notes](docs/RELEASES.md) list what each version changed, and
the installer is at https://example.com/widget/install.sh.

Logs are written to /var/log/widget.log. The endpoints are listed under
api/v2.0 of the reference. A plugin adds its own settings in a file such
as `plugins/extra.toml` <!-- example --> beside the main one.

Per-machine overrides live in the home directory. <!-- example -->
