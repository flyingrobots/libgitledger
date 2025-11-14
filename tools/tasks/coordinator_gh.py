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
        # Deduplicate: reuse existing issue if present
        existing = None
        try:
            import subprocess, json, sys
            print(f"[COORD] Looking up existing wave status issue by title: {title}", file=sys.stderr)
            cp = subprocess.run(
                ['gh','issue','list','--state','all','--search',title,'--json','number,title','--limit','100'],
                capture_output=True, text=True
            )
            if cp.returncode == 0:
                arr = json.loads(cp.stdout or '[]')
                for it in arr or []:
                    if isinstance(it, dict) and it.get('title') == title and isinstance(it.get('number'), int):
                        existing = it['number']
                        print(f"[COORD] Reusing existing issue #{existing} for wave {wave}", file=sys.stderr)
                        break
        except Exception as e:
            print(f"[COORD] Title search via gh failed: {e}", file=sys.stderr)
        if existing is None and hasattr(self.gh, 'find_issue_by_title'):
            try:
                existing = self.gh.find_issue_by_title(title)  # type: ignore[attr-defined]
                if existing:
                    print(f"[COORD] Reusing existing issue via GHPort #{existing}", file=sys.stderr)
            except Exception as e:
                print(f"[COORD] GHPort.find_issue_by_title failed: {e}", file=sys.stderr)
        if existing:
            num = existing
        else:
            num = self.gh.create_issue(title, body)
            print(f"[COORD] Created wave status issue #{num}", file=sys.stderr)
        # Add to project (best effort)
        try:
            self.gh.ensure_issue_in_project(project, num)
            print(f"[COORD] Added issue #{num} to project {project.title} ({project.number})", file=sys.stderr)
        except Exception:
            # fallback: try CLI URL add then verify via list
            try:
                import subprocess, json, sys
                # add by URL if supported
                url_cp = subprocess.run(['gh','issue','view',str(num),'--json','url','--jq','.url'], capture_output=True, text=True)
                if url_cp.returncode == 0:
                    issue_url = url_cp.stdout.strip()
                    cp2 = subprocess.run(['gh','project','item-add','--owner', project.owner, '--number', str(project.number), '--url', issue_url], capture_output=True, text=True)
                    print(f"[COORD] Fallback add by URL rc={cp2.returncode}", file=sys.stderr)
                # verify by re-scan through GHPort
                _ = self.gh.find_item_by_issue(project, num)  # type: ignore[attr-defined]
            except Exception:
                pass
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
        try:
            items = self.gh.list_items(project)
        except Exception:
            items = []
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
            try:
                bs = self.gh.get_blockers(n) or []
            except Exception:
                bs = []
            for b in bs:
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
            try:
                self.gh.add_comment(wave_issue, md)
            except Exception:
                # swallow comment failures; progress composition worked
                pass
            self._last_post_ts = now
