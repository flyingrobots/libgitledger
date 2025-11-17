#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
slaps_go.sh - one-touch runner for SLAPS GH mode

Options:
  -w <wave>      Wave number to run (required)
  -n <workers>   SLAPS_WORKERS (default: 2)
  -r <seconds>   SLAPS_REFRESH_SEC (default: 60)
  -b <seconds>   SLAPS_BLOCKERS_TTL (default: 600)
  -R <seconds>   SLAPS_RECONCILE_SEC (default: 600)
  -i <seconds>   SLAPS_WORKER_IDLE_SLEEP (default: 60)
  -m <mode>      Coordinator mode (default: gh)
  --no-logs      Do not start the log viewer
  --             Pass the rest to the coordinator

Examples:
  tools/cli/slaps_go.sh -w 1
  tools/cli/slaps_go.sh -w 2 -n 2 -r 120 -- --no-commit-preflight
USAGE
}

# cd to repo root
if root=$(git rev-parse --show-toplevel 2>/dev/null); then
  cd "$root"
fi
# Purge any stale bytecode so updated sources are always loaded
find tools -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find tools -name '*.pyc' -delete 2>/dev/null || true

# Ensure a usable 'setsid' command for tmux helper shells
if ! command -v setsid >/dev/null 2>&1; then
  shim_dir=".slaps/shims"
  mkdir -p "$shim_dir"
  shim="$shim_dir/setsid"
  if [[ ! -x "$shim" ]]; then
    cat <<'EOF' > "$shim"
#!/bin/sh
exec "$@"
EOF
    chmod +x "$shim"
  fi
  export PATH="$(pwd)/$shim_dir:$PATH"
fi

WAVE=""
WORKERS=2
REFRESH=60
BLOCKERS_TTL=600
RECONCILE_SEC=600
IDLE_SLEEP=60
MODE=gh
START_LOGS=1
LOG_VIEWER_PID=""

PASS_THROUGH=()

while (( "$#" )); do
  case "$1" in
    -w) WAVE="$2"; shift 2;;
    -n) WORKERS="$2"; shift 2;;
    -r) REFRESH="$2"; shift 2;;
    -b) BLOCKERS_TTL="$2"; shift 2;;
    -R) RECONCILE_SEC="$2"; shift 2;;
    -i) IDLE_SLEEP="$2"; shift 2;;
    -m) MODE="$2"; shift 2;;
    --no-logs) START_LOGS=0; shift;;
    --) shift; PASS_THROUGH=("$@"); break;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$WAVE" ]]; then
  echo "Error: -w <wave> is required" >&2
  usage
  exit 2
fi

# Environment knobs
export SLAPS_WORKERS="$WORKERS"
export SLAPS_REFRESH_SEC="$REFRESH"
export SLAPS_BLOCKERS_TTL="$BLOCKERS_TTL"
export SLAPS_RECONCILE_SEC="$RECONCILE_SEC"
export SLAPS_WORKER_IDLE_SLEEP="$IDLE_SLEEP"

echo "[SLAPS] Settings: wave=$WAVE workers=$SLAPS_WORKERS refresh=${SLAPS_REFRESH_SEC}s blockers_ttl=${SLAPS_BLOCKERS_TTL}s reconcile=${SLAPS_RECONCILE_SEC}s idle_sleep=${SLAPS_WORKER_IDLE_SLEEP}s mode=$MODE"
echo "[SLAPS] Starting log viewer (reuse+follow) in background..."

if [[ "$START_LOGS" == "1" ]]; then
  # Start log viewer (reuse + follow). Non-blocking.
  if command -v python3 >/dev/null 2>&1; then
    nohup python3 tools/cli/slaps_logs.py >/dev/null 2>&1 &
  else
    nohup python tools/cli/slaps_logs.py >/dev/null 2>&1 &
  fi
  LOG_VIEWER_PID=$!
fi

cleanup() {
  if [[ -n "$LOG_VIEWER_PID" ]]; then
    kill "$LOG_VIEWER_PID" >/dev/null 2>&1 || true
    LOG_VIEWER_PID=""
  fi
}

trap cleanup EXIT

# Kick coordinator
PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then PY=python; fi

# Guarantee repo root on module path for -m imports
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

mkdir -p .slaps/logs || true
echo "[SLAPS] Launching coordinator (wave=$WAVE, mode=$MODE). Live log: .slaps/logs/coord.out"
set +e
"$PY" tools/cli/slaps_coord.py --waveStart "$WAVE" --mode "$MODE" "${PASS_THROUGH[@]}" 2>&1 | tee -a .slaps/logs/coord.out
rc=${PIPESTATUS[0]}
set -e
cleanup
if [[ "$START_LOGS" == "1" ]]; then
  tmux kill-session -t slaps-logs >/dev/null 2>&1 || true
fi
if [[ "$rc" -ne 0 ]]; then
  echo "[SLAPS] Coordinator failed (rc=$rc); halting."
else
  echo "[SLAPS] Coordinator completed successfully."
fi
exit "$rc"
