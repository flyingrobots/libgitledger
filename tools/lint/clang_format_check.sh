#!/usr/bin/env bash
set -euo pipefail

format_bin="${1:-clang-format}"
mapfile -t files < <(git ls-files '*.c' '*.h')

if [[ ${#files[@]} -eq 0 ]]; then
  echo "clang-format: no C sources to check"
  exit 0
fi

for file in "${files[@]}"; do
  "${format_bin}" --dry-run --Werror "${file}"
done
