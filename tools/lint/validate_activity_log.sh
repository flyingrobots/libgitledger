#!/usr/bin/env bash
set -euo pipefail

if ! command -v jq >/dev/null 2>&1; then
    echo "activity-log: jq is required" >&2
    exit 1
fi

if ! command -v npx >/dev/null 2>&1; then
    echo "activity-log: npx is required" >&2
    exit 1
fi

log_file="ACTIVITY.log.jsonl"
schema_file="ACTIVITY.schema.json"

if [[ ! -f "${log_file}" ]]; then
    echo "activity-log: ${log_file} not found" >&2
    exit 1
fi

if [[ ! -f "${schema_file}" ]]; then
    echo "activity-log: ${schema_file} not found" >&2
    exit 1
fi

tmp_dir=$(mktemp -d)
trap 'rm -rf "${tmp_dir}"' EXIT

index=0
while IFS= read -r line; do
    if [[ -z "${line}" ]]; then
        continue
    fi
    if ! printf '%s\n' "${line}" | jq -e '.' >/dev/null; then
        echo "activity-log: invalid JSON on line $((index + 1))" >&2
        exit 1
    fi
    printf '%s\n' "${line}" > "${tmp_dir}/${index}.json"
    index=$((index + 1))
done < "${log_file}"

if (( index == 0 )); then
    echo "activity-log: no entries found" >&2
    exit 1
fi

declare -a data_args
for entry in "${tmp_dir}"/*.json; do
    data_args+=(-d "${entry}")
done

npx --yes ajv-cli@5.0.0 validate --spec=draft7 -s "${schema_file}" "${data_args[@]}" >/dev/null

echo "activity-log: validation passed"
