from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from .ports import FilePort, ReporterPort, GHPort, GHProject, GHField
from .adapters import LocalFS
from .logjson import JsonlLogger
from .domain import extract_issue_number, get_blockers_from_raw
from .cache import ItemsCache, CACHE_TELEMETRY
from .blockers_cache import BlockersCache
from .waves_cache import WavesCache


STATE_VALUES = ["open", "closed", "claimed", "failure", "dead", "blocked"]

_PROGRESS_LOCK = threading.Lock()
_PROGRESS_LAST_POST: Dict[int, float] = {}


class GHState:
    def __init__(self, project: GHProject, fields: Dict[str, GHField]):
        self.project = project
        self.fields = fields

    def field(self, name: str) -> GHField:
        return self.fields[name]


class GHWatcher:
    """Watcher that uses GitHub project fields for state and local FS locks for claims."""

    def __init__(self, gh: GHPort, fs: FilePort, reporter: ReporterPort, logger: Optional[JsonlLogger], raw_dir: Path, lock_dir: Path, project_title: str):
        self.gh = gh
        self.fs = fs
        self.r = reporter
        self.log = logger
        self.raw_dir = raw_dir
        self.lock_dir = lock_dir
        self.project_title = project_title
        self.state: Optional[GHState] = None
        self.admin_dir = Path('.slaps/tasks/admin')
        self.fs.mkdirs(self.admin_dir)
        self.leader_heartbeat = self.admin_dir / 'gh_watcher_leader.json'
        self.leader_ttl_sec = 15
        self.lock_ttl_sec = 1800  # default lease window for stale lock cleanup
        self.progress_debounce_sec = 5
        self._last_progress_post: float = 0.0
        self.cache = ItemsCache(Path('.slaps/cache/project_items.json'))
        self.blockers_cache = BlockersCache(Path('.slaps/cache/blockers'), gh=self.gh, ttl_sec=getattr(self, 'blockers_ttl_sec', 300))
        self.waves_cache = WavesCache(Path('.slaps/cache/waves.json'), ttl_sec=600)
        # refresh interval and blockers TTL tunables
        try:
            self.refresh_interval_sec = max(5, int(os.environ.get('SLAPS_REFRESH_SEC', '60')))
        except Exception:
            self.refresh_interval_sec = 60
        try:
            self.blockers_ttl_sec = max(30, int(os.environ.get('SLAPS_BLOCKERS_TTL', '300')))
        except Exception:
            self.blockers_ttl_sec = 300
        try:
            self.cache_hit_warn = float(os.environ.get('SLAPS_CACHE_HIT_WARN', '0.7'))
        except Exception:
            self.cache_hit_warn = 0.7
        self.cache_hit_warn = min(max(self.cache_hit_warn, 0.0), 1.0)
        self._last_cache_refresh_ts: float = 0.0
        self._last_cache_stats_log = 0.0

    def _emit(self, event: str, **kw) -> None:
        if self.log:
            self.log.emit(event, **kw)

    def preflight(self, wave: int) -> None:
        project = self.gh.ensure_project(self.project_title)
        fields = self.gh.ensure_fields(project, STATE_VALUES)
        self.state = GHState(project, fields)
        # Validate slaps-state options present
        try:
            st = fields["slaps-state"]
            required = {"open", "closed", "claimed", "failure", "dead", "blocked"}
            have = set((st.options or {}).keys())
            missing = required - have
            if missing:
                raise RuntimeError(f"slaps-state field missing options: {sorted(missing)}")
        except KeyError:
            raise RuntimeError("slaps-state field not found in project fields")
        # Ensure labels
        self.gh.ensure_labels(["slaps-wip", "slaps-did-it", "slaps-failed"])
        # Ensure lock dir exists
        self.fs.mkdirs(self.lock_dir)
        self.r.report(f"[SYSTEM] GH project ready: {project.title} (#{project.number})")
        self._emit("gh_preflight", project=project.title, number=project.number)

    def _now(self) -> float:
        import time as _t
        return _t.time()

    def _is_leader(self) -> bool:
        import json, os, socket
        # Try to acquire leadership if there is no fresh heartbeat
        now = self._now()
        if self.leader_ttl_sec <= 0:
            try:
                payload = json.dumps({'pid': os.getpid(), 'host': socket.gethostname(), 'ts': now})
                self.leader_heartbeat.write_text(payload, encoding='utf-8')
            except Exception:
                pass
            return True
        # Read existing heartbeat
        fresh = False
        if self.fs.exists(self.leader_heartbeat):
            try:
                data = json.loads(self.leader_heartbeat.read_text(encoding='utf-8'))
                ts = float(data.get('ts') or 0)
                if now - ts < self.leader_ttl_sec:
                    fresh = True
            except Exception:
                pass
        if fresh:
            return False
        # Become leader by writing our heartbeat
        try:
            payload = json.dumps({'pid': os.getpid(), 'host': socket.gethostname(), 'ts': now})
            self.leader_heartbeat.write_text(payload, encoding='utf-8')
            return True
        except Exception:
            return False

    def _heartbeat(self) -> None:
        import json, os, socket
        try:
            self.leader_heartbeat.write_text(json.dumps({'pid': os.getpid(), 'host': socket.gethostname(), 'ts': self._now()}), encoding='utf-8')
        except Exception:
            pass

    def ensure_cached_issue(self, issue: int, evict: bool = False) -> None:
        raw_file = self.raw_dir / f"issue-{issue}.json"
        if evict and raw_file.exists():
            try:
                raw_file.unlink()
            except Exception:
                pass
        if raw_file.exists():
            return
        try:
            data = self.gh.fetch_issue_json(issue)
            # Write as a minimal cache; relationships may already exist from prior import
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            raw_file.write_text(json.dumps(data), encoding='utf-8')
        except Exception:
            pass

    def _list_wave_issues_from_gh(self, wave: int) -> Set[int]:
        # Try cache first
        cached = None
        try:
            cached = self.waves_cache.get(wave)
        except Exception:
            cached = None
        if cached:
            if self.r:
                self.r.report(f"[SYSTEM] Wave discovery (CACHE): found {len(cached)} issues for wave {wave}")
            return set(int(x) for x in cached)
        # Primary: ask GitHub (label milestone::M{wave} or milestone title fallback)
        try:
            nums = self.gh.list_issues_for_wave(wave)
            if nums:
                if self.r:
                    self.r.report(f"[SYSTEM] Wave discovery (GH): found {len(nums)} issues for wave {wave}")
                out = set(int(n) for n in nums)
                try:
                    self.waves_cache.put(wave, out)
                except Exception:
                    pass
                return out
        except Exception as e:
            if self.r:
                self.r.report(f"[SYSTEM] Wave discovery (GH) failed: {e}")
        # Fallback: read raw cache under .slaps/tasks/raw
        out: Set[int] = set()
        try:
            for jf in sorted(self.raw_dir.glob('issue-*.json')):
                try:
                    data = json.loads(jf.read_text(encoding='utf-8'))
                except Exception:
                    continue
                num = data.get('number')
                if not isinstance(num, int):
                    continue
                labels = data.get('labels') or []
                ok = False
                for lab in labels:
                    name = lab.get('name') if isinstance(lab, dict) else None
                    if isinstance(name, str) and name.strip() == f"milestone::M{wave}":
                        ok = True
                        break
                # Also allow milestone title like "M{wave}" or "Wave {wave}"
                if not ok:
                    ms = data.get('milestone') or {}
                    title = ms.get('title') if isinstance(ms, dict) else None
                    if isinstance(title, str):
                        if title.strip() == f"M{wave}" or title.strip().lower() == f"wave {wave}":
                            ok = True
                if ok:
                    out.add(num)
        except Exception as e:
            if self.r:
                self.r.report(f"[SYSTEM] Wave discovery (RAW) failed: {e}")
        if out and self.r:
            self.r.report(f"[SYSTEM] Wave discovery (RAW): found {len(out)} issues for wave {wave}")
        # Write what we found to cache
        try:
            if out:
                self.waves_cache.put(wave, out)
        except Exception:
            pass
        return out

    # Back-compat shim: older caller expects a RAW-based enumerator name. Our GH
    # enumerator already falls back to RAW when GH is unavailable, so just proxy.
    def _list_wave_issues_from_raw(self, wave: int) -> Set[int]:
        return self._list_wave_issues_from_gh(wave)

    def initialize_items(self, wave: int) -> None:
        assert self.state is not None
        project = self.state.project
        f_state = self.state.field("slaps-state")
        f_wave = self.state.field("slaps-wave")
        f_attempt = self.state.field("slaps-attempt-count")

        issues = sorted(self._list_wave_issues_from_gh(wave))
        if not issues and self.r:
            self.r.report(f"[SYSTEM] No issues discovered for wave {wave}. Ensure label 'milestone::M{wave}' or milestone 'M{wave}'.")
        for issue in issues:
            item_id = self.gh.ensure_issue_in_project(project, issue)
            # Set initial fields: wave, attempt=0, state=blocked
            self.gh.set_item_number_field(project, item_id, f_wave, wave)
            self.gh.set_item_number_field(project, item_id, f_attempt, 0)
            self.gh.set_item_single_select(project, item_id, f_state, "blocked")
            self._emit("init_item", issue=issue, item_id=item_id, wave=wave)
        self.r.report(f"[SYSTEM] Initialized wave {wave} issues in project")
        # Prime cache after initialization
        try:
            self.refresh_cache()
        except Exception:
            pass

    def _get_field_value(self, fields_map: Dict[str, str], name: str) -> Optional[str]:
        return fields_map.get(name)

    def _blockers_satisfied(self, wave: int, issue: int) -> bool:
        assert self.state is not None
        project = self.state.project
        # Lookup blockers from cached dependencies (reduces GH calls)
        try:
            blockers = set(self.blockers_cache.get_blockers(issue))
        except Exception:
            blockers = set()
        if not blockers:
            return True
        snapshot = self.cache.read() or {}
        cached_items: Dict[int, dict] = {}
        for it in (snapshot.get('items') or []):
            try:
                num = int(it.get('num'))
            except Exception:
                continue
            cached_items[num] = it
        for b in blockers:
            it = cached_items.get(b)
            if it:
                fields = it.get('fields') or {}
                st = self._get_field_value(fields, "slaps-state")
                bwave = self._get_field_value(fields, "slaps-wave")
                try:
                    bwave = int(bwave) if bwave is not None else None
                except Exception:
                    bwave = None
                if st == "closed":
                    continue
                if bwave is not None and bwave < wave:
                    continue
                return False
            else:
                try:
                    meta = self.gh.fetch_issue_json(b)
                except Exception:
                    meta = {}
                state = (meta.get('state') or '').lower()
                if state == 'closed':
                    continue
                bwave = self.gh.get_issue_wave_by_label(b)
                if bwave is not None and bwave < wave:
                    continue
                return False
        return True

    def unlock_sweep(self, wave: int) -> None:
        # Only leader performs unlocks to avoid double work
        if not self._is_leader():
            return
        assert self.state is not None
        prj = self.state.project
        f_state = self.state.field("slaps-state")
        opened = 0
        # Use cache snapshot for decision; avoid a fresh list_items call
        cached = self.cache.read() or {}
        items_list = cached.get('items') or []
        # Build quick map num -> fields
        items_map = {int(it.get('num')): it for it in items_list if isinstance(it, dict) and isinstance(it.get('num'), (int, str))}
        wave_issues = self._list_wave_issues_from_gh(wave)
        for issue in list(wave_issues):
            it = items_map.get(int(issue))
            if issue not in wave_issues:
                continue
            # fields from cache are already flattened
            fields = (it or {}).get('fields') or {}
            st = self._get_field_value(fields, "slaps-state")
            if st in ("blocked", "failure"):
                if self._blockers_satisfied(wave, issue):
                    # Only open if attempt count < 3. Dead-letter is handled at worker time.
                    f_attempt = self.state.field("slaps-attempt-count")
                    try:
                        cur = int(self._get_field_value(fields, "slaps-attempt-count") or "0")
                    except Exception:
                        cur = 0
                    if cur < 3 and it and it.get('id'):
                        self.gh.set_item_number_field(prj, it['id'], f_attempt, cur + 1)
                        self.gh.set_item_single_select(prj, it['id'], f_state, "open")
                        opened += 1
                        self._emit("unlock_open", issue=issue)
        if opened:
            self.r.report(f"[SYSTEM] Opened {opened} issues in wave {wave}")
        # Refresh cache after reconciliation/opening (force when mutations occurred)
        try:
            self.refresh_cache(force=opened > 0)
        except Exception:
            pass
        # Reconcile occasionally via cache; skip heavy per-item API reconciliation here

    def watch_locks(self) -> None:
        """Process new lock files by marking issues as claimed and recording the worker id in GH fields.

        Format of lock filename: {issue}.lock.txt ; file content should contain worker id as integer.
        """
        # Only leader processes locks
        if not self._is_leader():
            return
        assert self.state is not None
        prj = self.state.project
        f_state = self.state.field("slaps-state")
        f_worker = self.state.field("slaps-worker")
        new_claims: list[tuple[int,int]] = []  # (issue, worker)
        for lock in sorted(self.lock_dir.glob("*.lock.txt")):
            issue = extract_issue_number(lock)
            if issue is None:
                continue
            # Parse lock payload
            wid = None
            started_at = None
            try:
                text = lock.read_text(encoding='utf-8').strip()
                if text.startswith('{'):
                    import json
                    data = json.loads(text)
                    wid = int(data.get('worker_id'))
                    started_at = float(data.get('started_at') or 0)
                else:
                    wid = int(text.splitlines()[0])
            except Exception:
                continue
            # Stale lock cleanup
            if started_at:
                if self._now() - started_at > self.lock_ttl_sec:
                    try:
                        lock.unlink(missing_ok=True)
                    except Exception:
                        pass
                    continue
            item_id = self.gh.ensure_issue_in_project(prj, issue)
            self.gh.set_item_number_field(prj, item_id, f_worker, wid)
            self.gh.set_item_single_select(prj, item_id, f_state, "claimed")
            self.gh.add_label(issue, "slaps-wip")
            self._emit("claimed", issue=issue, worker=wid)
            self.r.report(f"[SYSTEM] Claimed issue #{issue} for worker {wid}")
            new_claims.append((issue, wid))
        # Update heartbeat at end of pass
        self._heartbeat()
        # Post a single coalesced progress comment for all claims in this pass
        if new_claims:
            try:
                import os as _os
                wave_issue_env = _os.environ.get('WAVE_STATUS_ISSUE')
                if wave_issue_env and wave_issue_env.isdigit():
                    wave_issue_num = int(wave_issue_env)
                    tmpw = GHWorker(worker_id=new_claims[0][1], gh=self.gh, fs=self.fs, reporter=self.r, logger=self.log, locks=self.lock_dir, project=prj, fields=self.state.fields, wave=_os.environ.get('TASK_WAVE') and int(_os.environ.get('TASK_WAVE')) or None, wave_issue=wave_issue_num)
                    # Debounce posting
                    now = self._now()
                    if self.progress_debounce_sec <= 0 or (now - self._last_progress_post) >= self.progress_debounce_sec:
                        md = tmpw._compose_progress_md(tmpw.wave or 0)
                        self.gh.add_comment(wave_issue_num, md)
                        self._last_progress_post = now
            except Exception:
                pass
        # Refresh cache after claims processed; force when we mutated GH state
        try:
            self.refresh_cache(force=bool(new_claims))
        except Exception:
            pass

    def refresh_cache(self, force: bool = False) -> None:
        """Leader fetches items from GH and writes a simplified shared cache.

        Workers read this cache to find open issues, reducing GH API calls.
        """
        if not self._is_leader():
            return
        import time as _t
        now = _t.time()
        if not force and (now - self._last_cache_refresh_ts) < self.refresh_interval_sec:
            return
        assert self.state is not None
        items = self.gh.list_items(self.state.project)
        simple = []
        for it in items:
            num = (it.get('content') or {}).get('number')
            if not isinstance(num, int):
                continue
            fields_map = {}
            for f in it.get('fields') or []:
                nm = (f.get('name') or f.get('field', {}).get('name') or '').strip()
                val = f.get('value')
                fields_map[nm] = val.get('name') if isinstance(val, dict) else val
            simple.append({'id': it.get('id'), 'num': num, 'fields': fields_map})
        self.cache.write(simple, now)
        self._last_cache_refresh_ts = now
        self._log_cache_stats()

    def _log_cache_stats(self) -> None:
        stats = CACHE_TELEMETRY.snapshot(reset=True)
        if not stats:
            return
        hit = stats.get('fields_hit', 0)
        miss = stats.get('fields_miss', 0)
        total = hit + miss
        payload = dict(stats)
        if total:
            payload['fields_hit_rate'] = hit / total
        if self.log:
            self.log.emit('cache_stats', **payload)
        warning = False
        rate_pct = 0.0
        if total:
            rate = hit / total
            rate_pct = rate * 100.0
            if rate < self.cache_hit_warn:
                warning = True
        if self.r and total:
            prefix = "[CACHE WARNING]" if warning else "[CACHE]"
            self.r.report(f"{prefix} fields hit {hit}/{total} ({rate_pct:.1f}%) open_calls={stats.get('open_calls',0)} find_calls={stats.get('find_calls',0)}")
        if warning and self.log:
            self.log.emit('cache_stats_warning', threshold=self.cache_hit_warn, fields_hit=hit, fields_total=total)

    def reconcile_closed_state(self) -> None:
        """Occasional lightweight reconciliation: when GH issue is CLOSED, set slaps-state to closed.

        To minimize GH calls, sample at most N items per run and only for items whose
        cached state is not already 'closed'. Controlled by SLAPS_RECONCILE_SEC and
        SLAPS_RECONCILE_MAX (default 600s / 10 items).
        """
        if not self._is_leader():
            return
        try:
            import time as _t, os as _os
            interval = int(_os.environ.get('SLAPS_RECONCILE_SEC', '600'))
            limit = int(_os.environ.get('SLAPS_RECONCILE_MAX', '10'))
        except Exception:
            interval = 600
            limit = 10
        if not hasattr(self, '_last_reconcile_ts'):
            self._last_reconcile_ts = 0.0
        now = __import__('time').time()
        if now - self._last_reconcile_ts < interval:
            return
        self._last_reconcile_ts = now
        data = self.cache.read() or {}
        items = data.get('items') or []
        count = 0
        for it in items:
            if count >= limit:
                break
            num = it.get('num')
            fields = it.get('fields') or {}
            st = fields.get('slaps-state')
            if st == 'closed':
                continue
            try:
                istate = self.gh.fetch_issue_json(int(num)).get('state')
            except Exception:
                continue
            if istate == 'CLOSED' and it.get('id'):
                try:
                    f_state = self.state.field('slaps-state')
                    self.gh.set_item_single_select(self.state.project, it['id'], f_state, 'closed')
                    count += 1
                except Exception:
                    pass


