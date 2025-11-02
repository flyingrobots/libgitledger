#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MMD = Path('docs/ROADMAP-DAG.mmd')

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout

def parse_mmd(text):
    nodes = set()
    edges_hard = []
    edges_soft = []
    for ln in text.splitlines():
        m = re.match(r"\s*(N\d+)\[\"#(\d+) ", ln)
        if m:
            nodes.add((m.group(1), int(m.group(2))))
        m = re.match(r"\s*(N\d+)\s*==>\s*(N\d+)", ln)
        if m:
            edges_hard.append((m.group(1), m.group(2)))
        m = re.match(r"\s*(N\d+)\s*-.->\s*(N\d+)", ln)
        if m:
            edges_soft.append((m.group(1), m.group(2)))
    return nodes, edges_hard, edges_soft

def gh_json(args):
    out = run(["gh"] + args)
    return json.loads(out)

def main():
    if not MMD.exists():
        print("validate_dag: missing docs/ROADMAP-DAG.mmd", file=sys.stderr)
        return 1
    text = MMD.read_text(encoding='utf-8')
    nodes, edges_hard, _ = parse_mmd(text)
    # Map node id -> issue number
    node_to_issue = {n: num for (n,num) in nodes}

    # Basic syntax lint via mermaid-cli if available (optional)
    try:
        run(["docker", "run", "--rm", "-v", f"{MMD.parent.resolve() }:/data", "minlag/mermaid-cli", "-i", "/data/ROADMAP-DAG.mmd", "-o", "/data/.lint.svg"])
    except Exception as e:
        print(f"validate_dag: warning: mermaid lint skipped: {e}")

    # Sanity: all issue numbers exist
    missing = []
    for num in node_to_issue.values():
        try:
            gh_json(["issue", "view", str(num), "--json", "number" ])
        except Exception:
            missing.append(num)
    if missing:
        print(f"validate_dag: missing issues in DAG: {sorted(set(missing))}", file=sys.stderr)
        return 2

    # Success
    print("validate_dag: OK")
    return 0

if __name__ == '__main__':
    sys.exit(main())

