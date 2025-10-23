#!/usr/bin/env bash
set -euo pipefail

tidy_bin="${1:-clang-tidy}"
build_dir="${BUILD_DIR:-build-tidy}"

cmake -S . -B "${build_dir}" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "${build_dir}"

filtered_sources=$(python3 - "$build_dir" <<'PY'
import json
import sys
from pathlib import Path

build_dir = Path(sys.argv[1])
db_path = build_dir / "compile_commands.json"
data = json.loads(db_path.read_text())
repo_root = Path.cwd().resolve()
allowed_roots = {"src", "libgitledger"}
filtered = []
sources = []

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

db_path.write_text(json.dumps(filtered, indent=2))

print("\n".join(sorted(set(sources))))
PY
)

if [ -z "${filtered_sources}" ]; then
  echo "clang-tidy: no eligible C sources after filtering"
  exit 0
fi

if [[ "$(uname)" == "Darwin" ]]; then
  export SDKROOT="$(xcrun --show-sdk-path)"
fi

for source in ${filtered_sources}; do
  "${tidy_bin}" --quiet -p "${build_dir}" "${source}"
done
