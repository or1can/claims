"""Shared test scaffolding."""

from __future__ import annotations

import unittest

from claims import runner


class RegistryClearingTestCase(unittest.TestCase):
    """Base for tests that register checks: keeps the global registry isolated per test."""

    def setUp(self) -> None:
        runner.clear_registry()
        self.addCleanup(runner.clear_registry)
