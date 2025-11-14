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

WAVE=""
WORKERS=2
REFRESH=60
BLOCKERS_TTL=600
RECONCILE_SEC=600
IDLE_SLEEP=60
MODE=gh
START_LOGS=1

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

if [[ "$START_LOGS" == "1" ]]; then
  # Start log viewer (reuse + follow). Non-blocking.
  if command -v python3 >/dev/null 2>&1; then
    nohup python3 tools/cli/slaps_logs.py >/dev/null 2>&1 &
  else
    nohup python tools/cli/slaps_logs.py >/dev/null 2>&1 &
  fi
fi

# Kick coordinator
PY=${PYTHON:-python3}
if ! command -v "$PY" >/dev/null 2>&1; then PY=python; fi

exec "$PY" tools/cli/slaps_coord.py --waveStart "$WAVE" --mode "$MODE" "${PASS_THROUGH[@]}"

