from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Protocol


class _GHBlockersPort(Protocol):
    def get_blockers(self, issue_number: int) -> List[int]: ...


class BlockersCache:
    def __init__(self, base: Path, gh: _GHBlockersPort, ttl_sec: int = 300):
        self.base = base
        self.gh = gh
        self.ttl_sec = ttl_sec
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, issue: int) -> Path:
        return self.base / f'issue-{issue}.json'

    def get_blockers(self, issue: int) -> List[int]:
        p = self._path(issue)
        now = time.time()
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8') or '{}')
                ts = float(data.get('updated_at') or 0)
                if now - ts <= self.ttl_sec:
                    arr = data.get('blockedBy') or []
                    return [int(x) for x in arr if isinstance(x, int) or (isinstance(x, str) and x.isdigit())]
            except Exception:
                pass
        # refresh from GH
        try:
            arr = self.gh.get_blockers(issue)
        except Exception:
            arr = []
        try:
            tmp = p.with_suffix('.json.tmp')
            tmp.write_text(json.dumps({'updated_at': now, 'blockedBy': arr}), encoding='utf-8')
            tmp.replace(p)
        except Exception:
            pass
        return arr

