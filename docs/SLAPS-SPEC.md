# SLAPS — Swarm LLM Automated Project System (Product Spec)

Version: 0.9 (draft)
Owners: James (@repo owner), AGENT
Status: Active design; GH-mode canonical

## Purpose

SLAPS coordinates a swarm of LLM workers to execute a GitHub issue backlog in “waves,” using GitHub Issues + Projects as the single source of truth (SoT) for task state, dependencies, attempts, and audit trail. The local filesystem is used only as a mutex (locks) and for live logs/telemetry.

## Goals

- Orchestrate many concurrent LLM workers safely and deterministically against a shared repo branch.
- Use GitHub as the canonical state store for issue lifecycle and dependencies.
- Eliminate race conditions around claiming work; make recovery idempotent and restart‑safe.
- Provide rich observability (JSONL, logs, GH comments, Project draft items, optional Wave Status Issues).
- Enforce repo guardrails (no git ops by workers; tests in Docker via Guardian).

## Non‑Goals

- Workers do not perform git branching/pushing. They do not run tests (Guardian does).
- SLAPS is not a GitHub Actions runner replacement; it complements CI.

## Glossary

- Issue = GitHub Issue (task).
- Wave = Set of issues labeled `milestone::M{n}`.
- Project P = GitHub Project (v2) used to track SLAPS fields.
- Fields (Project item fields):
  - `slaps-state` (SINGLE_SELECT): one of `open | closed | claimed | failure | dead | blocked`.
  - `slaps-worker` (NUMBER): worker id that claimed.
  - `slaps-attempt-count` (NUMBER): 0..3 attempts.
  - `slaps-wave` (NUMBER): wave number.
- Labels: `slaps-wip`, `slaps-did-it`, `slaps-failed`.
- “Plan” comment: Markdown comment starting with `## TASKS` and containing a `## Prompt` fenced block (```text ... ```), the authoritative prompt for the next attempt.

## Canonical Sources of Truth

- GitHub Project fields and Issue comments/labels.
- Dependencies from GitHub Issue GraphQL `blockedBy` connections.
- Filesystem: only locks and logs (non‑authoritative).

## High‑Level Workflow

1) Coordinator (GH mode)
- Preflight gh auth + scopes; ensure Project `SLAPS-{repo}` (or specified name) exists; ensure fields/labels.
- For wave N:
  - (Optional) Create “SLAPS Wave {N}” status issue; add to Project.
  - Initialize items for wave N: add all issues labeled `milestone::M{N}` to the Project, set fields `blocked` `attempt=0` `wave=N`.
  - Start Watcher+Workers (GH mode) with `WAVE_STATUS_ISSUE` env to enable progress comments.
  - When watcher finishes (no `open|blocked|failure|claimed` remaining), run Guardian (Docker tests + healing). If Guardian fails or any `dead` exists → abort wave.
  - Push on success, advance to next wave.

2) Watcher (GH mode)
- Leader election via heartbeat file prevents dual control planes.
- Periodically:
  - Translate filesystem lock files into `slaps-worker` and `slaps-state=claimed` (only leader processes locks).
  - Unlock sweep: open items whose blockers (GH `blockedBy`) are satisfied (all closed or prior wave); increment attempt on open (but only if `<3`).
  - Reconcile: if GH Issue is CLOSED but `slaps-state!=closed`, set `closed`.

3) Worker (GH mode)
- Polls for `slaps-state=open` items for the current wave.
- Claim: create JSON lock `.slaps/tasks/lock/{issue}.lock.txt` atomically (O_EXCL). Verify claim once watcher sets `slaps-worker=<id>`.
- Compose prompt:
  - If latest `## TASKS` comment has a `## Prompt` fenced block → use block verbatim.
  - Else construct from Issue title/body + Acceptance Criteria section.
- Execute LLM via `codex exec`, streaming to per‑worker logs.
- On rc==0: set `slaps-state=closed`, label `slaps-did-it`, comment success; remove lock.
- On rc!=0 and attempts<3: set `failure`, post failure comment (stdout/stderr), then generate and post `## TASKS New Approach` with a new Prompt; increment attempt, set `open` again; remove lock.
- On rc!=0 and attempts>=3: mark `dead`, label `slaps-failed`; remove lock.
- (Optional) Post Wave Status progress comment on each state change (when `WAVE_STATUS_ISSUE` is set).

4) Guardian
- Runs tests in Docker; heals by editing code + tests until green; pushes when successful.

## State Machine (slaps-state)

blocked → open → claimed → {closed | failure}

failure → (attempt<3) open

failure (attempt==3) → dead

Manual GH close → closed (reconciled by watcher)

## Dependencies Logic

- Blockers from GH `Issue.blockedBy`.
- A blocker is “satisfied” if:
  - Its `slaps-state=closed` in Project; or
  - It belongs to a prior wave; or
  - If not in Project, GH Issue `state=CLOSED` or labeled with prior wave.

## Concurrency and Safety

- Filesystem locks are the mutex for claims (atomic O_EXCL).
- Leader election for watcher (heartbeat file TTL) prevents double processing.
- Idempotent unlock sweeps and claim verification avoid repeated side effects.

## Limits and Policies

- Attempt limit: 3.
- Workers never perform git ops; only Guardian uses git and Docker tests.
- Rate‑limits: retries/backoff on gh API.

## Observability

- JSONL events: `.slaps/logs/events.jsonl`.
- Per‑worker logs: `.slaps/logs/workers/{id}/current-llm.*` and archived `{issue}-llm.*`.
- Project draft “SLAPS Update” items at wave start/complete; optional “Wave Status Issue” receives progress comments.
- Tmux log viewer (reuse + follow) for coordination.

## Preflight Requirements

- gh CLI installed; token scopes: `project`, `repo` (issues read/write), `read:org` if needed for org projects.
- Project fields present with the exact options for `slaps-state`.

## Acceptance Criteria

- GH is SoT for state, dependencies, and plans.
- No FS usage beyond locks/logs; no reliance on edges.csv or local DAG.
- Concurrency safe (no double claims; stale locks cleaned).
- End‑to‑end run per wave succeeds or aborts predictably with clear diagnostics.

## Risks & Mitigations

- GH API hiccups → retries/backoff; idempotent operations.
- Human edits to Project fields/options → validation guard; loud errors.
- Large projects → pagination for items/comments/deps.

## Runbook (GH mode)

- `make logs-view`
- `make slaps-watch-gh WAVE=1 PROJECT="SLAPS-{repo}"`
- Coordinator (GH mode) will manage waves and Guardian runs.

