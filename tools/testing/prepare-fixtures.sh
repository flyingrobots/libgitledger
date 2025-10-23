#!/usr/bin/env bash
set -euo pipefail

DEST_ROOT="${1:-}"

if [[ -z "${DEST_ROOT}" ]]; then
    echo "Usage: $0 <destination-root>" >&2
    exit 1
fi

resolve_dest_root() {
    local input_path="${1}"
    local resolved=""

    if command -v python3 >/dev/null 2>&1; then
        resolved="$(python3 - "$input_path" <<'PY'
import os
import sys

target = sys.argv[1]
try:
    print(os.path.abspath(target))
except Exception as exc:
    sys.stderr.write(f"python3 failed to resolve path: {exc}\n")
    sys.exit(1)
PY
)" || return 1
    elif command -v realpath >/dev/null 2>&1; then
        resolved="$(realpath "${input_path}")" || return 1
    elif command -v readlink >/dev/null 2>&1; then
        resolved="$(readlink -f "${input_path}")" || return 1
    else
        resolved="$(cd "${input_path}" 2>/dev/null && pwd -P)" || {
            echo "Error: unable to resolve destination root without python3, realpath, or readlink -f" >&2
            return 1
        }
    fi

    printf '%s\n' "${resolved}"
}

if ! DEST_ROOT="$(resolve_dest_root "${DEST_ROOT}")"; then
    exit 1
fi

case "${DEST_ROOT}" in
    /|/bin|/usr|/home|/etc|/var|/tmp|/sys|/proc|/dev|/opt|/sbin)
        echo "Error: DEST_ROOT cannot be a system directory: ${DEST_ROOT}" >&2
        exit 1
        ;;
esac

if [[ "${DEST_ROOT}" == "${HOME}" ]] || [[ "${DEST_ROOT}" == "$(pwd)" ]]; then
    echo "Error: refusing to operate on critical path: ${DEST_ROOT}" >&2
    exit 1
fi

rm -rf -- "${DEST_ROOT}"
mkdir -p "${DEST_ROOT}"

FIXTURE_REPO="${DEST_ROOT}/ledger-fixture"

mkdir -p "${FIXTURE_REPO}"
cd "${FIXTURE_REPO}"

git init -q
git config --local user.name "libgitledger-fixture"
git config --local user.email "fixture@example.com"
echo "fixture" > README.md
git add README.md
git commit -q -m "Bootstrap fixture repo"

while read -r remote; do
    git remote remove "${remote}" || true
done < <(git remote)

echo "${DEST_ROOT}" > "${DEST_ROOT}/.path"
