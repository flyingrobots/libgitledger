#!/usr/bin/env bash
set -euo pipefail

log_file="ACTIVITY.log.jsonl"

if [[ ! -f "${log_file}" ]]; then
    echo "activity-log: ${log_file} not found" >&2
    exit 1
fi

python3 - "$log_file" <<'PY'
import json, os, re, sys

log_path = sys.argv[1]
if not os.path.exists(log_path):
    sys.exit("activity-log: missing log file")

def is_rfc3339(s: str) -> bool:
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$', s))

count=0
with open(log_path, 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"activity-log: invalid JSON on line {idx}: {e}", file=sys.stderr)
            sys.exit(1)
        # Accept either summary blocks or activity entries per schema intent.
        if 'timestamp' in obj:
            # minimal shape check
            if not isinstance(obj.get('branches', []), list) or not isinstance(obj.get('activity', []), list):
                print(f"activity-log: invalid summary on line {idx}", file=sys.stderr)
                sys.exit(1)
        else:
            required = {'who','what','where','when','why','how','protip'}
            if not required.issubset(obj.keys()):
                missing = required - set(obj.keys())
                print(f"activity-log: missing keys {sorted(missing)} on line {idx}", file=sys.stderr)
                sys.exit(1)
            if not isinstance(obj['where'], list):
                print(f"activity-log: 'where' must be an array on line {idx}", file=sys.stderr)
                sys.exit(1)
            if not isinstance(obj['when'], str) or not is_rfc3339(obj['when']):
                print(f"activity-log: 'when' must be RFC3339 string on line {idx}", file=sys.stderr)
                sys.exit(1)
        count += 1
if count == 0:
    print("activity-log: no entries found", file=sys.stderr)
    sys.exit(1)
print("activity-log: validation passed")
PY
