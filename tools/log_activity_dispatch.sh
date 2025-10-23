#!/usr/bin/env bash
set -euo pipefail

missing=()
for key in WHO WHAT WHY HOW PROTIP; do
    if [[ -z "${!key:-}" ]]; then
        missing+=("${key}")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Usage: WHO=… WHAT=… WHY=… HOW=… PROTIP=… [WHERE='file1 file2'] [WHEN='2025-10-23T00:00:00Z'] make log" >&2
    echo "Missing required fields: ${missing[*]}" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_TOOL="${SCRIPT_DIR}/log_activity.py"

if [[ ! -x "${LOG_TOOL}" ]]; then
    echo "log_activity_dispatch: cannot find executable ${LOG_TOOL}" >&2
    exit 1
fi

args=(
    --who "${WHO}"
    --what "${WHAT}"
    --why "${WHY}"
    --how "${HOW}"
    --protip "${PROTIP}"
)

if [[ -n "${WHERE:-}" ]]; then
    for path in ${WHERE}; do
        args+=(--where "${path}")
    done
fi

if [[ -n "${WHEN:-}" ]]; then
    args+=(--when "${WHEN}")
fi

exec "${LOG_TOOL}" "${args[@]}"
