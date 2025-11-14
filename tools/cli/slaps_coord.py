#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    try:
        root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
        os.chdir(root)
    except Exception:
        pass
    # Forward all args to the module
    args = [sys.executable, "-m", "tools.tasks.coordinate_waves", *sys.argv[1:]]
    return subprocess.call(args)


if __name__ == "__main__":
    raise SystemExit(main())

