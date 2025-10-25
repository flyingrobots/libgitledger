#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <make-target> [args...]" >&2
    exit 1
fi

TARGET="$1"
shift

SRC_DIR="${SRC_DIR:-/workspace}"
WORK_ROOT_RAW="${WORK_ROOT:-/tmp/libgitledger}"
JOB_NAME="${LIBGITLEDGER_MATRIX_JOB:-matrix}"

if [[ -z "${JOB_NAME}" ]]; then
    echo "invoke: LIBGITLEDGER_MATRIX_JOB must not be empty" >&2
    exit 1
fi

if [[ "${JOB_NAME}" == .* || "${JOB_NAME}" == *".."* || "${JOB_NAME}" == */* || "${JOB_NAME}" == *\\* ]]; then
    echo "invoke: unsafe job name '${JOB_NAME}'" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "invoke: python3 is required to resolve WORK_ROOT" >&2
    exit 1
fi

WORK_ROOT="$(python3 - "$WORK_ROOT_RAW" <<'PY'
import os
import sys
work_root = sys.argv[1]
resolved = os.path.abspath(work_root)
print(resolved)
PY
)"

if [[ -z "${WORK_ROOT}" || "${WORK_ROOT}" != /* ]]; then
    echo "invoke: WORK_ROOT must resolve to an absolute path" >&2
    exit 1
fi

if [[ "${WORK_ROOT}" == "/" ]]; then
    echo "invoke: refusing to operate on root directory" >&2
    exit 1
fi

TARGET_DIR="$(python3 - "$WORK_ROOT" "$JOB_NAME" <<'PY'
import os
import sys
base = sys.argv[1]
job = sys.argv[2]
print(os.path.abspath(os.path.join(base, job)))
PY
)"

case "${TARGET_DIR}" in
    "${WORK_ROOT}"|${WORK_ROOT}/*)
        ;;
    *)
        echo "invoke: resolved target '${TARGET_DIR}' escapes work root '${WORK_ROOT}'" >&2
        exit 1
        ;;
esac

rm -rf -- "${TARGET_DIR}"
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

FIXTURE_SCRIPT="${SRC_DIR}/tools/testing/prepare-fixtures.sh"

if [[ ! -f "${FIXTURE_SCRIPT}" ]]; then
    echo "invoke: fixture script not found at ${FIXTURE_SCRIPT}" >&2
    exit 1
fi

if [[ ! -x "${FIXTURE_SCRIPT}" ]]; then
    if ! chmod +x "${FIXTURE_SCRIPT}" 2>/dev/null; then
        echo "invoke: unable to mark fixture script executable (${FIXTURE_SCRIPT})" >&2
        exit 1
    fi
fi

"${FIXTURE_SCRIPT}" "${LIBGITLEDGER_SANDBOX_ROOT}"

make "${TARGET}" "$@"
