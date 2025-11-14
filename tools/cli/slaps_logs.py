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
    # Reuse + follow + iTerm2 attach by default
    try:
        # Start viewer
        subprocess.Popen([sys.executable, "tools/tasks/log_viewer.py", "--reuse", "--follow"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    # Attach using tmux -CC if available
    return subprocess.call(["tmux", "-CC", "attach", "-t", "slaps-logs"]) if os.environ.get("TERM_PROGRAM") == "iTerm.app" else 0


if __name__ == "__main__":
    raise SystemExit(main())

