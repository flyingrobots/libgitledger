#!/usr/bin/env bash
set -euo pipefail

tidy_bin="${1:-clang-tidy}"
build_dir="${BUILD_DIR:-build-tidy}"
require_build="${CLANG_TIDY_REQUIRE_BUILD:-0}"

if ! command -v cmake >/dev/null 2>&1; then
  echo "clang-tidy: cmake is required" >&2
  exit 1
fi

if ! command -v "${tidy_bin}" >/dev/null 2>&1; then
  echo "clang-tidy: required binary '${tidy_bin}' not found" >&2
  exit 1
fi

cmake -S . -B "${build_dir}" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON

compile_db="${build_dir}/compile_commands.json"
should_build=0
filtered_dir="${build_dir}-filtered"
filtered_db="${filtered_dir}/compile_commands.json"
rm -f "${filtered_db}"
mkdir -p "${filtered_dir}"

if [[ ! -f "${compile_db}" ]]; then
  echo "clang-tidy: compile_commands.json missing after configure; building targets" >&2
  should_build=1
fi

case "${require_build}" in
  1|true|TRUE|yes|YES)
    should_build=1
    ;;
esac

if (( should_build )); then
  cmake --build "${build_dir}"
fi

if [[ ! -f "${compile_db}" ]]; then
  echo "clang-tidy: compile_commands.json not found in ${build_dir}" >&2
  exit 1
fi

declare -a filtered_sources=()

# Allow callers to override which top-level directories are eligible for analysis.
allowed_roots_raw="${CLANG_TIDY_ALLOWED_ROOTS:-src:libgitledger}"

while IFS= read -r line; do
  filtered_sources+=("${line}")
done < <(python3 - "$build_dir" "$allowed_roots_raw" "$filtered_db" <<'PY'
import json
import sys
from pathlib import Path

build_dir = Path(sys.argv[1])
allowed_roots = {part for part in sys.argv[2].split(':') if part}
filtered_db_path = Path(sys.argv[3])
db_path = build_dir / "compile_commands.json"
data = json.loads(db_path.read_text())
repo_root = Path.cwd().resolve()
filtered = []
sources = []

if not allowed_roots:
    sys.stderr.write("clang-tidy: CLANG_TIDY_ALLOWED_ROOTS expanded to an empty list\n")
    sys.exit(1)

for entry in data:
    directory = Path(entry.get("directory", build_dir))
    file_path = Path(entry["file"])
    if not file_path.is_absolute():
        file_path = (directory / file_path).resolve()
    else:
        file_path = file_path.resolve()
    try:
        rel = file_path.relative_to(repo_root)
    except ValueError:
        continue
    if rel.parts and rel.parts[0] in allowed_roots:
        entry["file"] = str(file_path)
        filtered.append(entry)
        sources.append(str(rel))

filtered_db_path.write_text(json.dumps(filtered, indent=2))

print("\n".join(sorted(set(sources))))
PY
)

if [[ ! -f "${filtered_db}" ]]; then
  echo "clang-tidy: filtered compile_commands.json not written to ${filtered_db}" >&2
  exit 1
fi

if [[ ${#filtered_sources[@]} -eq 0 ]]; then
  echo "clang-tidy: no eligible C sources after filtering" >&2
  echo "Set CLANG_TIDY_ALLOWED_ROOTS to expand the search if this was unexpected" >&2
  exit 1
fi

# Bind the header filter to the concrete repo root so clang-tidy never walks system headers.
header_filter="${CLANG_TIDY_HEADER_FILTER:-}"
if [[ -z "${header_filter}" ]]; then
  header_filter=$(python3 - <<'PY'
import os
import re
repo_root = os.path.abspath('.')
escaped = re.escape(repo_root)
print(f"^{escaped}/(include|src|libgitledger)/.*\\.(h|c)$")
PY
  )
fi

if ! HEADER_FILTER="${header_filter}" python3 - <<'PY'; then
import os
import re
import sys
pattern = os.environ["HEADER_FILTER"]
try:
    re.compile(pattern)
except re.error as exc:
    sys.stderr.write(f"clang-tidy: invalid header filter '{pattern}': {exc}\n")
    sys.exit(1)
PY
  exit 1
fi

if [[ "$(uname)" == "Darwin" ]]; then
  if [[ -z "${SDKROOT:-}" ]]; then
    if sdk_path=$(xcrun --show-sdk-path 2>/dev/null); then
      if [[ -z "${sdk_path}" ]]; then
        echo "clang-tidy: xcrun reported an empty SDK path" >&2
        exit 1
      fi
      export SDKROOT="${sdk_path}"
    else
      echo "clang-tidy: failed to resolve SDKROOT via xcrun" >&2
      exit 1
    fi
  fi
fi

for source in "${filtered_sources[@]}"; do
  "${tidy_bin}" -p "${filtered_dir}" --header-filter="${header_filter}" "${source}"
done