class GHWorker:
    def __init__(self, worker_id: int, gh: GHPort, fs: FilePort, reporter: ReporterPort, logger: Optional[JsonlLogger], locks: Path, project: GHProject, fields: Dict[str, GHField], wave: int | None = None, wave_issue: int | None = None):
        self.worker_id = worker_id
        self.gh = gh
        self.fs = fs
        self.r = reporter
        self.log = logger
        self.locks = locks
        self.project = project
        self.fields = fields
        self.wave = wave
        self.wave_issue = wave_issue
        try:
            self.items_cache = ItemsCache(Path('.slaps/cache/project_items.json'))
        except Exception:
            self.items_cache = None
        self._progress_cooldown = self._resolve_progress_cooldown()

    def _emit(self, event: str, **kw) -> None:
        if self.log:
            self.log.emit(event, worker=self.worker_id, **kw)

    def _resolve_progress_cooldown(self) -> int:
        try:
            return max(30, int(os.environ.get('SLAPS_PROGRESS_MIN_SEC', '120')))
        except Exception:
            return 120

    def _cached_issue_fields(self, issue: int) -> Optional[Dict[str, str]]:
        cache = getattr(self, 'items_cache', None)
        if cache is None:
            return None
        try:
            fields = cache.get_fields(issue=issue)
        except Exception:
            return None
        return fields

    def _fields_confirm_claim(self, fields: Optional[Dict[str, str]]) -> bool:
        if not fields:
            return False
        try:
            wid = int(fields.get("slaps-worker") or 0)
        except Exception:
            wid = 0
        return wid == self.worker_id

    def _cache_confirms_claim(self, issue: int) -> bool:
        return self._fields_confirm_claim(self._cached_issue_fields(issue))

    def _should_post_progress(self) -> bool:
        if not self.wave_issue:
            return False
        cooldown = self._progress_cooldown
        now = time.time()
        with _PROGRESS_LOCK:
            last = _PROGRESS_LAST_POST.get(self.wave_issue)
            if last and (now - last) < cooldown:
                return False
            _PROGRESS_LAST_POST[self.wave_issue] = now
        return True

    def _atomic_lock_create(self, issue: int) -> bool:
        self.fs.mkdirs(self.locks)
        p = self.locks / f"{issue}.lock.txt"
        try:
            # atomic create JSON payload
            import json, time as _t, os as _os
            fd = _os.open(p, _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(json.dumps({"worker_id": self.worker_id, "pid": os.getpid(), "started_at": _t.time(), "est_timeout_sec": 1200}))
            return True
        except FileExistsError:
            return False

    def _remove_lock(self, issue: int) -> None:
        try:
            (self.locks / f"{issue}.lock.txt").unlink(missing_ok=True)
        except Exception:
            pass

    def _list_open_issues(self, wave: int) -> List[int]:
        # Prefer shared cache written by the watcher to avoid GH calls.
        try:
            return self.gh_cache_get_open(wave)
        except Exception:
            # Fallback (rare): attempt a direct scan if cache missing
            items = self.gh.list_items(self.project)
            out: List[int] = []
            for it in items:
                content = it.get("content") or {}
                num = content.get("number")
                fields = { (f.get("name") or f.get("field", {}).get("name") or "").strip(): f.get("value") for f in (it.get("fields") or []) }
                st = fields.get("slaps-state")
                st = st.get("name") if isinstance(st, dict) else st
                wv = fields.get("slaps-wave")
                try:
                    wv = int(wv) if not isinstance(wv, dict) else None
                except Exception:
                    wv = None
                if num and st == "open" and wv == wave:
                    out.append(num)
            return sorted(out)

    def gh_cache_get_open(self, wave: int) -> List[int]:
        # Wait briefly for cache to appear on first use
        cf = ItemsCache(Path('.slaps/cache/project_items.json'))
        data = cf.read()
        if not data:
            import time as _t
            for _ in range(3):
                _t.sleep(2)
                data = cf.read()
                if data:
                    break
        return cf.get_open_issues(wave)

    def claim_and_verify(self, issue: int, timeout: float = 60.0) -> bool:
        if not self._atomic_lock_create(issue):
            self.r.report(f"[WORKER:{self.worker_id:03d}] Lock exists for #{issue}; skipping")
            return False
        self._emit("lock_create", issue=issue)
        # Wait for watcher to set GH fields
        start = time.time()
        item_id = self.gh.ensure_issue_in_project(self.project, issue)
        attempts = 0
        remote_checked = False
        while time.time() - start < timeout:
            if self._cache_confirms_claim(issue):
                self.r.report(f"[WORKER:{self.worker_id:03d}] Verified claim on #{issue} (cache)")
                return True
            attempts += 1
            # As a fallback, hit the API once after several cache misses
            if not remote_checked and attempts >= 5:
                fields = self.gh.get_item_fields(self.project, item_id)
                if self._fields_confirm_claim(fields):
                    self.r.report(f"[WORKER:{self.worker_id:03d}] Verified claim on #{issue}")
                    return True
                remote_checked = True
            time.sleep(2)
        # Timed out; relinquish
        self._remove_lock(issue)
        self._emit("claim_timeout", issue=issue)
        self.r.report(f"[WORKER:{self.worker_id:03d}] Claim timeout #{issue}; releasing lock")
        return False

    def _extract_ac(self, body: str) -> Optional[str]:
        lines = body.splitlines()
        start = None
        for i, ln in enumerate(lines):
            if ln.strip().lower().startswith("## acceptance criteria"):
                start = i
                break
        if start is None:
            return None
        out = []
        for j in range(start, len(lines)):
            if j > start and lines[j].strip().startswith("## "):
                break
            out.append(lines[j])
        return "\n".join(out).strip()

    def _latest_tasks_comment(self, issue: int) -> Optional[str]:
        try:
            comments = self.gh.list_issue_comments(issue)
        except Exception:
            comments = []
        latest = None
        latest_ts = None
        for c in comments:
            body = c.get("body") or ""
            if body.strip().startswith("## TASKS"):
                ts = c.get("createdAt") or ""
                if latest is None or ts > (latest_ts or ""):
                    latest = body
                    latest_ts = ts
        return latest

    def _extract_prompt_block(self, text: str) -> Optional[str]:
        # Try to extract a fenced block (``` or ```lang)
        import re
        m = re.search(r"```[a-zA-Z]*\n([\s\S]*?)\n```", text)
        if m:
            return m.group(1).strip()
        return None

    def _compose_prompt(self, issue: int) -> str:
        raw = Path('.slaps/tasks/raw') / f"issue-{issue}.json"
        title = f"Issue #{issue}"
        body = ""
        if raw.exists():
            try:
                data = json.loads(raw.read_text(encoding='utf-8'))
                title = data.get('title') or title
                body = data.get('body') or ''
            except Exception:
                pass
        if not body:
            try:
                meta = self.gh.fetch_issue_json(issue)
                title = meta.get('title') or title
                body = meta.get('body') or body
            except Exception:
                pass
        ac = self._extract_ac(body) or "## Acceptance Criteria\n- Execute the task as described."
        plan = self._latest_tasks_comment(issue)
        plan_prompt = self._extract_prompt_block(plan) if plan else None
        if plan_prompt:
            return plan_prompt
        # Fall back to constructing a prompt from issue body + AC if no plan found
        return (
            "You are an autonomous repo assistant. Follow all repository rules.\n\n"
            f"Task: {title}\n\n"
            f"Details (from issue body):\n\n{body}\n\n"
            f"{ac}\n\n"
            "Important:\n- DO NOT perform git operations.\n- Write failing tests first, then implementation.\n- Do not run tests directly; rely on repository tooling.\n"
        )

    def _comment_wip(self, issue: int, attempt: int, prompt: str) -> None:
        md = (
            f"# SLAPS: Worker WIP\n\n"
            f"Worker {self.worker_id} has claimed this issue and is about to begin attempt number {attempt} using the following LLM prompt:\n\n"
            f"## Prompt\n\n````text\n{prompt}\n````\n\n"
            "(NOTE: this message was automatically generated by a SLAPS worker swarm 🦾 beep-boop)\n"
        )
        try:
            self.gh.add_comment(issue, md)
        except Exception:
            pass

    def _comment_failure(self, issue: int, stdout_text: str, stderr_text: str, state: str) -> None:
        md = (
            f"## SLAPS Worker Attempt FAILED\n\n"
            f"🚨 Worker #{self.worker_id} failed to resolve this issue. The following are the `stdout` and `stderr` streams from the LLM that made the attempt.\n\n"
            f"<details>\n<summary>STDOUT</summary>\n\n```text\n{stdout_text}\n```\n</details>\n\n"
            f"<details>\n<summary>STDERR</summary>\n\n```text\n{stderr_text}\n```\n</details>\n\n"
            f"The issue is now marked as: {state}\n\n"
            "(NOTE: This message was automatically generated by a SLAPS worker swarm 🦾 beep-boop)\n"
        )
        try:
            self.gh.add_comment(issue, md)
        except Exception:
            pass

    def _comment_success(self, issue: int) -> None:
        md = (
            f"## SLAPS Worker Did It\n\n"
            f"✌️ Worker #{self.worker_id} successfully resolved this issue.\n\n"
            "(NOTE: This message was automatically generated by a SLAPS worker swarm 🦾 beep-boop)\n"
        )
        try:
            self.gh.add_comment(issue, md)
        except Exception:
            pass

    def work_issue(self, issue: int, llm) -> bool:
        # Compose prompt and post WIP comment
        item_id = self.gh.ensure_issue_in_project(self.project, issue)
        fields = self.gh.get_item_fields(self.project, item_id)
        try:
            attempt = int(fields.get("slaps-attempt-count") or "1")
        except Exception:
            attempt = 1
        prompt = self._compose_prompt(issue)
        self._comment_wip(issue, attempt, prompt)

        # Execute
        logs_dir = Path('.slaps/logs/workers') / f"{self.worker_id:03d}"
        self.fs.mkdirs(logs_dir)
        out_path = logs_dir / f"{issue}-llm.stdout.txt"
        err_path = logs_dir / f"{issue}-llm.stderr.txt"
        # truncate live
        (logs_dir / 'current-llm.stdout.txt').write_text('', encoding='utf-8')
        (logs_dir / 'current-llm.stderr.txt').write_text('', encoding='utf-8')
        rc, out, err = llm.exec(prompt, out_path=logs_dir / 'current-llm.stdout.txt', err_path=logs_dir / 'current-llm.stderr.txt')
        # archive
        (out_path).write_text(out, encoding='utf-8')
        (err_path).write_text(err, encoding='utf-8')

        f_state = self.fields["slaps-state"]
        if rc == 0:
            self.gh.set_item_single_select(self.project, item_id, f_state, "closed")
            self.gh.add_label(issue, "slaps-did-it")
            self._comment_success(issue)
            self._remove_lock(issue)
            self.r.report(f"[WORKER:{self.worker_id:03d}] LLM success task #{issue}")
            self._emit("success", issue=issue)
            self._maybe_post_progress()
            return True
        else:
            # Read current attempt count to decide dead vs remediation
            fields_now = self.gh.get_item_fields(self.project, item_id)
            try:
                cur_attempt = int(fields_now.get("slaps-attempt-count") or "1")
            except Exception:
                cur_attempt = 1
            if cur_attempt >= 3:
                # Dead letter immediately
                self.gh.set_item_single_select(self.project, item_id, f_state, "dead")
                self.gh.add_label(issue, "slaps-failed")
                self._comment_failure(issue, out, err, state="dead")
                self._remove_lock(issue)
                self.r.report(f"[WORKER:{self.worker_id:03d}] LLM error task #{issue}: exit code {rc}; marked dead")
                self._emit("dead", issue=issue, rc=rc)
                self._maybe_post_progress()
                return True
            # mark failure, post details, then generate remediation plan and reopen with attempt+1
            self.gh.set_item_single_select(self.project, item_id, f_state, "failure")
            self._comment_failure(issue, out, err, state="failure")
            # Build remediation plan (## TASKS New Approach) with a new prompt block
            rem_prompt = (
                "You are a senior engineer triaging a failed automated attempt.\n"
                "Read the following artifacts and write a concise remediation plan as a Markdown comment that starts with the heading '## TASKS New Approach'.\n"
                "Include a table with: What Went Wrong, New Plan, Why This Should Work, Confidence Index (0-1).\n"
                "Then include a 'Prompt' section with a fenced ```text block containing the exact prompt the next worker should run.\n\n"
                f"Issue #{issue} prior prompt:\n\n```text\n{prompt}\n```\n\n"
                f"LLM STDOUT (truncated):\n\n```text\n{out[:4000]}\n```\n\n"
                f"LLM STDERR (truncated):\n\n```text\n{err[:4000]}\n```\n\n"
                "Important constraints:\n- DO NOT perform git operations.\n- Plan must be specific and executable in this repository.\n- Keep the prompt self-contained.\n"
            )
            rc2, plan_md, _ = llm.exec(rem_prompt, timeout=120)
            if rc2 == 0 and plan_md.strip():
                try:
                    self.gh.add_comment(issue, plan_md)
                except Exception:
                    pass
            # Reopen for next attempt and increment attempt count now
            f_attempt = self.fields["slaps-attempt-count"]
            self.gh.set_item_number_field(self.project, item_id, f_attempt, cur_attempt + 1)
            self.gh.set_item_single_select(self.project, item_id, f_state, "open")
            self._remove_lock(issue)
            self.r.report(f"[WORKER:{self.worker_id:03d}] LLM error task #{issue}: exit code {rc}; posted remediation and reopened")
            self._emit("failure_reopen", issue=issue, rc=rc, next_attempt=cur_attempt + 1)
            self._maybe_post_progress()
            return True

    def _maybe_post_progress(self) -> None:
        if not self.wave_issue or not self.wave:
            return
        if not self._should_post_progress():
            return
        try:
            md = self._compose_progress_md(self.wave)
            self.gh.add_comment(self.wave_issue, md)
        except Exception:
            pass

    def _compose_progress_md(self, wave: int) -> str:
        cache = getattr(self, 'items_cache', None)
        snapshot = {}
        if cache:
            try:
                snapshot = cache.read() or {}
            except Exception:
                snapshot = {}
        items = snapshot.get('items') or []
        inscope: List[tuple[int, Dict[str, str]]] = []
        for entry in items:
            fields = (entry.get('fields') or {})
            try:
                entry_wave = int(fields.get('slaps-wave')) if fields.get('slaps-wave') is not None else None
            except Exception:
                entry_wave = None
            if entry_wave != wave:
                continue
            try:
                num = int(entry.get('num'))
            except Exception:
                continue
            inscope.append((num, fields))
        open_issues: List[int] = []
        blocked_issues: List[int] = []
        closed_issues: List[int] = []
        failure_issues: List[int] = []
        dead_issues: List[int] = []
        claimed_issues: List[int] = []
        for num, fields in inscope:
            st = fields.get('slaps-state')
            if st == 'open':
                open_issues.append(num)
            elif st == 'blocked':
                blocked_issues.append(num)
            elif st == 'closed':
                closed_issues.append(num)
            elif st == 'failure':
                failure_issues.append(num)
            elif st == 'dead':
                dead_issues.append(num)
            elif st == 'claimed':
                claimed_issues.append(num)
        wave_status = 'pending'
        if dead_issues:
            wave_status = 'dead'
        elif not open_issues and not blocked_issues and not failure_issues and not claimed_issues:
            wave_status = 'complete'

        def links(nums: List[int]) -> str:
            return ', '.join(f"#{x}" for x in sorted(nums)) if nums else '(none)'

        md = (
            "## SLAPS Progress Update\n\n"
            "|  |  |\n|--|--|\n"
            f"| **OPEN ISSUES:** | {len(open_issues)} ({links(open_issues)}) |\n"
            f"| **CLOSED ISSUES:** | {len(closed_issues)} ({links(closed_issues)}) |\n"
            f"| **BLOCKED ISSUES:** | {len(blocked_issues)} ({links(blocked_issues)}) |\n"
            f"| **WAVE STATUS:** | {wave_status} |\n\n"
            "### Issues\n\n"
        )

        def line(icon: str, n: int, suffix: str = '') -> str:
            return f"{icon} (#{n}){suffix}"

        rows: List[str] = []
        for n in sorted(closed_issues):
            rows.append(line('✅', n))
        for n in sorted(claimed_issues):
            rows.append(line('⏳', n))
        for n in sorted(dead_issues):
            rows.append(line('🪦', n))
        for n in sorted(failure_issues):
            rows.append(line('❌', n))
        return md + (("\n".join(rows) + "\n") if rows else '')
