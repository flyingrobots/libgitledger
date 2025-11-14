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
    args = [sys.executable, "-m", "tools.tasks.watch_tasks_gh", *sys.argv[1:]]
    return subprocess.call(args)


if __name__ == "__main__":
    raise SystemExit(main())

