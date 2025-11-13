from __future__ import annotations

from typing import Dict

from .taskwatch.ports import GHPort, GHProject


class CoordinatorGH:
    def __init__(self, gh: GHPort):
        self.gh = gh
        self.debounce_sec = 5
        self._last_post_ts: float = 0.0

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

    def compose_progress_md(self, project: GHProject, wave: int) -> str:
        items = self.gh.list_items(project)
        # Helpers
        def fval(it, name):
            for f in it.get('fields') or []:
                nm = (f.get('name') or f.get('field', {}).get('name') or '').strip()
                if nm == name:
                    v = f.get('value')
                    return v.get('name') if isinstance(v, dict) else v
            return None
        inscope = [it for it in items if fval(it, 'slaps-wave') == wave]
        open_issues = []
        blocked_issues = []
        closed_issues = []
        failure_issues = []
        dead_issues = []
        claimed_issues = []
        for it in inscope:
            num = (it.get('content') or {}).get('number')
            st = fval(it, 'slaps-state')
            if st == 'open': open_issues.append(num)
            elif st == 'blocked': blocked_issues.append(num)
            elif st == 'closed': closed_issues.append(num)
            elif st == 'failure': failure_issues.append(num)
            elif st == 'dead': dead_issues.append(num)
            elif st == 'claimed': claimed_issues.append(num)
        blocked_lines = []
        for n in blocked_issues:
            for b in self.gh.get_blockers(n) or []:
                blocked_lines.append(f"- (#{n})-[blocked by]->(#{b})")
        wave_status = 'pending'
        if dead_issues:
            wave_status = 'dead'
        elif not open_issues and not blocked_issues and not failure_issues and not claimed_issues:
            wave_status = 'complete'
        def links(nums):
            return ', '.join(f"#{x}" for x in sorted(nums)) if nums else '(none)'
        md = (
            "## SLAPS Progress Update\n\n"
            "|  |  |\n|--|--|\n"
            f"| **OPEN ISSUES:** | {len(open_issues)} |\n"
            f"| **OPEN ISSUES:** | {links(open_issues)} |\n"
            f"| **CLOSED ISSUES:** | {len(closed_issues)} |\n"
            f"| **CLOSED ISSUES:** | {links(closed_issues)} |\n"
            f"| **BLOCKED ISSUES:** | {len(blocked_issues)} |\n"
            f"| **BLOCKED ISSUES:** | {'\n'.join(blocked_lines) if blocked_lines else '(none)'} |\n"
            f"| **WAVE STATUS:** | {wave_status} |\n\n"
        )
        return md

    def post_progress_comment(self, project: GHProject, wave_issue: int, wave: int) -> None:
        import time as _t
        now = _t.time()
        if self.debounce_sec <= 0 or (now - self._last_post_ts) >= self.debounce_sec:
            md = self.compose_progress_md(project, wave)
            self.gh.add_comment(wave_issue, md)
            self._last_post_ts = now
