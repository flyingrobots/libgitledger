#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <make-target> [args...]" >&2
    exit 1
fi

TARGET="$1"
shift

SRC_DIR="${SRC_DIR:-/workspace}"
WORK_ROOT="${WORK_ROOT:-/tmp/libgitledger}" 
JOB_NAME="${LIBGITLEDGER_MATRIX_JOB:-matrix}"
TARGET_DIR="${WORK_ROOT}/${JOB_NAME}"

rm -rf "${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

rsync -a --delete \
    --exclude 'build' \
    --exclude 'build-*' \
    --exclude 'meson-*' \
    --exclude '.git/modules' \
    "${SRC_DIR}/" "${TARGET_DIR}/"

cd "${TARGET_DIR}"

export LIBGITLEDGER_IN_CONTAINER=1
export RUN_TIDY="${RUN_TIDY:-1}"

git config --global --add safe.directory "${TARGET_DIR}"

if [[ -d .git ]]; then
    while read -r remote; do
        git remote remove "${remote}" || true
    done < <(git remote)
    git config --local --unset-all remote.origin.url >/dev/null 2>&1 || true
    git config --local --unset-all remote.origin.pushurl >/dev/null 2>&1 || true
    git config --local advice.detachedHead false
fi

export LIBGITLEDGER_SANDBOX_ROOT="${TARGET_DIR}/.container-fixtures"
mkdir -p "${LIBGITLEDGER_SANDBOX_ROOT}"
"${SRC_DIR}/tools/testing/prepare-fixtures.sh" "${LIBGITLEDGER_SANDBOX_ROOT}"

make "${TARGET}" "$@"
