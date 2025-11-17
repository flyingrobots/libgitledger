from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional
import threading


class CacheTelemetry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()

    def incr(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._counts[key] += amount

    def snapshot(self, reset: bool = False) -> Dict[str, int]:
        with self._lock:
            data = dict(self._counts)
            if reset:
                self._counts.clear()
            return data


CACHE_TELEMETRY = CacheTelemetry()


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
        CACHE_TELEMETRY.incr('open_calls')
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

    def find_item(self, *, issue: Optional[int] = None, item_id: Optional[str] = None, record: bool = True) -> Optional[Dict[str, Any]]:
        """Return cached entry for a given issue number or project item id."""
        if issue is None and item_id is None:
            return None
        if record:
            CACHE_TELEMETRY.incr('find_calls')
        data = self.read() or {}
        for it in (data.get("items") or []):
            try:
                num = int(it.get("num"))
            except Exception:
                num = None
            if issue is not None and num == issue:
                if record:
                    CACHE_TELEMETRY.incr('find_hit')
                return it
            if item_id is not None and it.get("id") == item_id:
                if record:
                    CACHE_TELEMETRY.incr('find_hit')
                return it
        if record:
            CACHE_TELEMETRY.incr('find_miss')
        return None

    def get_fields(self, *, issue: Optional[int] = None, item_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        entry = self.find_item(issue=issue, item_id=item_id, record=False)
        if not entry:
            CACHE_TELEMETRY.incr('fields_miss')
            return None
        fields = entry.get("fields")
        if isinstance(fields, dict):
            CACHE_TELEMETRY.incr('fields_hit')
            return dict(fields)
        CACHE_TELEMETRY.incr('fields_miss')
        return None
