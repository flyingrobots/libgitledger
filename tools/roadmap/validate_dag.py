#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
from typing import Sequence, Tuple, List, Dict
from pathlib import Path

MMD = Path('docs/ROADMAP-DAG.mmd')

def run(cmd: Sequence[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout

def parse_mmd(text: str) -> Tuple[set, List[Tuple[str, str]], List[Tuple[str, str]]]:
    nodes = set()
    edges_hard: List[Tuple[str, str]] = []
    edges_soft: List[Tuple[str, str]] = []
    for ln in text.splitlines():
        m = re.match(r"\s*(N\d+)\[\"#(\d+) ", ln)
        if m:
            nodes.add((m.group(1), int(m.group(2))))
        m = re.match(r"\s*(N\d+)\s*==>\s*(N\d+)", ln)
        if m:
            edges_hard.append((m.group(1), m.group(2)))
        m = re.match(r"\s*(N\d+)\s*-->\s*(N\d+)", ln)
        if m:
            edges_hard.append((m.group(1), m.group(2)))
        m = re.match(r"\s*(N\d+)\s*-.->\s*(N\d+)", ln)
        if m:
            edges_soft.append((m.group(1), m.group(2)))
    return nodes, edges_hard, edges_soft

def gh_json(args: Sequence[str]) -> dict:
    out = run(["gh", *args])
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
        run(["docker", "run", "--rm", "-v", f"{MMD.parent.resolve()}:/data", "minlag/mermaid-cli", "-i", "/data/ROADMAP-DAG.mmd", "-o", "/data/.lint.svg"])
    except (RuntimeError, FileNotFoundError) as e:
        print(f"validate_dag: warning: mermaid lint skipped: {e}")

    # Sanity: all issue numbers exist
    missing: List[int] = []
    for num in node_to_issue.values():
        try:
            gh_json(["issue", "view", str(num), "--json", "number" ])
        except RuntimeError:
            missing.append(num)
    if missing:
        print(f"validate_dag: missing issues in DAG: {sorted(set(missing))}", file=sys.stderr)
        return 2

    # Validate edges reference existing nodes
    invalid_edges: List[Tuple[str, str]] = []
    for src, dst in edges_hard:
        if src not in node_to_issue or dst not in node_to_issue:
            invalid_edges.append((src, dst))
    if invalid_edges:
        print(f"validate_dag: edges reference non-existent nodes: {invalid_edges}", file=sys.stderr)
        return 3

    # Success
    print("validate_dag: OK")
    return 0

if __name__ == '__main__':
    sys.exit(main())
