#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tools.tasks.taskwatch.logjson import JsonlLogger


def load_caps() -> dict:
    p = Path('.slaps/logs/capabilities.json')
    if not p.exists():
        return {"error": "capabilities.json missing"}
    try:
        return json.loads(p.read_text(encoding='utf-8') or '{}')
    except Exception as e:
        return {"error": f"parse: {e}"}


def rate_ok(caps: dict) -> bool:
    rl = caps.get('rate_limit') or {}
    core = (rl.get('core') or {}).get('remaining')
    graphql = (rl.get('graphql') or {}).get('remaining')
    try:
        if core is not None and int(core) < 5:
            return False
        if graphql is not None and int(graphql) < 5:
            return False
    except Exception:
        pass
    return True


def fields_ok(caps: dict) -> bool:
    f = caps.get('fields') or {}
    st = (f.get('slaps-state') or {}).get('options') or {}
    required = {"open", "closed", "claimed", "failure", "dead", "blocked"}
    return required.issubset(set(st.keys()))


def main() -> int:
    log = JsonlLogger(Path('.slaps/logs/events.jsonl'))
    caps = load_caps()
    degraded = []
    if 'error' in caps:
        degraded.append(caps['error'])
    if not fields_ok(caps):
        degraded.append('slaps-state options incomplete')
    if not rate_ok(caps):
        degraded.append('rate limit low')
    if degraded:
        log.emit('degraded', reasons=degraded)
        print('sentinel: DEGRADED — ' + '; '.join(degraded))
        return 1
    log.emit('ok', msg='sentinel')
    print('sentinel: OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

