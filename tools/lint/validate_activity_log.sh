#!/usr/bin/env bash
set -euo pipefail

log_file="ACTIVITY.log.jsonl"

python3 - "$log_file" <<'PY'
import json
import os
import re
import sys

log_path = sys.argv[1]
if not os.path.exists(log_path):
    print(f"activity-log: missing log file: {log_path}", file=sys.stderr)
    sys.exit(1)

def is_rfc3339(s: str) -> bool:
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$', s))

count = 0
try:
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
            except UnicodeDecodeError as e:
                print(f"activity-log: invalid encoding in log file: {e}", file=sys.stderr)
                sys.exit(1)
            # Accept either summary blocks or activity entries per schema intent.
            if 'timestamp' in obj:
                branches = obj.get('branches', [])
                activity = obj.get('activity', [])
                if not isinstance(branches, list):
                    print(f"activity-log: summary 'branches' must be an array on line {idx}", file=sys.stderr)
                    sys.exit(1)
                if not isinstance(activity, list):
                    print(f"activity-log: summary 'activity' must be an array on line {idx}", file=sys.stderr)
                    sys.exit(1)
                for j, b in enumerate(branches):
                    if not isinstance(b, str):
                        print(f"activity-log: branches[{j}] must be string on line {idx}", file=sys.stderr)
                        sys.exit(1)
                for j, a in enumerate(activity):
                    if not (isinstance(a, str) or isinstance(a, dict)):
                        print(f"activity-log: activity[{j}] must be string or object on line {idx}", file=sys.stderr)
                        sys.exit(1)
            else:
                required = {'who', 'what', 'where', 'when', 'why', 'how', 'protip'}
                if not required.issubset(obj.keys()):
                    missing = sorted(required - set(obj.keys()))
                    print(f"activity-log: missing keys {missing} on line {idx}", file=sys.stderr)
                    sys.exit(1)
                if not isinstance(obj['where'], list):
                    print(f"activity-log: 'where' must be an array on line {idx}", file=sys.stderr)
                    sys.exit(1)
                if not isinstance(obj['when'], str) or not is_rfc3339(obj['when']):
                    print(f"activity-log: 'when' must be RFC3339 string on line {idx}", file=sys.stderr)
                    sys.exit(1)
            count += 1
except OSError as e:
    print(f"activity-log: cannot open {log_path}: {e}", file=sys.stderr)
    sys.exit(1)

if count == 0:
    print("activity-log: no entries found", file=sys.stderr)
    sys.exit(1)
print("activity-log: validation passed")
PY
