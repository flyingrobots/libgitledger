#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    try:
        cp = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if cp.returncode != 0:
            print("[PREFLIGHT] gh auth status failed. Run 'gh auth login' and ensure 'project' scope.", file=sys.stderr)
            print(cp.stderr.strip(), file=sys.stderr)
            return 1
        # Check that 'project' scope is present
        cp2 = subprocess.run(["gh", "auth", "status", "--show-token"], capture_output=True, text=True)
        # We can't reliably parse scopes; just hint the user
        print("[PREFLIGHT] gh auth OK. Ensure your token has 'project' scope if project commands fail.")
        return 0
    except FileNotFoundError:
        print("[PREFLIGHT] GitHub CLI 'gh' not found. Install from https://cli.github.com/", file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

