# Reference

`widget` reads a configuration file at startup.

## Behaviour

Native TOML configuration arrived in 0.3.0.

There is no `--output` mode yet.

`widget` now reads its own configuration.

Requires Docker 20.10 or later.

The image is pinned to `alpine:3.18.2`.

```toml
version = "1.2.3"
```

> **Status.** From 0.9.0 the reader is native.

*The reader used to be external.*

Previously said: there is no reader yet.
