# SLAPS — Technical Specification

Version: 0.9 (draft)

## Architecture

- Hexagonal / Ports & Adapters.
  - Ports: `FilePort`, `ReporterPort`, `LLMPort`, `GHPort`.
  - Adapters: LocalFS, StdoutReporter, CodexLLM, GHCLI.
  - Domain: GHWatcher, GHWorker, Coordinator, Guardian, Log Viewer.

## Components

- GHCLI (tools/tasks/taskwatch/ghcli.py)
  - Methods (selected):
    - `ensure_project(title)`, `ensure_fields(project)`, `ensure_labels([...])`.
    - Project paging: `list_items(project)` via GraphQL; fallback to CLI.
    - Wave issues: `list_issues_for_wave(wave)` via GraphQL label filter.
    - Dependencies: `get_blockers(issue)` via GraphQL `issue.blockedBy`.
    - Comments paging: `list_issue_comments(issue)` via GraphQL; fallback to CLI JSON.
    - `issue_node_id(number)`, `ensure_issue_in_project(project, number)`.
    - `add_comment`, `add_label`, `remove_label`.
    - Retries/backoff wrapper for gh invocations.

- GHWatcher (tools/tasks/taskwatch/domain_gh.py)
  - Leader election: heartbeat file `.slaps/tasks/admin/gh_watcher_leader.json`; TTL default 15s.
  - `watch_locks()`: process JSON lock files → `slaps-worker` + `slaps-state=claimed`; remove stale locks.
  - `unlock_sweep(wave)`: open eligible issues (attempt<3); reconcile GH CLOSED issues to `closed`.
  - Only the leader executes locks/unlocks.

- GHWorker (tools/tasks/taskwatch/domain_gh.py)
  - Claim: create JSON lock with O_EXCL; verify claim by reading Project fields.
  - Compose prompt: latest `## TASKS` comment → `## Prompt` fenced block; fallback to issue body + AC.
  - Execute via `CodexLLM.exec`, stream logs to per‑worker files.
  - rc==0: close + label; rc!=0 & attempts<3: failure comment + remediation `## TASKS New Approach` + reopen; rc!=0 & attempts>=3: dead + label.
  - Optional wave progress comment per event (env `WAVE_STATUS_ISSUE`).

- Coordinator (tools/tasks/coordinate_waves.py)
  - GH mode (to be added): create Wave Status Issue; launch GH watcher; compute abort conditions from Project; post updates; run Guardian and push.

## Data Models

- Project item fields:
  - `slaps-state` (SINGLE_SELECT): values must include `open|closed|claimed|failure|dead|blocked` (validated at preflight).
  - `slaps-worker` (NUMBER); `slaps-attempt-count` (NUMBER); `slaps-wave` (NUMBER).

- Lock file JSON schema:
  ```json
  { "worker_id": 123, "pid": 4567, "started_at": 1712345678.9, "est_timeout_sec": 1200 }
  ```

- Comments formats:
  - Plan: `## TASKS` + `## Prompt` fenced ```text block.
  - Failure: "## SLAPS Worker Attempt FAILED" with stdout/stderr details.
  - Remediation: "## TASKS New Approach" with table and new Prompt block.
  - Progress: "## SLAPS Progress Update" with counts and blocked-by bullets.

- JSONL events: `.slaps/logs/events.jsonl` (event, ts, worker, task, rc, etc.).

## Algorithms

- Leader election: read heartbeat; if stale (now - ts > TTL), write heartbeat and act as leader; else stand down. Periodic `_heartbeat()` updates.
- Claim: create lock (O_EXCL). Watcher processes lock → claimed. Worker verifies `slaps-worker` matches id within timeout; else releases lock.
- Unlock: for each wave item in `blocked|failure`, if all blockers satisfied, increment attempt (<3) and set `open`.
- Remediation: on failure (<3), post “New Approach” with updated Prompt; reopen with attempt+1.
- Dead: on failure at attempt≥3, set `dead`.
- Reconciliation: set `closed` if GH issue is CLOSED.

## Error Handling & Retries

- gh CLI calls use retry/backoff (0/200/500ms).
- Fallback CLI endpoints for GraphQL failures (items/comments).
- Missing `slaps-state` options → fatal with explicit message.
- Stale lock cleanup avoids indefinite blocking.

## Configuration

- Project title default: `SLAPS-{repo}`; override via `--project` or `PROJECT` Make var.
- Wave number: `--wave N` / `WAVE=N`.
- `WAVE_STATUS_ISSUE`: issue number for per‑event progress comments.
- Timeouts: verify claim (default 60s), lock TTL (default 1800s), heartbeat TTL (default 15s).

## CLI & Make Targets

- `make slaps-watch-gh WAVE=1 [PROJECT="P"]` — GH watcher/workers.
- `make gh-tasks-test` — unit tests for GH mode.
- `make logs-view` — tmux log viewer (reuse + follow).

## Testing Strategy

- Unit tests with FakeGH cover:
  - Preflight/init/open roots; unlock dependent on blocker close or prior wave.
  - Leader election; stale lock cleanup; non-leader stands down.
  - Latest `## TASKS` prompt selection.
  - Dead on 3rd failure; remediation + reopen on earlier failures.
- Planned tests:
  - Coordinator GH mode E2E (FakeGH): normal and dead‑abort paths.
  - Comments pagination >100.
  - Retry wrapper behavior.
  - SINGLE_SELECT option guard failure.
  - Manual GH close reconciliation.

## Performance & Scale

- Workers = CPU cores; lock contention resolved via filesystem atomic create.
- Project/list/comments/deps paginated (100/page) with minimal payloads.
- Coalesce progress comments (future) to avoid spam.

## Security & Compliance

- Do not include secrets in comments or logs.
- Required scopes documented; preflight verifies `gh auth status`.

## Future Work

- Pure GH claims (CAS‑like) if/when API supports atomic field updates with conflict detection.
- Auto‑link PRs to issues; richer Guardian heuristics.

