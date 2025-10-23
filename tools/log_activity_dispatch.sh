#!/usr/bin/env bash
set -euo pipefail

missing=()
for key in WHO WHAT WHY HOW PROTIP; do
    if [[ -z "${!key:-}" ]]; then
        missing+=("${key}")
    fi
done

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Usage: WHO=… WHAT=… WHY=… HOW=… PROTIP=… [WHERE='file1 file2'|WHERE__0='path with spaces'] [WHEN='2025-10-23T00:00:00Z'] make log" >&2
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

declare -a where_entries=()

if [[ -n "${WHERE_JSON:-}" ]]; then
    if command -v python3 >/dev/null 2>&1; then
        mapfile -t parsed_where < <(python3 - <<'PY'
import json
import os
try:
    data = json.loads(os.environ["WHERE_JSON"])
except Exception as exc:  # noqa: BLE001
    raise SystemExit(f"invalid WHERE_JSON: {exc}") from exc
for item in data:
    print(item)
PY
        )
        where_entries+=("${parsed_where[@]}")
    else
        echo "log_activity_dispatch: WHERE_JSON provided but python3 is unavailable" >&2
        exit 1
    fi
fi

if [[ -n "${WHERE:-}" ]]; then
    if [[ "${WHERE}" == *$'\n'* ]]; then
        while IFS= read -r entry; do
            [[ -z "${entry}" ]] && continue
            where_entries+=("${entry}")
        done < <(printf '%s' "${WHERE}" | tr -d '\r')
    else
        read -r -a parsed_where <<<"${WHERE}"
        where_entries+=("${parsed_where[@]}")
    fi
fi

index=0
while true; do
    var="WHERE__${index}"
    if [[ -n "${!var:-}" ]]; then
        where_entries+=("${!var}")
        index=$((index + 1))
    else
        break
    fi
done

if [[ ${#where_entries[@]} -gt 0 ]]; then
    for path in "${where_entries[@]}"; do
        args+=(--where "${path}")
    done
fi

if [[ -n "${WHEN:-}" ]]; then
    args+=(--when "${WHEN}")
fi

exec "${LOG_TOOL}" "${args[@]}"
