#!/usr/bin/env bash
set -euo pipefail

tidy_bin="${1:-clang-tidy}"
build_dir="${BUILD_DIR:-build-tidy}"

cmake -S . -B "${build_dir}" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build "${build_dir}"

sources=$(git ls-files '*.c')
if [ -z "${sources}" ]; then
  echo "clang-tidy: no C sources to analyze"
  exit 0
fi

if [[ "$(uname)" == "Darwin" ]]; then
  export SDKROOT="$(xcrun --show-sdk-path)"
fi

for source in ${sources}; do
  "${tidy_bin}" --quiet -p "${build_dir}" "${source}"
done
