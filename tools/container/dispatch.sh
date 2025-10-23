#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"

if [[ -z "${TARGET}" ]]; then
    echo "Usage: $0 <make-target> [args...]" >&2
    exit 1
fi

shift

if [[ "${LIBGITLEDGER_IN_CONTAINER:-0}" == "1" ]]; then
    exec make "host-${TARGET}" "$@"
fi

if [[ "${I_KNOW_WHAT_I_AM_DOING:-0}" == "1" ]]; then
    exec make "host-${TARGET}" "$@"
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required to run ${TARGET} safely." >&2
    echo "If you really intend to run on the host, re-run with I_KNOW_WHAT_I_AM_DOING=1." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${SCRIPT_DIR}/run-matrix.sh" "${TARGET}" "$@"

