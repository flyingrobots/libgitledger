from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


class ItemsCache:
    """Simple JSON cache for project items to reduce GitHub API pressure.

    Schema:
    {
      "updated_at": 1731560000.123,
      "items": [
        {"id": "PVTI_...", "num": 42, "fields": {"slaps-state": "open", "slaps-wave": 1, "slaps-worker": 0, "slaps-attempt-count": 1}}
      ]
    }
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, items: List[Dict[str, Any]], now_ts: float) -> None:
        data = {"updated_at": float(now_ts), "items": items}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.path)

    def read(self) -> Dict[str, Any] | None:
        try:
            text = self.path.read_text(encoding="utf-8")
            return json.loads(text or "{}")
        except Exception:
            return None

    def get_open_issues(self, wave: int) -> List[int]:
        data = self.read() or {}
        out: List[int] = []
        for it in (data.get("items") or []):
            try:
                num = int(it.get("num"))
            except Exception:
                continue
            f = it.get("fields") or {}
            st = f.get("slaps-state")
            wv = f.get("slaps-wave")
            try:
                wv = int(wv) if wv is not None else None
            except Exception:
                wv = None
            if num and st == "open" and wv == wave:
                out.append(num)
        return sorted(out)

