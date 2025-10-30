#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <make-target> [args...]" >&2
    exit 1
fi

TARGET="$1"
shift

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_NAME="${LIBGITLEDGER_CONTAINER_IMAGE:-libgitledger-ci:latest}"

if ! command -v docker >/dev/null 2>&1; then
    echo "[container] ERROR: docker is required" >&2
    exit 1
fi

if [[ "${LIBGITLEDGER_SKIP_BUILD:-0}" == "1" ]]; then
    echo "[container] Skipping image build because LIBGITLEDGER_SKIP_BUILD=1"
else
    echo "[container] Ensuring image ${IMAGE_NAME} is available"
    docker pull "${IMAGE_NAME}" >/dev/null 2>&1 || true
    if ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
        echo "[container] Building image ${IMAGE_NAME}"
        docker build -t "${IMAGE_NAME}" -f "${SCRIPT_DIR}/Dockerfile" "${REPO_ROOT}"
    fi
fi

matrix_configs=(
    $'name=gcc-14\ncc=gcc-14\ncxx=g++-14\nrun_tidy=1'
    $'name=clang-18\ncc=clang\ncxx=clang++\nrun_tidy=0'
)

max_jobs="${LIBGITLEDGER_MATRIX_JOBS:-0}"
declare -a job_pids=()
declare -a job_names=()
status=0

start_job() {
    local config="$1"
    shift || true

    local name=""
    local cc=""
    local cxx=""
    local run_tidy="1"
    local supports_sanitizers="0"
    local supports_analyze="0"

    while IFS= read -r pair; do
        [[ -z "${pair}" ]] && continue
        local key="${pair%%=*}"
        local value="${pair#*=}"
        case "${key}" in
            name) name="${value}" ;;
            cc) cc="${value}" ;;
            cxx) cxx="${value}" ;;
            run_tidy) run_tidy="${value}" ;;
            sanitizers) supports_sanitizers="${value}" ;;
            analyze) supports_analyze="${value}" ;;
        esac
    done <<< "${config}"

    if [[ -z "${name}" ]]; then
        echo "[container] ERROR: matrix entry missing name" >&2
        return 1
    fi

    if [[ "${TARGET}" == "tidy" && "${run_tidy}" != "1" ]]; then
        echo "[container:${name}] Skipping target ${TARGET} (RUN_TIDY=0)"
        return 2
    fi

    if [[ "${TARGET}" == "sanitizers" && "${supports_sanitizers}" != "1" ]]; then
        echo "[container:${name}] Skipping target ${TARGET} (sanitizers unsupported)"
        return 2
    fi

    if [[ "${TARGET}" == "analyze" && "${supports_analyze}" != "1" ]]; then
        echo "[container:${name}] Skipping target ${TARGET} (analyzer unsupported)"
        return 2
    fi

    local target_escaped
    target_escaped=$(printf '%q' "${TARGET}")
    local docker_cmd="/workspace/tools/container/invoke.sh ${target_escaped}"
    for arg in "$@"; do
        docker_cmd+=" $(printf '%q' "${arg}")"
    done

    echo "[container:${name}] Running make ${TARGET}" "$@"

    docker run --rm \
        -e CC="${cc}" \
        -e CXX="${cxx}" \
        -e RUN_TIDY="${run_tidy}" \
        -e LIBGITLEDGER_SUPPORTS_SANITIZERS="${supports_sanitizers}" \
        -e LIBGITLEDGER_SUPPORTS_ANALYZE="${supports_analyze}" \
        -e SUPPORTS_SANITIZERS="${supports_sanitizers}" \
        -e SUPPORTS_ANALYZE="${supports_analyze}" \
        -e LIBGITLEDGER_IN_CONTAINER=true \
        -e LIBGITLEDGER_MATRIX_JOB="${name}" \
        -v "${REPO_ROOT}:/workspace:ro" \
        "${IMAGE_NAME}" \
        /bin/bash -lc "${docker_cmd}" &

    local pid=$!
    job_pids+=("${pid}")
    job_names+=("${name}")

    return 0
}

wait_for_oldest_job() {
    if [[ ${#job_pids[@]} -eq 0 ]]; then
        return 0
    fi

    local pid="${job_pids[0]}"
    local name="${job_names[0]}"

    if wait "${pid}"; then
        echo "[container:${name}] Completed successfully"
    else
        echo "[container:${name}] Failed" >&2
        status=1
    fi

    job_pids=("${job_pids[@]:1}")
    job_names=("${job_names[@]:1}")
}

for config in "${matrix_configs[@]}"; do
    if start_job "${config}" "$@"; then
        rc=0
    else
        rc=$?
    fi

    if [[ ${rc} -eq 0 ]]; then
        :
    elif [[ ${rc} -eq 2 ]]; then
        continue
    else
        status=1
        break
    fi

    while [[ "${max_jobs}" -gt 0 && ${#job_pids[@]} -ge "${max_jobs}" ]]; do
        wait_for_oldest_job
    done
done

while [[ ${#job_pids[@]} -gt 0 ]]; do
    wait_for_oldest_job
done

exit "${status}"
