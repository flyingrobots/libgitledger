from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class JsonlLogger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def emit(self, event: str, **fields: Any) -> None:
        entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
        }
        entry.update(fields)
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

