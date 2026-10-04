"""Run a non-Python drill (k6, Playwright) under the same one-drill-at-a-time lock.

    uv run python scripts/with_lock.py <name> -- <command> [args...]

The lock is the one every Python drill takes (_inspect_common.exclusive_run); the
command inherits the environment and its exit code is passed through.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _inspect_common import exclusive_run  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] != "--":
        print("usage: with_lock.py <name> -- <command> [args...]", file=sys.stderr)
        return 2
    name, command = argv[0], argv[2:]
    # Resolved to a full path first: on Windows `pnpm` is often a .cmd shim that a bare
    # name cannot launch without a shell.
    command = [shutil.which(command[0]) or command[0], *command[1:]]
    with exclusive_run(name):
        return subprocess.call(command)  # noqa: S603 - the command is the Makefile's own


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
