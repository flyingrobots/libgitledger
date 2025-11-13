from __future__ import annotations

from typing import Dict

from .taskwatch.ports import GHPort, GHProject


class CoordinatorGH:
    def __init__(self, gh: GHPort):
        self.gh = gh

    def create_wave_status_issue(self, project: GHProject, wave: int) -> int:
        title = f"SLAPS Wave {wave}"
        body = (
            f"## SLAPS Wave {wave}\n\n"
            "This issue tracks progress for the wave. Comments will include progress updates.\n"
        )
        num = self.gh.create_issue(title, body)
        # Add to project
        self.gh.ensure_issue_in_project(project, num)
        return num

    def compute_counts(self, project: GHProject, wave: int) -> Dict[str, int]:
        items = self.gh.list_items(project)
        counts: Dict[str, int] = {"open": 0, "closed": 0, "blocked": 0, "claimed": 0, "failure": 0, "dead": 0}
        for it in items:
            # Filter by slaps-wave
            wave_val = None
            st = None
            for f in it.get("fields") or []:
                nm = (f.get("name") or f.get("field", {}).get("name") or "").strip()
                val = f.get("value")
                if nm == "slaps-wave":
                    try:
                        wave_val = int(val) if not isinstance(val, dict) else None
                    except Exception:
                        wave_val = None
                elif nm == "slaps-state":
                    st = val.get("name") if isinstance(val, dict) else val
            if wave_val != wave or not st:
                continue
            if st in counts:
                counts[st] += 1
        return counts

    def should_abort(self, counts: Dict[str, int]) -> bool:
        return counts.get("dead", 0) > 0

