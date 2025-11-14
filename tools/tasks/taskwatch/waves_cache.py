from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Set


class WavesCache:
    def __init__(self, path: Path, ttl_sec: int = 600):
        self.path = path
        self.ttl = ttl_sec
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> Dict[str, List[int]] | None:
        try:
            obj = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except Exception:
            return None
        try:
            ts = float(obj.get("updated_at") or 0)
            if time.time() - ts > self.ttl:
                return None
        except Exception:
            return None
        return obj.get("waves") or {}

    def write(self, waves: Dict[int, List[int]]) -> None:
        data = {
            "updated_at": time.time(),
            "waves": {str(k): v for k, v in waves.items()},
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self.path)

    def get(self, wave: int) -> List[int] | None:
        d = self.read() or {}
        arr = d.get(str(wave))
        if isinstance(arr, list):
            return [int(x) for x in arr]
        return None

    def put(self, wave: int, issues: Set[int]) -> None:
        cur = self.read() or {}
        waves = {int(k): v for k, v in ((cur or {}).get("waves") or {}).items()} if isinstance(cur, dict) else {}
        waves[wave] = sorted(list(set(int(x) for x in issues)))
        self.write(waves)

