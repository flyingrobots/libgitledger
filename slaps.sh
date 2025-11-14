#!/usr/bin/env bash
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)
exec "$DIR/tools/cli/slaps_go.sh" -w 1 -n 2 -r 60 -b 600 -R 600 -i 60

