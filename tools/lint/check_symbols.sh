#!/usr/bin/env bash
set -euo pipefail

# Symbol policy for freestanding smoke binary: ensure no forbidden imports.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")"/../.. && pwd)"

targets=()
if [[ -f "${repo_root}/build-ffs/gitledger_ffs_smoke" ]]; then
  targets+=("${repo_root}/build-ffs/gitledger_ffs_smoke")
fi
if [[ -f "${repo_root}/meson-ffs/gitledger_ffs_smoke" ]]; then
  targets+=("${repo_root}/meson-ffs/gitledger_ffs_smoke")
fi

if [[ ${#targets[@]} -eq 0 ]]; then
  echo "symbols-check: no freestanding smoke binary found. Build one first (see CI freestanding job)." >&2
  exit 0
fi

deny_re='(^|[^A-Za-z0-9_])(printf|fprintf|vprintf|vfprintf|puts|gets|scanf|sscanf|getenv|atexit|__libc_start_main|__stack_chk_fail|malloc|free|calloc|realloc|strlen|strcpy|strcmp|memcpy|memset|exit|abort)($|[^A-Za-z0-9_])'

fail=0
for bin in "${targets[@]}"; do
  if ! file "$bin" | grep -q 'ELF'; then
    echo "symbols-check: skipping non-ELF ${bin}" >&2
    continue
  fi
  # Unresolved symbols should be none; additionally grep strings for deny-list hints.
  nm_out=$(nm -u "$bin" 2>&1 || true)
  if [[ -n "$nm_out" ]]; then
    echo "symbols-check: unexpected unresolved symbols in ${bin}" >&2
    echo "$nm_out" | sed 's/^/  /' >&2
    fail=1
  fi
  str_hits=$(strings -a "$bin" | grep -E "$deny_re" || true)
  if [[ -n "$str_hits" ]]; then
    echo "symbols-check: forbidden symbol reference detected in ${bin}" >&2
    echo "$str_hits" | sed 's/^/  /' >&2
    fail=1
  fi
done

if [[ $fail -ne 0 ]]; then
  exit 1
fi
echo "symbols-check: OK"
