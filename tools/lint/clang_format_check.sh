#!/usr/bin/env bash
set -euo pipefail

format_bin="${1:-clang-format}"
files=$(git ls-files '*.c' '*.h')

if [ -z "${files}" ]; then
  echo "clang-format: no C sources to check"
  exit 0
fi

for file in ${files}; do
  "${format_bin}" --dry-run --Werror "${file}"
done
