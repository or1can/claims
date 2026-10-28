# TODO

- `claims/gate.py`'s `_disabled_checks` reads a check's own `enabled` by
  truthiness, so `[stale-claims] enabled = 0` silences that check and
  `enabled = "false"` does not: the same defect #129 fixed for `[hook]
  enabled`, left out of that ticket's scope.
