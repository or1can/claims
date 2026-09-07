"""Minimal CLI adapter over `claims.runner.run`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks  # noqa: F401
from .config import ConfigError, load_config
from .runner import run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="claims")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to check (default: current directory).",
    )
    parser.add_argument(
        "--diff-range",
        default="HEAD",
        help="Diff range to check, working tree against this ref (default: HEAD).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root: Path = args.repo_root.resolve()
    try:
        config = load_config(repo_root)
    except ConfigError as e:
        print(f"claims.toml is invalid: {e}", file=sys.stderr)
        return 2
    result = run(repo_root, args.diff_range, config)

    if not result.checks_run:
        print("0 checked — no checks registered (failure, not a clean pass)")
        return 1

    for finding in result.findings:
        marker = "GATE" if finding.gate else "advisory"
        print(f"[{marker}] {finding.citation} ({finding.mode}) {finding.message}")

    gate_findings = [f for f in result.findings if f.gate]
    print(
        f"{len(result.checks_run)} checked, {len(result.findings)} finding(s), "
        f"{len(gate_findings)} gate failure(s)"
    )
    return 1 if gate_findings else 0


if __name__ == "__main__":
    sys.exit(main())
